"""
Audit log endpoints (admin only).

GET  /api/v1/audit         — fetch recent audit records
POST /api/v1/audit/export  — download as CSV
"""
import csv
import io
import logging
from typing import List, Optional

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from api.auth import UserInfo
from api.dependencies import get_agent, require_admin

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/audit", tags=["audit"])


# ── Pydantic schemas ───────────────────────────────────────────────────────────
class AuditRecord(BaseModel):
    id: int
    timestamp: str
    user_id: str
    user_role: str
    query_text: str
    project_id: Optional[str] = None
    departments_accessed: Optional[str] = None
    access_verdict: str
    denial_reason: Optional[str] = None
    confidence_score: Optional[float] = None
    confidence_verdict: Optional[str] = None
    routing_path: Optional[str] = None
    model_used: Optional[str] = None
    latency_ms: Optional[int] = None
    db_triggered: Optional[int] = None
    rag_triggered: Optional[int] = None
    firewall_applied: Optional[int] = None
    raw_data_destroyed: Optional[int] = None
    columns_blocked: Optional[str] = None
    columns_anonymized: Optional[str] = None


# ── Get recent audit records ───────────────────────────────────────────────────
@router.get("", response_model=List[AuditRecord])
async def get_audit_log(
    limit: int = 200,
    current_user: UserInfo = Depends(require_admin),
    agent = Depends(get_agent),
):
    """
    Return the most recent audit log records. Admin only.
    Maximum 1000 records per request.
    """
    limit = min(limit, 1000)
    try:
        records = agent.audit.get_recent(limit=limit)
        return records
    except Exception as e:
        logger.error(f"Failed to fetch audit log: {e}")
        from fastapi import HTTPException
        raise HTTPException(status_code=500, detail=f"Could not fetch audit log: {e}")


# ── Export audit as CSV ────────────────────────────────────────────────────────
@router.post("/export")
async def export_audit_csv(
    limit: int = 10000,
    current_user: UserInfo = Depends(require_admin),
    agent = Depends(get_agent),
):
    """
    Stream audit records as a CSV download. Admin only.
    """
    limit = min(limit, 50000)
    try:
        records = agent.audit.get_recent(limit=limit)
    except Exception as e:
        logger.error(f"Failed to export audit log: {e}")
        from fastapi import HTTPException
        raise HTTPException(status_code=500, detail=f"Could not export audit log: {e}")

    if not records:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="No audit records found")

    def generate_csv():
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=records[0].keys())
        writer.writeheader()
        for row in records:
            writer.writerow(row)
        yield output.getvalue()

    return StreamingResponse(
        generate_csv(),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=rapid_audit_export.csv"},
    )
