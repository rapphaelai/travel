"""Extrage statisticile relevante de pe campaniile Meta Ads ale Raphael
Travel, la nivel de reclama individuala (ad), ca sa putem compara direct
performanta intre videoclipuri/formate.

Metricile alese sunt cele relevante pentru conversie pe reclame video UGC:
  - spend, impressions, reach, ctr, cpc, cpm
  - cost per rezultat (lead/mesaj/achizitie, in functie de obiectiv)
  - metrici de retentie video: video_p25/p50/p75/p95, thruplay
    (thumb-stop rate si hook rate se calculeaza din ele)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .client import ad_account_path, graph_get

AD_INSIGHT_FIELDS = [
    "ad_id",
    "ad_name",
    "campaign_name",
    "adset_name",
    "spend",
    "impressions",
    "reach",
    "clicks",
    "ctr",
    "cpc",
    "cpm",
    "actions",
    "cost_per_action_type",
    "video_play_actions",
    "video_p25_watched_actions",
    "video_p50_watched_actions",
    "video_p75_watched_actions",
    "video_p95_watched_actions",
    "video_thruplay_watched_actions",
]


@dataclass
class AdPerformance:
    ad_id: str
    ad_name: str
    campaign_name: str
    adset_name: str
    spend: float
    impressions: int
    reach: int
    clicks: int
    ctr: float
    cpc: float
    cpm: float
    results: int
    cost_per_result: float | None
    hook_rate: float | None       # % din impresii care au vazut >25% din video
    hold_rate: float | None       # % din impresii care au vazut >75% din video
    thruplay_rate: float | None
    raw: dict[str, Any] = field(repr=False, default_factory=dict)

    @property
    def format_tag(self) -> str | None:
        """Incearca sa extraga eticheta de format din numele reclamei, daca
        respecta conventia `<trip-id>-<format-tag>` folosita de pipeline
        (vezi meta_ads.campaign_name_prefix / ad_name din fisierul excursiei)."""
        parts = self.ad_name.rsplit("-", 1)
        return parts[-1] if len(parts) > 1 else None


def _extract_action_value(actions: list[dict] | None, action_type_prefixes: tuple[str, ...]) -> int:
    if not actions:
        return 0
    total = 0
    for action in actions:
        if action.get("action_type", "").startswith(action_type_prefixes):
            total += int(float(action.get("value", 0)))
    return total


def _extract_cost_per_result(cost_per_action_type: list[dict] | None, action_type_prefixes: tuple[str, ...]) -> float | None:
    if not cost_per_action_type:
        return None
    for entry in cost_per_action_type:
        if entry.get("action_type", "").startswith(action_type_prefixes):
            return float(entry.get("value", 0))
    return None


# Actiunile care conteaza drept "rezultat" -- ajusteaza in functie de
# obiectivul campaniei (leads, mesaje, achizitii).
RESULT_ACTION_PREFIXES = ("lead", "onsite_conversion.lead", "offsite_conversion.fb_pixel_lead", "onsite_conversion.messaging_conversation_started_7d")


def _parse_ad_insight(entry: dict) -> AdPerformance:
    impressions = int(entry.get("impressions", 0))
    video_plays = _extract_action_value(entry.get("video_play_actions"), ("video_view",))
    p25 = _extract_action_value(entry.get("video_p25_watched_actions"), ("video_view",))
    p75 = _extract_action_value(entry.get("video_p75_watched_actions"), ("video_view",))
    thruplay = _extract_action_value(entry.get("video_thruplay_watched_actions"), ("video_view",))
    results = _extract_action_value(entry.get("actions"), RESULT_ACTION_PREFIXES)
    cost_per_result = _extract_cost_per_result(entry.get("cost_per_action_type"), RESULT_ACTION_PREFIXES)

    return AdPerformance(
        ad_id=entry.get("ad_id", ""),
        ad_name=entry.get("ad_name", ""),
        campaign_name=entry.get("campaign_name", ""),
        adset_name=entry.get("adset_name", ""),
        spend=float(entry.get("spend", 0)),
        impressions=impressions,
        reach=int(entry.get("reach", 0)),
        clicks=int(entry.get("clicks", 0)),
        ctr=float(entry.get("ctr", 0)),
        cpc=float(entry.get("cpc", 0)) if entry.get("cpc") else 0.0,
        cpm=float(entry.get("cpm", 0)) if entry.get("cpm") else 0.0,
        results=results,
        cost_per_result=cost_per_result,
        hook_rate=(p25 / impressions) if impressions else None,
        hold_rate=(p75 / impressions) if impressions else None,
        thruplay_rate=(thruplay / video_plays) if video_plays else None,
        raw=entry,
    )


def get_ad_performance(date_preset: str = "last_30d", limit: int = 200) -> list[AdPerformance]:
    """Statistici per reclama individuala, pentru ultima perioada `date_preset`
    (valori valide Meta: today, yesterday, last_7d, last_14d, last_30d,
    last_90d, this_month, last_month, ...).
    """
    data = graph_get(
        ad_account_path("insights"),
        params={
            "level": "ad",
            "date_preset": date_preset,
            "fields": ",".join(AD_INSIGHT_FIELDS),
            "limit": limit,
        },
    )
    return [_parse_ad_insight(entry) for entry in data.get("data", [])]
