"""
Admin-only endpoints.
GET  /api/v1/admin/users           — list configured users (no passwords)
GET  /api/v1/admin/access-rules    — return raw access_rules.yaml as JSON
GET  /api/v1/admin/connectors      — connector status (which are configured)
POST /api/v1/admin/access-rules    — overwrite access_rules.yaml (admin only)
"""
import logging
import os
import yaml
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from typing import List, Dict, Any

from api.auth import UserInfo, get_current_user

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/admin", tags=["admin"])

ACCESS_RULES_PATH = "config/access_rules.yaml"


def _require_admin(current_user: UserInfo = Depends(get_current_user)) -> UserInfo:
    if current_user.user_role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin role required")
    return current_user


@router.get("/users")
async def list_users(current_user: UserInfo = Depends(_require_admin)):
    """Return list of configured users (username + role only, no passwords)."""
    raw = os.getenv("AEGIS_USERS", "")
    users = []
    for entry in raw.split(","):
        entry = entry.strip()
        if not entry:
            continue
        parts = entry.split(":")
        if len(parts) >= 2:
            users.append({"user_id": parts[0], "role": parts[1]})
    return {"users": users}


@router.get("/access-rules")
async def get_access_rules(current_user: UserInfo = Depends(_require_admin)):
    """Return the current access_rules.yaml as a JSON object."""
    try:
        with open(ACCESS_RULES_PATH) as f:
            rules = yaml.safe_load(f) or {}
        return {"rules": rules}
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="access_rules.yaml not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Could not read access rules: {e}")


@router.post("/access-rules")
async def update_access_rules(
    payload: Dict[str, Any],
    current_user: UserInfo = Depends(_require_admin),
):
    """
    Overwrite access_rules.yaml. Body must be a valid access-rules object.

    These rules ARE the data firewall — a malformed write makes every query fail
    (column-rule loading raises). So we validate the shape, confirm it round-trips
    through YAML, back up the current file, and write atomically.
    """
    # 1. Schema validation — must be an object with a 'roles' mapping.
    if not isinstance(payload, dict) or not isinstance(payload.get("roles"), dict):
        raise HTTPException(
            status_code=422,
            detail="Invalid access rules: expected an object with a 'roles' mapping.",
        )
    if not payload["roles"]:
        raise HTTPException(status_code=422, detail="Invalid access rules: 'roles' cannot be empty.")

    # 1b. Rule-value validation. The enforcement layer fails closed on unknown
    # values, but rejecting typos here ("Block", "DENY") tells the admin about
    # the mistake instead of silently blocking columns they meant to allow.
    from aegis.rbac.rbac_module import VALID_RULES
    for role_name, role_cfg in payload["roles"].items():
        if not isinstance(role_cfg, dict):
            raise HTTPException(status_code=422, detail=f"Invalid role config for '{role_name}'")
        col_rules = role_cfg.get("db_column_rules", {})
        if not isinstance(col_rules, dict):
            raise HTTPException(
                status_code=422, detail=f"'{role_name}.db_column_rules' must be a mapping"
            )
        for table, table_rules in col_rules.items():
            if not isinstance(table_rules, dict):
                raise HTTPException(
                    status_code=422,
                    detail=f"Rules for '{role_name}.{table}' must be a mapping of column → rule",
                )
            for col, rule in table_rules.items():
                if rule not in VALID_RULES:
                    raise HTTPException(
                        status_code=422,
                        detail=(
                            f"Invalid rule '{rule}' for '{role_name}.{table}.{col}' — "
                            f"must be one of {', '.join(VALID_RULES)}"
                        ),
                    )

    # 2. Confirm it serializes and re-parses identically before touching disk.
    try:
        serialized = yaml.dump(payload, default_flow_style=False, allow_unicode=True)
        if yaml.safe_load(serialized) != payload:
            raise ValueError("rules did not round-trip through YAML")
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Invalid access rules: {e}")

    # 3. Back up current file, then write atomically via a temp file + os.replace.
    import os
    import shutil
    import tempfile
    try:
        if os.path.exists(ACCESS_RULES_PATH):
            shutil.copy2(ACCESS_RULES_PATH, ACCESS_RULES_PATH + ".bak")
        target_dir = os.path.dirname(ACCESS_RULES_PATH) or "."
        fd, tmp_path = tempfile.mkstemp(dir=target_dir, suffix=".tmp")
        with os.fdopen(fd, "w") as f:
            f.write(serialized)
        os.replace(tmp_path, ACCESS_RULES_PATH)
        logger.info(f"access_rules.yaml updated by admin '{current_user.user_id}' (backup written)")
        return {"status": "ok", "message": "Access rules updated"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Could not write access rules: {e}")


@router.get("/connectors")
async def connector_status(current_user: UserInfo = Depends(_require_admin)):
    """Return which connectors are configured (env vars present)."""
    return {
        "connectors": {
            "google": bool(os.getenv("AEGIS_GOOGLE_CLIENT_ID")),
            "microsoft": bool(os.getenv("AEGIS_MICROSOFT_CLIENT_ID")),
            "slack": bool(os.getenv("AEGIS_SLACK_BOT_TOKEN")),
        }
    }
