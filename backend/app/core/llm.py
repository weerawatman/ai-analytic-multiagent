"""Single construction point for chat LLMs.

Phase D will extend this into get_llm(role) with external providers
(Claude API) behind a data-policy redaction layer — keep all model
instantiation going through here.
"""

from __future__ import annotations

from langchain_ollama import ChatOllama, OllamaEmbeddings

from backend.app.core.config import get_settings


def make_chat_ollama(*, model: str | None = None, temperature: float = 0.0) -> ChatOllama:
    settings = get_settings()
    # ChatOllama has no top-level `timeout` field (extra="ignore" silently drops
    # it) — the request timeout must go through the httpx client kwargs.
    timeout_kwargs = {"timeout": settings.ollama_timeout}
    return ChatOllama(
        base_url=settings.ollama_base_url,
        model=model or settings.ollama_model,
        temperature=temperature,
        num_ctx=settings.ollama_num_ctx,
        num_predict=settings.ollama_num_predict,
        keep_alive=settings.ollama_keep_alive,
        client_kwargs=timeout_kwargs,
        async_client_kwargs=timeout_kwargs,
    )


def make_embed_ollama(*, model: str | None = None) -> OllamaEmbeddings:
    """Phase J — embedding client for semantic retrieval (nomic-embed-text by default).

    Same timeout gotcha as make_chat_ollama: the request timeout must go
    through client_kwargs/async_client_kwargs, not a top-level field.
    """
    settings = get_settings()
    timeout_kwargs = {"timeout": settings.ollama_timeout}
    return OllamaEmbeddings(
        base_url=settings.ollama_base_url,
        model=model or settings.ollama_embed_model,
        client_kwargs=timeout_kwargs,
        async_client_kwargs=timeout_kwargs,
    )
