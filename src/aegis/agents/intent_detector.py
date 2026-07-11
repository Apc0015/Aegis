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
    from aegis.services.llm_service import LLMService

logger = logging.getLogger(__name__)

LLM_INTENT_SYSTEM = """You are an intent classifier for an enterprise medical AI system.

The system has three data sources:
1. DOCUMENTS — uploaded PDFs, medical policies, clinical procedures, compliance guides, staff handbooks
2. DATABASE  — live records (patients, appointments, medical_records, prescriptions, billing, lab_results, employees, departments, insurance_info, payroll, leave_requests, medical_facilities)
3. UPLOADED FILE — file the user attached to this chat message

Classify the user query and return ONLY valid JSON in this exact format:
{
  "needs_documents": true or false,
  "needs_database": true or false,
  "is_internal": true or false,
  "is_verify": true or false,
  "reasoning": "one sentence"
}

Rules:
- needs_documents = true  when the query asks about policies, rules, guidelines, procedures, protocols, compliance
- needs_database  = true  when the query asks about live records, counts, statuses, specific patient/employee data, billing, lab results, appointments, prescriptions, payroll
- is_internal     = true  when the query is about the organization's own data, patients, staff, or operations (not general medical knowledge)
- is_verify       = true  when user uploads a file AND asks to check/verify/validate claims in it against company data
- Both needs_documents and needs_database can be true at the same time
- is_verify implies user wants fact-checking, not just retrieval
- Medical questions about THIS facility's patients, staff, or records are is_internal=true and needs_database=true"""

# Keywords that signal a verify/fact-check intent (file uploaded + check against DB)
VERIFY_KEYWORDS = [
    "correct", "verify", "validate", "check", "is this right", "is this correct",
    "matches", "accurate", "wrong", "incorrect", "confirm", "does this match",
    "compare", "discrepancy", "mismatch", "right or wrong", "fact check",
]

# Keywords that signal the query needs live database records
DB_INTENT_KEYWORDS = [
    # Medical / patient data
    "patient", "patients", "how many patient", "patient count", "patient status",
    "diagnosis", "diagnoses", "medical record", "medical records", "icd",
    "prescription", "prescriptions", "prescribed", "medication",
    "appointment", "appointments", "scheduled visit",
    "lab result", "lab results", "blood test", "cbc", "hba1c", "lipid panel",
    "billing", "bill", "billed", "insurance", "insurance record", "coverage",
    "medical facility", "medical facilities", "bed capacity", "icu",
    "admission", "discharge", "readmission",
    # Employee / operational data
    "leave", "parental leave", "sick leave", "annual leave", "vacation", "pto", "time off", "fmla",
    "headcount", "team size", "how many employees", "how many people", "employee count",
    "payroll", "salary", "pay", "wage", "compensation", "net pay", "gross pay",
    "my salary", "my pay", "my record", "my status", "my leave balance", "my team",
    "approved", "pending", "request status", "department size",
]

# Keywords that strongly signal internal company query (should NOT trigger web search)
INTERNAL_QUERY_KEYWORDS = [
    "our", "company", "hr", "policy", "policies", "handbook", "team",
    "my", "employee", "staff", "department", "office", "internal",
    "benefits", "leave", "salary", "manager", "onboarding",
    "patient", "patients", "medical record", "prescription", "appointment",
    "billing", "insurance", "payroll", "facility", "clinical", "hipaa",
    "diagnosis", "lab result", "medical facility",
]


def detect_intent(query: str, has_file: bool = False) -> dict:
    """
    Lightweight keyword-based intent detection.
    Returns dict with needs_documents, needs_database, is_external, is_verify flags.

    has_file: True when user attached a file to this chat message.
    """
    query_lower = query.lower()

    needs_database  = any(kw in query_lower for kw in DB_INTENT_KEYWORDS)
    is_internal     = any(kw in query_lower for kw in INTERNAL_QUERY_KEYWORDS)
    is_verify       = has_file and any(kw in query_lower for kw in VERIFY_KEYWORDS)

    needs_documents = True  # default: always check documents
    is_external     = not is_internal and not needs_database

    return {
        "needs_documents": needs_documents,
        "needs_database":  needs_database,
        "is_external":     is_external,
        "is_internal":     is_internal,
        "is_verify":       is_verify,
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
        is_verify       = bool(parsed.get("is_verify", False))
        is_external     = not is_internal and not needs_database

        logger.info(
            f"LLM intent | needs_docs={needs_documents} | needs_db={needs_database} "
            f"| is_verify={is_verify} | reasoning={parsed.get('reasoning', '')}"
        )

        return {
            "needs_documents": needs_documents,
            "needs_database":  needs_database,
            "is_external":     is_external,
            "is_internal":     is_internal,
            "is_verify":       is_verify,
        }

    except Exception as e:
        logger.warning(f"LLM intent detection failed ({e}) — falling back to keyword detection")
        return detect_intent(query)
