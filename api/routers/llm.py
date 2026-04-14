"""
LLM provider endpoints.

GET /api/v1/llm/models — returns available models for a given provider.
No authentication required (called from settings screen before login).
"""
import logging
from typing import Optional

import httpx
from fastapi import APIRouter, Query

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/llm", tags=["llm"])


@router.get("/models")
async def list_models(
    provider: str = Query(..., description="openrouter or ollama"),
    api_key: Optional[str] = Query(None, description="API key (required for openrouter)"),
):
    """
    Returns available models for the given provider.

    - openrouter: fetches https://openrouter.ai/api/v1/models and returns free models
      (pricing.prompt == "0"). Requires api_key.
    - ollama: fetches http://localhost:11434/api/tags and returns installed models.
      Returns empty list with a message if Ollama is not running.

    Returns: {"models": [{"id": "...", "name": "..."}]}
    """
    if provider == "openrouter":
        return await _fetch_openrouter_models(api_key or "")
    elif provider == "ollama":
        return await _fetch_ollama_models()
    else:
        return {"models": [], "message": f"Unknown provider: {provider}"}


async def _fetch_openrouter_models(api_key: str) -> dict:
    headers = {"User-Agent": "RAPID/1.0"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                "https://openrouter.ai/api/v1/models",
                headers=headers,
            )
            resp.raise_for_status()
            data = resp.json()
    except httpx.HTTPStatusError as e:
        logger.warning(f"OpenRouter API error {e.response.status_code}: {e}")
        return {"models": [], "message": f"OpenRouter API error: {e.response.status_code}"}
    except Exception as e:
        logger.warning(f"Failed to fetch OpenRouter models: {e}")
        return {"models": [], "message": f"Could not reach OpenRouter: {e}"}

    models = []
    for m in data.get("data", []):
        pricing = m.get("pricing", {})
        # Only return free models (pricing.prompt == "0")
        prompt_price = str(pricing.get("prompt", "1"))
        if prompt_price == "0":
            model_id = m.get("id", "")
            name = m.get("name") or model_id
            if model_id:
                models.append({"id": model_id, "name": name})

    # Sort alphabetically by id
    models.sort(key=lambda x: x["id"])
    return {"models": models}


async def _fetch_ollama_models() -> dict:
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get("http://localhost:11434/api/tags")
            resp.raise_for_status()
            data = resp.json()
    except Exception as e:
        logger.info(f"Ollama not available: {e}")
        return {"models": [], "message": "Ollama is not running or not reachable"}

    models = []
    for m in data.get("models", []):
        model_name = m.get("name", "")
        if model_name:
            models.append({"id": model_name, "name": model_name})

    return {"models": models}
