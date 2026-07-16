import os

import httpx

BACKEND_URL = os.getenv("BACKEND_URL", "http://127.0.0.1:8000")
DEFAULT_TIMEOUT = float(os.getenv("COMPOSE_HTTP_TIMEOUT", "600"))


def get_json(path: str) -> dict | list:
    response = httpx.get(f"{BACKEND_URL}{path}", timeout=30.0)
    response.raise_for_status()
    return response.json()


def get_json_allow_error(path: str) -> dict | list:
    """GET that returns JSON body even on 4xx/5xx (e.g. Fabric health 503)."""
    response = httpx.get(f"{BACKEND_URL}{path}", timeout=30.0)
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


def post_json(path: str, payload: dict) -> dict:
    response = httpx.post(f"{BACKEND_URL}{path}", json=payload, timeout=DEFAULT_TIMEOUT)
    response.raise_for_status()
    return response.json()


def patch_json(path: str, payload: dict) -> dict:
    response = httpx.patch(f"{BACKEND_URL}{path}", json=payload, timeout=30.0)
    response.raise_for_status()
    return response.json()
