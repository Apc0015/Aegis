"""
Department Router — maps a user query to the correct FAISS project_id.

When project_id is "general", this module picks the best-matching department
index. When project_id is already specific (e.g. "hr"), it passes through.

Departments correspond to the indexed project_ids created by
scripts/index_knowledge_base.py — lowercase folder names.
"""
import logging
from typing import List

logger = logging.getLogger(__name__)

# Keyword → department index mapping.
# Order matters: first match wins for overlapping keywords.
DEPARTMENT_KEYWORDS: dict[str, List[str]] = {
    "hr": [
        "employee", "leave", "vacation", "pto", "time off", "sick leave",
        "parental leave", "onboarding", "offboarding", "hiring", "recruit",
        "performance review", "compensation", "salary", "pay", "benefits",
        "health insurance", "dental", "401k", "handbook", "hr policy",
        "work from home", "remote work", "termination", "resignation",
    ],
    "finance": [
        "budget", "expense", "reimbursement", "invoice", "revenue", "cost",
        "payroll", "salary budget", "financial report", "fiscal", "accounting",
        "procurement", "purchase order", "vendor payment", "capex", "opex",
    ],
    "engineering": [
        "code", "deployment", "pull request", "sprint", "architecture",
        "api", "infrastructure", "ci/cd", "database", "kubernetes",
        "microservice", "release", "bug", "issue tracker", "devops",
        "tech debt", "code review", "engineering process",
    ],
    "sales": [
        "quota", "deal", "pipeline", "crm", "prospect", "lead", "close",
        "sales process", "account executive", "sdr", "demo", "proposal",
        "contract negotiation", "commission", "sales team", "revenue target",
        "customer acquisition",
    ],
    "marketing": [
        "campaign", "content", "brand", "seo", "social media", "demand gen",
        "event", "webinar", "marketing", "lead generation", "mql", "sql",
        "email campaign", "press release", "messaging",
    ],
    "legal": [
        "contract", "agreement", "nda", "compliance", "regulation", "gdpr",
        "legal", "lawsuit", "intellectual property", "patent", "trademark",
        "licensing", "liability", "risk management", "legal review",
    ],
    "it": [
        "help desk", "ticket", "password reset", "vpn", "laptop", "equipment",
        "software license", "it support", "security policy", "access request",
        "firewall", "network", "it infrastructure", "active directory",
    ],
    "operations": [
        "office", "facility", "vendor", "supplier", "travel", "logistics",
        "operations", "sop", "procedure", "process improvement", "emergency",
        "business continuity", "supply chain", "workspace",
    ],
    "product": [
        "product roadmap", "feature", "user research", "sprint planning",
        "product requirements", "prd", "user story", "backlog", "stakeholder",
        "product release", "product strategy", "feedback",
    ],
    "customer_success": [
        "customer", "client", "churn", "renewal", "onboarding customer",
        "health score", "qbr", "success plan", "nps", "csat",
        "support ticket", "customer satisfaction", "account management",
    ],
}

# Departments that span cross-functional queries — searched last as fallback
CROSS_FUNCTIONAL_IDS = ["hr", "general"]


def route_multi(query: str, current_project_id: str, top_k: int = 2) -> List[str]:
    """
    Return up to top_k department IDs ranked by keyword score.
    Used for cross-department queries that should search multiple indexes.

    Always returns at least ['general'] as a fallback.
    """
    if current_project_id and current_project_id != "general":
        return [current_project_id]

    query_lower = query.lower()
    scores: dict[str, int] = {}

    for dept, keywords in DEPARTMENT_KEYWORDS.items():
        score = sum(1 for kw in keywords if kw in query_lower)
        if score > 0:
            scores[dept] = score

    if not scores:
        return ["general"]

    ranked = sorted(scores.keys(), key=lambda d: scores[d], reverse=True)
    return ranked[:top_k] or ["general"]
