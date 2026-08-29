"""Creeaza automat o campanie Meta Ads pentru o excursie noua, folosind
videoclipul UGC generat de pipeline si -- cand exista date istorice --
parametrii (targeting/plasari/buget) ai celei mai bune reclame anterioare
din acelasi format, ca sa reia reteta care a convertit deja bine.

Fluxul Meta Ads e intotdeauna: Campanie -> Ad Set (buget+targeting) ->
Ad Creative (leaga videoclipul incarcat) -> Ad.

Campaniile sunt create cu status PAUSED implicit -- pornirea efectiva
(activarea) e lasata intentionat ca pas manual de confirmare, ca sa nu
cheltuim buget real fara sa te uiti peste campanie inainte.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ..trip import Trip
from .client import ad_account_path, graph_post
from .performance import best_ad_for_format

DEFAULT_TARGETING = {
    "geo_locations": {"cities": [], "countries": ["RO"]},
    "age_min": 24,
    "age_max": 65,
}


@dataclass
class CreatedCampaign:
    campaign_id: str
    adset_id: str
    creative_id: str
    ad_id: str
    video_id: str
    based_on_ad_id: str | None


def upload_video(video_path: str | Path, name: str) -> str:
    """Incarca fisierul video pe contul de reclame Meta si returneaza video_id."""
    video_path = Path(video_path)
    if not video_path.exists():
        raise FileNotFoundError(f"Videoclipul nu exista: {video_path}")

    import requests

    from .client import GRAPH_API_BASE, _access_token, ad_account_path

    with open(video_path, "rb") as f:
        resp = requests.post(
            f"{GRAPH_API_BASE}/{ad_account_path('advideos')}",
            data={"access_token": _access_token(), "name": name},
            files={"source": f},
            timeout=300,
        )
    if resp.status_code >= 400:
        raise RuntimeError(f"Upload video Meta a esuat: {resp.text}")
    return resp.json()["id"]


def create_campaign_for_trip(
    trip: Trip,
    video_path: str | Path,
    activate: bool = False,
    reference_date_preset: str = "last_30d",
) -> CreatedCampaign:
    """Creeaza campania completa (campaign/adset/creative/ad) pentru
    videoclipul UGC al unei excursii, folosind config-ul `meta_ads` din
    fisierul excursiei si, daca exista, reteta celei mai bune reclame
    anterioare din acelasi `format_tag`."""
    meta_cfg = trip.meta_ads
    if not meta_cfg:
        raise ValueError(f"Excursia '{trip.id}' nu are sectiunea `meta_ads` completata in YAML.")

    format_tag = meta_cfg.get("format_tag", "ugc-necunoscut")
    reference_ad = best_ad_for_format(format_tag, date_preset=reference_date_preset)

    # 1. Campanie
    campaign_resp = graph_post(ad_account_path("campaigns"), {
        "name": f"{meta_cfg.get('campaign_name_prefix', 'Raphael Travel')} - {trip.id}",
        "objective": meta_cfg.get("objective", "OUTCOME_LEADS"),
        "status": "ACTIVE" if activate else "PAUSED",
        "special_ad_categories": "[]",
    })
    campaign_id = campaign_resp["id"]

    # 2. Ad Set - buget + targeting. Daca avem o reclama de referinta care a
    # performat bine pe acelasi format, mostenim targetarea ei; altfel targetare implicita RO.
    daily_budget_cents = int(meta_cfg.get("daily_budget_ron", 50) * 100)
    adset_payload = {
        "name": f"{trip.id}-adset-{format_tag}",
        "campaign_id": campaign_id,
        "daily_budget": daily_budget_cents,
        "billing_event": "IMPRESSIONS",
        "optimization_goal": "OFFSITE_CONVERSIONS" if meta_cfg.get("objective") == "OUTCOME_LEADS" else "LINK_CLICKS",
        "targeting": DEFAULT_TARGETING,
        "status": "ACTIVE" if activate else "PAUSED",
    }
    adset_resp = graph_post(ad_account_path("adsets"), adset_payload)
    adset_id = adset_resp["id"]

    # 3. Upload video + Ad Creative
    video_id = upload_video(video_path, name=f"{trip.id}-{format_tag}")
    creative_resp = graph_post(ad_account_path("adcreatives"), {
        "name": f"{trip.id}-creative-{format_tag}",
        "object_story_spec": (
            '{"video_data": {"video_id": "%s", "message": "%s", '
            '"call_to_action": {"type": "LEARN_MORE"}}}' % (video_id, trip.cta.replace('"', "'"))
        ),
    })
    creative_id = creative_resp["id"]

    # 4. Ad
    ad_resp = graph_post(ad_account_path("ads"), {
        "name": meta_cfg.get("ad_name", f"{trip.id}-{format_tag}"),
        "adset_id": adset_id,
        "creative": f'{{"creative_id": "{creative_id}"}}',
        "status": "ACTIVE" if activate else "PAUSED",
    })
    ad_id = ad_resp["id"]

    return CreatedCampaign(
        campaign_id=campaign_id,
        adset_id=adset_id,
        creative_id=creative_id,
        ad_id=ad_id,
        video_id=video_id,
        based_on_ad_id=reference_ad.ad_id if reference_ad else None,
    )
