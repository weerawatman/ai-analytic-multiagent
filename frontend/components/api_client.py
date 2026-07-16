import os

import httpx

BACKEND_URL = os.getenv("BACKEND_URL", "http://127.0.0.1:8000")
DEFAULT_TIMEOUT = float(os.getenv("COMPOSE_HTTP_TIMEOUT", "600"))
# Collaborative chat (DE→DA→DS→BA) on LAN Ollama often exceeds 10 minutes
CHAT_TIMEOUT = float(os.getenv("CHAT_HTTP_TIMEOUT", "3600"))
ONBOARDING_TIMEOUT = float(os.getenv("ONBOARDING_HTTP_TIMEOUT", "3600"))


def get_json(path: str, timeout: float = 30.0) -> dict | list:
    response = httpx.get(f"{BACKEND_URL}{path}", timeout=timeout)
    response.raise_for_status()
    return response.json()


def get_json_allow_error(path: str, timeout: float = 30.0) -> dict | list:
    """GET that returns JSON body even on 4xx/5xx (e.g. Fabric health 503)."""
    response = httpx.get(f"{BACKEND_URL}{path}", timeout=timeout)
    try:
        data = response.json()
    except Exception:
        response.raise_for_status()
        raise
    if response.is_success:
        return data
    if isinstance(data, dict) and "detail" in data:
        detail = data["detail"]
        if isinstance(detail, dict):
            return detail
    response.raise_for_status()
    return data


def post_json(path: str, payload: dict, *, timeout: float | None = None) -> dict:
    response = httpx.post(
        f"{BACKEND_URL}{path}",
        json=payload,
        timeout=timeout if timeout is not None else DEFAULT_TIMEOUT,
    )
    response.raise_for_status()
    return response.json()


def patch_json(path: str, payload: dict, timeout: float = 30.0) -> dict:
    response = httpx.patch(f"{BACKEND_URL}{path}", json=payload, timeout=timeout)
    response.raise_for_status()
    return response.json()


# ──── Job-based endpoints (submit fast, then poll /api/v1/jobs/{id}) ────


def submit_chat_job(payload: dict, timeout: float = 30.0) -> dict:
    """POST /chat/ now returns 202 + job_id immediately."""
    return post_json("/api/v1/chat/", payload, timeout=timeout)


def submit_onboarding_job(theme_id: str, theme_name: str = "", timeout: float = 30.0) -> dict:
    response = httpx.post(
        f"{BACKEND_URL}/api/v1/onboarding/{theme_id}/run",
        params={"theme_name": theme_name},
        timeout=timeout,
    )
    response.raise_for_status()
    return response.json()


def get_job(job_id: str, timeout: float = 30.0) -> dict:
    return get_json(f"/api/v1/jobs/{job_id}", timeout=timeout)


def find_active_job(thread_id: str, kind: str = "chat", timeout: float = 30.0) -> dict | None:
    response = httpx.get(
        f"{BACKEND_URL}/api/v1/jobs/",
        params={"thread_id": thread_id, "kind": kind, "active": "true", "limit": 1},
        timeout=timeout,
    )
    response.raise_for_status()
    jobs = response.json()
    return jobs[0] if jobs else None


def get_consultant_status(timeout: float = 15.0) -> dict:
    return get_json("/api/v1/consultant/status", timeout=timeout)


def submit_consult_job(theme_id: str, question: str, timeout: float = 30.0) -> dict:
    return post_json(
        f"/api/v1/consultant/{theme_id}/consult",
        {"question": question},
        timeout=timeout,
    )
