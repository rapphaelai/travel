"""Client subtire pentru Meta Marketing API (Graph API), fara SDK-ul oficial
`facebook-business` (evitam o dependinta grea si greu de tinut la zi).

Foloseste direct Graph API prin `requests`. Are nevoie de variabilele de
mediu:
    META_ACCESS_TOKEN   - token de sistem/user cu permisiuni ads_management, ads_read
    META_AD_ACCOUNT_ID  - id-ul contului de reclame, format "act_1234567890"

Cum obtii un token pe termen lung, pas cu pas: vezi README.md, sectiunea
"Conectarea contului Meta Ads".
"""
from __future__ import annotations

import os

import requests

GRAPH_API_VERSION = "v21.0"
GRAPH_API_BASE = f"https://graph.facebook.com/{GRAPH_API_VERSION}"


class MetaAdsError(RuntimeError):
    pass


def _access_token() -> str:
    token = os.environ.get("META_ACCESS_TOKEN")
    if not token:
        raise MetaAdsError(
            "Lipseste META_ACCESS_TOKEN. Seteaza-l ca variabila de mediu sau in .env "
            "(vezi README.md -> 'Conectarea contului Meta Ads')."
        )
    return token


def _ad_account_id() -> str:
    account_id = os.environ.get("META_AD_ACCOUNT_ID")
    if not account_id:
        raise MetaAdsError("Lipseste META_AD_ACCOUNT_ID (format 'act_1234567890').")
    if not account_id.startswith("act_"):
        account_id = f"act_{account_id}"
    return account_id


def graph_get(path: str, params: dict | None = None) -> dict:
    params = dict(params or {})
    params["access_token"] = _access_token()
    resp = requests.get(f"{GRAPH_API_BASE}/{path}", params=params, timeout=60)
    _raise_for_graph_error(resp)
    return resp.json()


def graph_post(path: str, data: dict) -> dict:
    data = dict(data)
    data["access_token"] = _access_token()
    resp = requests.post(f"{GRAPH_API_BASE}/{path}", data=data, timeout=60)
    _raise_for_graph_error(resp)
    return resp.json()


def _raise_for_graph_error(resp: requests.Response) -> None:
    if resp.status_code >= 400:
        try:
            err = resp.json().get("error", {})
            message = err.get("message", resp.text)
        except ValueError:
            message = resp.text
        raise MetaAdsError(f"Meta Graph API a raspuns cu eroare {resp.status_code}: {message}")


def ad_account_path(suffix: str = "") -> str:
    account_id = _ad_account_id()
    return f"{account_id}/{suffix}" if suffix else account_id
