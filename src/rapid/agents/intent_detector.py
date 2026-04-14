"""
Intent Detector
Determines whether a query needs documents, database, or both.

Two modes:
  detect_intent()      — keyword-based, zero latency, no LLM call
  detect_intent_llm()  — LLM-based, ~500ms, more accurate for ambiguous queries

Used by master_agent.py to decide which pipelines to run.
"""
import json
import logging
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from rapid.services.llm_service import LLMService

logger = logging.getLogger(__name__)

LLM_INTENT_SYSTEM = """You are an intent classifier for an HR enterprise AI system.

The system has two data sources:
1. DOCUMENTS — uploaded PDFs, policies, handbooks, onboarding guides
2. DATABASE  — live HR records (employees, leave requests, benefits, headcount, policies table)

Classify the user query and return ONLY valid JSON in this exact format:
{
  "needs_documents": true or false,
  "needs_database": true or false,
  "is_internal": true or false,
  "reasoning": "one sentence"
}

Rules:
- needs_documents = true  when the query asks about policies, rules, guidelines, procedures
- needs_database  = true  when the query asks about live records, counts, statuses, specific data
- is_internal     = true  when the query is about company/HR matters (not general knowledge)
- Both can be true at the same time
- needs_documents defaults to true unless the query is purely about live numbers"""

# Keywords that signal the query needs live database records
DB_INTENT_KEYWORDS = [
    "leave", "parental leave", "sick leave", "annual leave", "vacation", "pto", "time off",
    "benefit", "health insurance", "dental", "401k", "enrollment", "enroll",
    "headcount", "team size", "how many employees", "how many people",
    "my salary", "my pay", "my compensation", "my record", "my status",
    "my leave balance", "my benefits", "my team",
    "approved", "pending", "request status"
]

# Keywords that strongly signal internal company query (should NOT trigger web search)
INTERNAL_QUERY_KEYWORDS = [
    "our", "company", "hr", "policy", "policies", "handbook", "team",
    "my", "employee", "staff", "department", "office", "internal",
    "benefits", "leave", "salary", "manager", "onboarding"
]


def detect_intent(query: str) -> dict:
    """
    Lightweight keyword-based intent detection.
    Returns dict with needs_documents, needs_database, is_external flags.

    This is intentionally simple — a rule-based heuristic that adds
    no latency and no additional LLM calls.
    """
    query_lower = query.lower()

    needs_database = any(kw in query_lower for kw in DB_INTENT_KEYWORDS)
    is_internal = any(kw in query_lower for kw in INTERNAL_QUERY_KEYWORDS)

    # Documents are always searched unless the query is purely about
    # live records (e.g. "what is my leave balance") with no policy component
    needs_documents = True  # default: always check documents
    if needs_database and not is_internal:
        # Pure data query like "how many employees in engineering" —
        # database is enough, but still check documents for context
        needs_documents = True

    is_external = not is_internal and not needs_database

    return {
        "needs_documents": needs_documents,
        "needs_database": needs_database,
        "is_external": is_external,
        "is_internal": is_internal
    }


async def detect_intent_llm(query: str, llm: "LLMService") -> dict:
    """
    LLM-based intent detection. More accurate than keyword matching for
    ambiguous or conversational queries.

    Adds ~500ms latency. Falls back to keyword detection if LLM call fails.

    Returns same dict format as detect_intent().
    """
    try:
        raw = await llm.chat_simple(
            prompt=f"Classify this HR query:\n\n{query}",
            system=LLM_INTENT_SYSTEM,
            temperature=0.0,
        )

        # Parse JSON from LLM response
        # Strip markdown code fences if present
        raw = raw.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        raw = raw.strip()

        parsed = json.loads(raw)

        needs_documents = bool(parsed.get("needs_documents", True))
        needs_database  = bool(parsed.get("needs_database", False))
        is_internal     = bool(parsed.get("is_internal", True))
        is_external     = not is_internal and not needs_database

        logger.info(
            f"LLM intent | needs_docs={needs_documents} | "
            f"needs_db={needs_database} | reasoning={parsed.get('reasoning', '')}"
        )

        return {
            "needs_documents": needs_documents,
            "needs_database":  needs_database,
            "is_external":     is_external,
            "is_internal":     is_internal,
        }

    except Exception as e:
        logger.warning(f"LLM intent detection failed ({e}) — falling back to keyword detection")
        return detect_intent(query)
