"""
Slack connector — fetches messages and file attachments from configured channels.

Uses Slack Web API (slack_sdk). Requires:
  pip install slack_sdk
  AEGIS_SLACK_BOT_TOKEN env var (xoxb-...)

Config in connectors.yaml per project:
  slack:
    enabled: true
    channels: ["#general", "#hr-team", "C0123456789"]  # name or channel_id
    include_files: true      # download file attachments
    include_threads: true    # include thread replies
    lookback_days: 30        # how far back on first sync (default 30)
"""
import logging
from datetime import datetime, timedelta, timezone
from typing import AsyncIterator, Optional

from aegis.connectors.base import BaseConnector, ConnectorFile
from aegis.connectors.delta_tracker import DeltaTracker

logger = logging.getLogger(__name__)

# Timestamp tracker prefix for last-sync cursors per channel
_CURSOR_PREFIX = "slack"
_CURSOR_SUFFIX = "cursor"

SUPPORTED_FILE_TYPES = {"pdf", "docx", "txt", "md"}


class SlackConnector(BaseConnector):
    """
    Connector for Slack — yields text files of channel messages and
    optionally downloads file attachments.
    """

    SOURCE = "slack"

    def __init__(self, tracker: DeltaTracker, bot_token: str):
        self._tracker = tracker
        self._bot_token = bot_token

    # ------------------------------------------------------------------
    # BaseConnector interface
    # ------------------------------------------------------------------

    def is_authenticated(self) -> bool:
        return bool(self._bot_token)

    def get_auth_url(self, state: str) -> str:
        # Bot tokens don't use an OAuth redirect flow
        return ""

    def exchange_code(self, code: str) -> None:
        # No-op for bot token auth
        pass

    # ------------------------------------------------------------------
    # Main sync logic
    # ------------------------------------------------------------------

    async def list_new_files(
        self, project_id: str, dept_config: dict
    ) -> AsyncIterator[ConnectorFile]:
        try:
            from slack_sdk import WebClient
            from slack_sdk.errors import SlackApiError
        except ImportError:
            logger.warning(
                "SlackConnector: slack_sdk not installed — skipping sync. "
                "Install with: pip install slack_sdk"
            )
            return

        if not self.is_authenticated():
            logger.warning("SlackConnector: AEGIS_SLACK_BOT_TOKEN not set — skipping sync")
            return

        client = WebClient(token=self._bot_token)

        channels: list = dept_config.get("channels", [])
        include_files: bool = dept_config.get("include_files", True)
        include_threads: bool = dept_config.get("include_threads", True)
        lookback_days: int = int(dept_config.get("lookback_days", 30))

        if not channels:
            logger.warning(
                f"SlackConnector: no channels configured for project '{project_id}'"
            )
            return

        # Resolve channel names → IDs
        channel_map = self._resolve_channels(client, channels)

        for channel_input, channel_id in channel_map.items():
            if not channel_id:
                logger.warning(
                    f"SlackConnector: could not resolve channel '{channel_input}' — skipping"
                )
                continue

            # Determine oldest timestamp to fetch from
            oldest_ts = self._get_oldest_ts(channel_id, lookback_days)

            logger.debug(
                f"SlackConnector: syncing #{channel_input} ({channel_id}) "
                f"from ts={oldest_ts} (project={project_id})"
            )

            messages = []
            newest_ts: Optional[str] = None

            try:
                cursor = None
                while True:
                    kwargs = {
                        "channel": channel_id,
                        "oldest": oldest_ts,
                        "limit": 200,
                    }
                    if cursor:
                        kwargs["cursor"] = cursor

                    from slack_sdk.errors import SlackApiError  # already imported above
                    try:
                        resp = client.conversations_history(**kwargs)
                    except SlackApiError as e:
                        logger.error(
                            f"SlackConnector: error fetching history for "
                            f"'{channel_input}': {e.response['error']}"
                        )
                        break

                    batch = resp.get("messages", [])
                    messages.extend(batch)

                    if batch and newest_ts is None:
                        # Slack returns newest first
                        newest_ts = batch[0].get("ts")

                    if not resp.get("has_more"):
                        break
                    cursor = resp["response_metadata"].get("next_cursor")

            except Exception as e:
                logger.error(f"SlackConnector: unexpected error for '{channel_input}': {e}")
                continue

            if not messages:
                continue

            # Optionally fetch thread replies
            if include_threads:
                messages = await self._expand_threads(
                    client, channel_id, messages
                )

            # Build per-day text file(s) and yield
            async for cf in self._messages_to_files(
                client,
                messages,
                channel_id,
                channel_input,
                project_id,
                include_files,
            ):
                yield cf

            # Update cursor to newest message timestamp
            if newest_ts:
                self._tracker.mark_seen(
                    self.SOURCE,
                    f"{channel_id}:{_CURSOR_SUFFIX}",
                    newest_ts,
                )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _resolve_channels(self, client, channels: list) -> dict:
        """
        Map each entry in *channels* (name or ID) to a Slack channel ID.
        Returns {input_value: channel_id_or_None}.
        """
        result = {}
        # Build name→id map lazily only if we have any non-ID entries
        needs_lookup = [c for c in channels if not c.startswith("C")]
        name_to_id: dict = {}

        if needs_lookup:
            try:
                cursor = None
                while True:
                    kwargs = {"types": "public_channel,private_channel", "limit": 200}
                    if cursor:
                        kwargs["cursor"] = cursor
                    resp = client.conversations_list(**kwargs)
                    for ch in resp.get("channels", []):
                        name_to_id[f"#{ch['name']}"] = ch["id"]
                        name_to_id[ch["name"]] = ch["id"]
                    if not resp.get("has_more"):
                        break
                    cursor = resp["response_metadata"].get("next_cursor")
            except Exception as e:
                logger.warning(f"SlackConnector: could not list channels: {e}")

        for ch in channels:
            if ch.startswith("C") and len(ch) > 8:
                result[ch] = ch  # already an ID
            else:
                result[ch] = name_to_id.get(ch) or name_to_id.get(ch.lstrip("#"))

        return result

    def _get_oldest_ts(self, channel_id: str, lookback_days: int) -> str:
        """Return the Slack timestamp string to use as the oldest boundary."""
        cursor_key = f"{channel_id}:{_CURSOR_SUFFIX}"
        record_version = None

        # Peek into state without going through is_new() to get the raw value
        key = f"{self.SOURCE}:{cursor_key}"
        with self._tracker._lock:
            record = self._tracker._state.get(key)
            if record:
                record_version = record.get("version")

        if record_version:
            # Advance by 1 microsecond to avoid re-fetching the last message
            try:
                ts_float = float(record_version) + 0.000001
                return str(ts_float)
            except (TypeError, ValueError):
                pass

        # First sync: go back lookback_days
        cutoff = datetime.now(timezone.utc) - timedelta(days=lookback_days)
        return str(cutoff.timestamp())

    async def _expand_threads(self, client, channel_id: str, messages: list) -> list:
        """Inline thread replies into the message list."""
        expanded = []
        for msg in messages:
            expanded.append(msg)
            if msg.get("reply_count", 0) == 0:
                continue
            ts = msg.get("ts")
            if not ts:
                continue
            try:
                resp = client.conversations_replies(channel=channel_id, ts=ts, limit=200)
                replies = resp.get("messages", [])[1:]  # skip the parent
                expanded.extend(replies)
            except Exception as e:
                logger.warning(f"SlackConnector: could not fetch thread {ts}: {e}")
        return expanded

    async def _messages_to_files(
        self,
        client,
        messages: list,
        channel_id: str,
        channel_label: str,
        project_id: str,
        include_files: bool,
    ) -> AsyncIterator[ConnectorFile]:
        """
        Group messages by date into text files and optionally yield attachments.
        Uses DeltaTracker.is_content_changed() to skip unchanged content.
        """
        # Group messages by date
        by_date: dict = {}
        for msg in messages:
            ts = msg.get("ts", "0")
            try:
                dt = datetime.fromtimestamp(float(ts), tz=timezone.utc)
                date_key = dt.strftime("%Y-%m-%d")
            except (TypeError, ValueError):
                date_key = "unknown"
            by_date.setdefault(date_key, []).append(msg)

        safe_label = channel_label.lstrip("#").replace("/", "_")

        for date_key, day_msgs in sorted(by_date.items()):
            # Sort oldest first within the day
            day_msgs.sort(key=lambda m: float(m.get("ts", "0")))

            lines = []
            for msg in day_msgs:
                ts = msg.get("ts", "")
                try:
                    dt_str = datetime.fromtimestamp(float(ts), tz=timezone.utc).strftime(
                        "%Y-%m-%d %H:%M:%S UTC"
                    )
                except (TypeError, ValueError):
                    dt_str = ts

                user = msg.get("user") or msg.get("bot_id") or "unknown"
                text = msg.get("text", "").strip()
                lines.append(f"[{dt_str}] @{user}: {text}")

                # Mark individual message as seen for delta tracking
                msg_key = f"{channel_id}:{ts}"
                self._tracker.mark_seen(self.SOURCE, msg_key, ts)

                # Handle file attachments
                if include_files:
                    for f_meta in msg.get("files", []):
                        async for cf in self._download_attachment(
                            client, f_meta, project_id
                        ):
                            yield cf

            content = "\n".join(lines) + "\n"
            content_bytes = content.encode("utf-8")
            filename = f"slack_{safe_label}_{date_key}.txt"
            file_id = f"{channel_id}:text:{date_key}"

            if self._tracker.is_content_changed(self.SOURCE, file_id, content_bytes):
                self._tracker.record_content_hash(self.SOURCE, file_id, content_bytes)
                logger.debug(
                    f"SlackConnector: yielding text file '{filename}' (project={project_id})"
                )
                yield ConnectorFile(content_bytes, filename, file_id, project_id)

    async def _download_attachment(
        self, client, file_meta: dict, project_id: str
    ) -> AsyncIterator[ConnectorFile]:
        """Download a Slack file attachment if its type is supported."""
        filetype = file_meta.get("filetype", "").lower()
        if filetype not in SUPPORTED_FILE_TYPES:
            return

        file_id = file_meta.get("id", "")
        name = file_meta.get("name") or f"slack_file_{file_id}.{filetype}"
        url = file_meta.get("url_private_download") or file_meta.get("url_private")

        if not url or not file_id:
            return

        try:
            import urllib.request
            req = urllib.request.Request(
                url,
                headers={"Authorization": f"Bearer {self._bot_token}"},
            )
            with urllib.request.urlopen(req, timeout=30) as resp:
                data: bytes = resp.read()
        except Exception as e:
            logger.warning(f"SlackConnector: could not download attachment '{name}': {e}")
            return

        if self._tracker.is_content_changed(self.SOURCE, file_id, data):
            self._tracker.record_content_hash(self.SOURCE, file_id, data)
            logger.debug(f"SlackConnector: yielding attachment '{name}' (project={project_id})")
            yield ConnectorFile(data, name, file_id, project_id)
