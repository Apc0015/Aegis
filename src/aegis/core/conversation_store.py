"""
In-memory conversation history store.

Keyed by conversation_id (UUID from client). Stores messages as
[{"role": "user"|"assistant", "content": "..."}] per session.

Thread-safe for concurrent async access. Trims to MAX_TURNS pairs
to prevent unbounded memory growth and token overflow.
"""

import threading
from collections import defaultdict
from typing import Dict, List
import logging

logger = logging.getLogger(__name__)

MAX_TURNS = 10  # keep last 10 user+assistant pairs = 20 messages

# Number of turns that triggers summarization
_SUMMARIZE_THRESHOLD = 8   # 16 messages
# Number of oldest turns (message pairs) to collapse into summary
_TURNS_TO_SUMMARIZE = 6    # 12 messages collapsed → 1 summary message
# Recent turns to always preserve intact (message pairs)
_TURNS_TO_KEEP = 2         # 4 messages kept verbatim


class ConversationStore:
    """
    SECURITY: conversations are keyed by (user_id, conversation_id), not by the
    client-supplied conversation_id alone. conversation_id comes from the client,
    so without the user scope any authenticated user could read (via prompt
    injection of history) or poison another user's conversation by guessing or
    reusing their id.
    """

    def __init__(self):
        self._lock = threading.Lock()
        self._store: Dict[str, List[Dict[str, str]]] = defaultdict(list)

    @staticmethod
    def _key(user_id: str, conversation_id: str) -> str:
        return f"{user_id}\x1f{conversation_id}"

    def get_history(self, user_id: str, conversation_id: str) -> List[Dict[str, str]]:
        with self._lock:
            return list(self._store[self._key(user_id, conversation_id)])

    def append(self, user_id: str, conversation_id: str, role: str, content: str) -> None:
        with self._lock:
            key = self._key(user_id, conversation_id)
            msgs = self._store[key]
            msgs.append({"role": role, "content": content})
            # Trim: keep last MAX_TURNS pairs (MAX_TURNS*2 messages)
            if len(msgs) > MAX_TURNS * 2:
                self._store[key] = msgs[-(MAX_TURNS * 2):]

    def clear(self, user_id: str, conversation_id: str) -> None:
        with self._lock:
            self._store.pop(self._key(user_id, conversation_id), None)

    def session_count(self) -> int:
        with self._lock:
            return len(self._store)

    async def summarize_and_compress(self, user_id: str, conversation_id: str, llm_service) -> None:
        """
        Summarize the oldest turns in a conversation to prevent token overflow.

        When history has >= _SUMMARIZE_THRESHOLD turns (16 messages):
        - Takes the oldest _TURNS_TO_SUMMARIZE turns (12 messages)
        - Summarizes them via the LLM into a single system message
        - Replaces those messages with: {"role": "system", "content": "Previous conversation summary: <summary>"}
        - Keeps the _TURNS_TO_KEEP most recent turns (4 messages) verbatim

        Safe to call concurrently — uses the store's lock when reading/writing.
        Failures are logged but do not propagate.
        """
        key = self._key(user_id, conversation_id)
        with self._lock:
            msgs = list(self._store.get(key, []))

        # 16 messages = 8 turns
        if len(msgs) < _SUMMARIZE_THRESHOLD * 2:
            return

        # Messages to summarize: oldest _TURNS_TO_SUMMARIZE turns = oldest 12 messages
        summarize_count = _TURNS_TO_SUMMARIZE * 2  # 12
        keep_count = _TURNS_TO_KEEP * 2            # 4

        to_summarize = msgs[:summarize_count]
        to_keep = msgs[-keep_count:]

        # Build a transcript for the LLM
        transcript_lines = []
        for m in to_summarize:
            role_label = m["role"].capitalize()
            transcript_lines.append(f"{role_label}: {m['content']}")
        transcript = "\n".join(transcript_lines)

        summary_prompt = (
            "Summarize the following conversation excerpt briefly and concisely. "
            "Capture the key questions asked and answers given. "
            "Do not include opinions or filler — only facts exchanged.\n\n"
            f"{transcript}"
        )

        try:
            summary = await llm_service.chat(
                [
                    {
                        "role": "system",
                        "content": "You are a concise conversation summarizer.",
                    },
                    {"role": "user", "content": summary_prompt},
                ],
                temperature=0.2,
                max_tokens=512,
            )
        except Exception as e:
            logger.warning(
                f"summarize_and_compress: LLM summarization failed for '{conversation_id}': {e}"
            )
            return

        summary_message = {
            "role": "system",
            "content": f"Previous conversation summary: {summary.strip()}",
        }

        compressed = [summary_message] + to_keep

        with self._lock:
            self._store[key] = compressed

        logger.info(
            f"summarize_and_compress: compressed {len(msgs)} → {len(compressed)} "
            f"messages for conversation '{conversation_id}'"
        )
