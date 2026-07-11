import asyncio
import os
from typing import Optional, List, Dict, AsyncIterator
from openai import AsyncOpenAI
from aegis.config import LLM_PROVIDERS


class LLMService:
    """
    Multi-provider LLM abstraction. Single chat() interface regardless of provider.
    Supported: openai, anthropic, ollama, openrouter, lm_studio

    Features:
    - 3-tier context-overflow retry (full → truncated → minimal)
    - Streaming via stream_chat() async generator
    """

    def __init__(self, provider: str, model: str, api_key: Optional[str] = None):
        self.provider = provider
        self.model = model
        self.api_key = api_key
        self._client = self._build_client()

    # Per-request timeout and bounded transient retry (429/5xx/connection drops).
    # Without an explicit timeout a hung provider held the whole multi-call
    # pipeline until the client's default gave up; without a retry a single
    # transient 429 failed a query after all upstream work was already spent.
    REQUEST_TIMEOUT_SECONDS = float(os.getenv("AEGIS_LLM_TIMEOUT_SECONDS", "60"))
    TRANSIENT_RETRIES = int(os.getenv("AEGIS_LLM_RETRIES", "1"))

    def _build_client(self) -> AsyncOpenAI:
        cfg = LLM_PROVIDERS[self.provider]
        if self.provider == "anthropic":
            return AsyncOpenAI(
                api_key=self.api_key or "none",
                base_url=os.getenv("ANTHROPIC_BASE_URL", "https://api.anthropic.com/v1"),
                default_headers={"anthropic-version": "2023-06-01"},
                timeout=self.REQUEST_TIMEOUT_SECONDS,
                max_retries=self.TRANSIENT_RETRIES,
            )
        base_url = os.getenv(f"{self.provider.upper()}_BASE_URL") or cfg.get("base_url")
        return AsyncOpenAI(
            api_key=self.api_key or "none",
            base_url=base_url,
            timeout=self.REQUEST_TIMEOUT_SECONDS,
            max_retries=self.TRANSIENT_RETRIES,
        )


    async def _attempt(
        self,
        messages: List[Dict[str, str]],
        temperature: float,
        max_tokens: int,
    ) -> str:
        response = await self._client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        content = response.choices[0].message.content
        return (content or "").strip()


    async def chat(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.1,
        max_tokens: int = 1024,
    ) -> str:
        """
        Call LLM with automatic context-overflow retry.

        Tier 1: full call (original messages)
        Tier 2: last 2 turns + prompt truncated to 8 000 chars + max_tokens 512
        Tier 3: no history + prompt truncated to 3 000 chars + max_tokens 256
        """
        try:
            return await self._attempt(messages, temperature, max_tokens)
        except Exception as e1:
            err = str(e1).lower()
            if not any(k in err for k in ("context", "token", "length", "limit", "too large")):
                raise RuntimeError(f"LLM call failed ({self.provider}/{self.model}): {e1}")

            # Tier 2 — keep system + last 2 turns, truncate user content
            try:
                trimmed = _trim_messages(messages, max_user_chars=8_000, keep_turns=2)
                return await self._attempt(trimmed, temperature, min(max_tokens, 512))
            except Exception as e2:
                import logging
                logging.getLogger(__name__).warning(
                    f"LLM tier-2 retry failed ({self.provider}/{self.model}): {e2} — attempting tier-3"
                )

            # Tier 3 — system only + minimal user content
            try:
                minimal = _trim_messages(messages, max_user_chars=3_000, keep_turns=0)
                return await self._attempt(minimal, temperature, 256)
            except Exception as e3:
                raise RuntimeError(
                    f"LLM call failed after 3 retries ({self.provider}/{self.model}): {e3}"
                )


    async def stream_chat(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.1,
        max_tokens: int = 1024,
    ) -> AsyncIterator[str]:
        """Async generator that yields text tokens as they arrive."""
        stream = await self._client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            stream=True,
        )
        async for chunk in stream:
            delta = chunk.choices[0].delta.content
            if delta:
                yield delta


    async def chat_simple(self, prompt: str, system: str = "", temperature: float = 0.1) -> str:
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        return await self.chat(messages, temperature=temperature)

    async def stream_simple(
        self,
        prompt: str,
        system: str = "",
        temperature: float = 0.1,
    ) -> AsyncIterator[str]:
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        async for token in self.stream_chat(messages, temperature=temperature):
            yield token



def _trim_messages(
    messages: List[Dict[str, str]],
    max_user_chars: int,
    keep_turns: int,
) -> List[Dict[str, str]]:
    """
    Return a trimmed copy of messages:
    - Always keeps the system message (if any)
    - Keeps the last `keep_turns` non-system pairs (keep_turns=0 → last user only)
    - Truncates the last user message to max_user_chars
    """
    system = [m for m in messages if m["role"] == "system"]
    non_system = [m for m in messages if m["role"] != "system"]

    if keep_turns > 0:
        non_system = non_system[-(keep_turns * 2):]
    elif non_system:
        non_system = [non_system[-1]]  # last user message only

    # Truncate last user message
    trimmed = list(non_system)
    for i in range(len(trimmed) - 1, -1, -1):
        if trimmed[i]["role"] == "user":
            trimmed[i] = {**trimmed[i], "content": trimmed[i]["content"][:max_user_chars]}
            break

    return system + trimmed
