import sys
from pathlib import Path

import requests
import streamlit as st

ROOT = Path(__file__).resolve().parent.parent
sys.path.append(str(ROOT))
import config

TIMEOUT = 60


class ApiError(Exception):
    pass


def _headers():
    return {"x-api-key": config.API_KEY} if config.API_KEY else {}


@st.cache_data(ttl=60, show_spinner=False)
def get(path: str, params: tuple = ()):
    """GET from the CommerceIQ API. `params` is a tuple of (key, value) pairs so it can be cached."""
    try:
        r = requests.get(
            f"{config.API_URL}{path}",
            params=dict(params),
            headers=_headers(),
            timeout=TIMEOUT,
        )
        r.raise_for_status()
        return r.json()
    except requests.exceptions.ConnectionError:
        raise ApiError(f"Cannot reach the API at {config.API_URL}. Is uvicorn running?")
    except requests.exceptions.RequestException as e:
        raise ApiError(f"API request failed: {e}")


def health():
    """Uncached health check, so the sidebar status is always current."""
    try:
        r = requests.get(f"{config.API_URL}/health", headers=_headers(), timeout=5)
        r.raise_for_status()
        return r.json()
    except Exception:
        return None
