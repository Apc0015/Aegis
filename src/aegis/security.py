"""
Shared input-validation helpers for Aegis.

`project_id` flows from untrusted clients straight into filesystem paths
(``data/faiss/aegis_<id>.index``, ``data/bm25/<id>.pkl``) and BM25 files are
loaded with ``pickle.load`` — so an unsanitized id is both a path-traversal and
an arbitrary-deserialization vector. Every router that accepts a project_id must
route it through ``sanitize_project_id`` before it reaches a service.
"""
import re

# Lowercase alphanumerics + underscore only. Leading underscore is allowed so the
# internally generated session-file ids ("_session_<user>_<hash>") validate too.
_PROJECT_ID_RE = re.compile(r"^_?[a-z0-9][a-z0-9_]{0,62}$")


class InvalidProjectId(ValueError):
    """Raised when a project_id contains unsafe characters or the wrong shape."""


def is_valid_project_id(project_id: str) -> bool:
    return bool(project_id) and _PROJECT_ID_RE.match(project_id) is not None


def sanitize_project_id(project_id: str, *, default: str | None = None) -> str:
    """
    Return ``project_id`` unchanged if it is safe, else raise InvalidProjectId.

    When ``default`` is provided, a blank/whitespace id resolves to the default
    instead of raising (used by query endpoints that treat "" as "general").
    Traversal attempts ("../x", "a/b", "a\\b") and any character outside
    [a-z0-9_] are always rejected — never silently coerced — so a malicious id
    can neither escape the data directory nor plant a pickle file.
    """
    pid = (project_id or "").strip()
    if not pid and default is not None:
        return default
    if not is_valid_project_id(pid):
        raise InvalidProjectId(
            f"Invalid project_id {project_id!r}: must match [a-z0-9_] (max 63 chars)."
        )
    return pid
