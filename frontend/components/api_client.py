import os

import httpx

BACKEND_URL = os.getenv("BACKEND_URL", "http://127.0.0.1:8000")
DEFAULT_TIMEOUT = float(os.getenv("COMPOSE_HTTP_TIMEOUT", "600"))


def get_json(path: str) -> dict | list:
    response = httpx.get(f"{BACKEND_URL}{path}", timeout=30.0)
    response.raise_for_status()
    return response.json()


def post_json(path: str, payload: dict) -> dict:
    response = httpx.post(f"{BACKEND_URL}{path}", json=payload, timeout=DEFAULT_TIMEOUT)
    response.raise_for_status()
    return response.json()


def patch_json(path: str, payload: dict) -> dict:
    response = httpx.patch(f"{BACKEND_URL}{path}", json=payload, timeout=30.0)
    response.raise_for_status()
    return response.json()
