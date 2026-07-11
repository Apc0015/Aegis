"""
ConnectorManager — orchestrates all external data source connectors.

Responsibilities:
  - Load config/connectors.yaml on startup
  - Start watchdog live watchers for local connectors
  - Run 15-minute scheduled sync loop (asyncio background task)
  - Feed new files into the Aegis _ingest_file pipeline
  - Expose status and manual sync trigger for the API layer
"""
import asyncio
import logging
import os
from pathlib import Path
from typing import Any, Callable, Dict, Optional

import yaml

from aegis.connectors.delta_tracker import DeltaTracker
from aegis.connectors.local_connector import LocalConnector
from aegis.connectors.gmail_connector import GmailConnector
from aegis.connectors.gdrive_connector import GDriveConnector
from aegis.connectors.onedrive_connector import OneDriveConnector
from aegis.connectors.slack_connector import SlackConnector
from aegis.connectors.sharepoint_connector import SharePointConnector

logger = logging.getLogger(__name__)

CONFIG_PATH = Path("config/connectors.yaml")
SYNC_INTERVAL_SECONDS = 15 * 60  # 15 minutes


class ConnectorManager:
    """
    Singleton that owns all connectors and the background sync loop.
    Injected with an ingest_fn so it stays decoupled from FastAPI/agent internals.
    """

    def __init__(self, ingest_fn: Callable):
        """
        ingest_fn: async callable(file_bytes, filename, project_id) → None
        Called for every new file discovered by any connector.
        """
        self._ingest_fn = ingest_fn
        self._tracker = DeltaTracker()
        self._config: Dict[str, Any] = self._load_config()
        self._sync_task: Optional[asyncio.Task] = None

        # Instantiate connectors from env vars
        google_client_id     = os.getenv("AEGIS_GOOGLE_CLIENT_ID", "")
        google_client_secret = os.getenv("AEGIS_GOOGLE_CLIENT_SECRET", "")
        google_redirect      = os.getenv(
            "AEGIS_GOOGLE_REDIRECT_URI",
            "http://localhost:8000/api/v1/connectors/google/callback",
        )
        ms_client_id   = os.getenv("AEGIS_MICROSOFT_CLIENT_ID", "")
        ms_tenant_id   = os.getenv("AEGIS_MICROSOFT_TENANT_ID", "common")
        ms_redirect    = os.getenv(
            "AEGIS_MICROSOFT_REDIRECT_URI",
            "http://localhost:8000/api/v1/connectors/onedrive/callback",
        )

        slack_token = os.getenv("AEGIS_SLACK_BOT_TOKEN", "")

        self.local      = LocalConnector(self._tracker, self._on_local_file)
        self.gmail      = GmailConnector(self._tracker, google_client_id, google_client_secret, google_redirect)
        self.gdrive     = GDriveConnector(self._tracker, google_client_id, google_client_secret, google_redirect)
        self.onedrive   = OneDriveConnector(self._tracker, ms_client_id, ms_tenant_id, ms_redirect)
        self.slack      = SlackConnector(self._tracker, slack_token)
        self.sharepoint = SharePointConnector(self._tracker, ms_client_id, ms_tenant_id, ms_redirect)


    def _load_config(self) -> Dict[str, Any]:
        if not CONFIG_PATH.exists():
            logger.info("ConnectorManager: config/connectors.yaml not found — connectors disabled")
            return {}
        try:
            with open(CONFIG_PATH) as f:
                data = yaml.safe_load(f) or {}
            return data.get("connectors", {})
        except Exception as e:
            logger.error(f"ConnectorManager: failed to load connectors.yaml: {e}")
            return {}

    def _dept_config(self, project_id: str, source: str) -> dict:
        return self._config.get(project_id, {}).get(source, {})


    async def start(self) -> None:
        """Start local watchers and background 15-min sync loop."""
        self._start_local_watchers()
        self._sync_task = asyncio.create_task(self._sync_loop(), name="connector_sync")
        logger.info("ConnectorManager: started (15-min sync + live local watchers)")

    async def stop(self) -> None:
        if self._sync_task:
            self._sync_task.cancel()
            try:
                await self._sync_task
            except asyncio.CancelledError:
                pass
        self.local.stop_all()
        logger.info("ConnectorManager: stopped")


    def _start_local_watchers(self) -> None:
        for project_id, sources in self._config.items():
            local_cfg = sources.get("local", {})
            if local_cfg.get("enabled") and local_cfg.get("watch"):
                path = local_cfg.get("path", "")
                if path:
                    self.local.start_watcher(project_id, path)

    async def _on_local_file(self, data: bytes, filename: str, project_id: str) -> None:
        """Callback from watchdog live watcher — runs in a thread, needs asyncio.run()."""
        await self._ingest(data, filename, project_id, source="local")


    async def _sync_loop(self) -> None:
        while True:
            try:
                await self._sync_all()
            except Exception as e:
                logger.error(f"ConnectorManager: sync error: {e}")
            await asyncio.sleep(SYNC_INTERVAL_SECONDS)

    async def sync_all(self) -> Dict[str, int]:
        """Public method for manual sync trigger. Returns files_ingested per source."""
        return await self._sync_all()

    async def sync_project(self, project_id: str) -> Dict[str, int]:
        """Sync a single department across all configured sources."""
        return await self._sync_one(project_id)

    async def _sync_all(self) -> Dict[str, int]:
        totals: Dict[str, int] = {"local": 0, "gmail": 0, "gdrive": 0, "onedrive": 0, "slack": 0, "sharepoint": 0}
        for project_id in self._config:
            counts = await self._sync_one(project_id)
            for src, n in counts.items():
                totals[src] = totals.get(src, 0) + n
        return totals

    async def _sync_one(self, project_id: str) -> Dict[str, int]:
        counts: Dict[str, int] = {}

        # Local scheduled scan
        local_cfg = self._dept_config(project_id, "local")
        if local_cfg.get("enabled"):
            n = await self._run_connector(self.local, project_id, local_cfg, "local")
            counts["local"] = n

        # Gmail
        gmail_cfg = self._dept_config(project_id, "gmail")
        if gmail_cfg.get("enabled"):
            n = await self._run_connector(self.gmail, project_id, gmail_cfg, "gmail")
            counts["gmail"] = n

        # Google Drive
        gdrive_cfg = self._dept_config(project_id, "gdrive")
        if gdrive_cfg.get("enabled"):
            n = await self._run_connector(self.gdrive, project_id, gdrive_cfg, "gdrive")
            counts["gdrive"] = n

        # OneDrive
        onedrive_cfg = self._dept_config(project_id, "onedrive")
        if onedrive_cfg.get("enabled"):
            n = await self._run_connector(self.onedrive, project_id, onedrive_cfg, "onedrive")
            counts["onedrive"] = n

        # Slack
        slack_cfg = self._dept_config(project_id, "slack")
        if slack_cfg.get("enabled"):
            n = await self._run_connector(self.slack, project_id, slack_cfg, "slack")
            counts["slack"] = n

        # SharePoint
        sharepoint_cfg = self._dept_config(project_id, "sharepoint")
        if sharepoint_cfg.get("enabled"):
            n = await self._run_connector(self.sharepoint, project_id, sharepoint_cfg, "sharepoint")
            counts["sharepoint"] = n

        return counts

    async def _run_connector(self, connector, project_id: str, dept_cfg: dict, source: str) -> int:
        count = 0
        try:
            async for cf in connector.list_new_files(project_id, dept_cfg):
                await self._ingest(cf.bytes_, cf.filename, cf.project_id, source)
                count += 1
        except Exception as e:
            logger.error(f"ConnectorManager: {source}/{project_id} error: {e}")
        return count

    async def _ingest(self, data: bytes, filename: str, project_id: str, source: str) -> None:
        try:
            await self._ingest_fn(data, filename, project_id)
            logger.info(f"ConnectorManager: ingested '{filename}' ({source} → {project_id})")
        except Exception as e:
            logger.error(f"ConnectorManager: ingest failed for '{filename}': {e}")


    def status(self) -> Dict[str, Any]:
        return {
            "local":      {"authenticated": True,                              "configured_projects": self._configured_for("local")},
            "gmail":      {"authenticated": self.gmail.is_authenticated(),      "configured_projects": self._configured_for("gmail")},
            "gdrive":     {"authenticated": self.gdrive.is_authenticated(),     "configured_projects": self._configured_for("gdrive")},
            "onedrive":   {"authenticated": self.onedrive.is_authenticated(),   "configured_projects": self._configured_for("onedrive")},
            "slack":      {"authenticated": self.slack.is_authenticated(),      "configured_projects": self._configured_for("slack")},
            "sharepoint": {"authenticated": self.sharepoint.is_authenticated(), "configured_projects": self._configured_for("sharepoint")},
        }

    def _configured_for(self, source: str) -> list:
        return [
            pid for pid, srcs in self._config.items()
            if srcs.get(source, {}).get("enabled")
        ]
