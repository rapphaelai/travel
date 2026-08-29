"""Clasamentul reclamelor dupa performanta, agregat pe `format_tag`
(eticheta de format din numele reclamei, ex: "ugc-talking-head-9x16",
"slideshow-poze-9x16") -- ca sa vedem ce TIP de video/format converteste
cel mai bine, nu doar care reclama individuala.

Folosit de campaign_builder.py pentru a decide automat ce format sa
recomande/reia la urmatoarea excursie.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .insights import AdPerformance, get_ad_performance


@dataclass
class FormatPerformance:
    format_tag: str
    ad_count: int
    total_spend: float
    total_impressions: int
    total_results: int
    avg_ctr: float
    avg_cost_per_result: float | None
    avg_hook_rate: float | None
    avg_hold_rate: float | None
    ads: list[AdPerformance] = field(repr=False, default_factory=list)


def rank_formats(date_preset: str = "last_30d") -> list[FormatPerformance]:
    """Grupeaza reclamele dupa format_tag si le ordoneaza descrescator dupa
    performanta (cost per rezultat mai mic = mai bun; daca lipsesc rezultate,
    cade pe hook_rate ca proxy de calitate a creativei)."""
    ads = get_ad_performance(date_preset=date_preset)

    by_format: dict[str, list[AdPerformance]] = {}
    for ad in ads:
        tag = ad.format_tag or "necunoscut"
        by_format.setdefault(tag, []).append(ad)

    ranked: list[FormatPerformance] = []
    for tag, group in by_format.items():
        total_spend = sum(a.spend for a in group)
        total_impressions = sum(a.impressions for a in group)
        total_results = sum(a.results for a in group)
        ctrs = [a.ctr for a in group if a.ctr]
        hook_rates = [a.hook_rate for a in group if a.hook_rate is not None]
        hold_rates = [a.hold_rate for a in group if a.hold_rate is not None]
        cost_per_result = (total_spend / total_results) if total_results else None

        ranked.append(FormatPerformance(
            format_tag=tag,
            ad_count=len(group),
            total_spend=total_spend,
            total_impressions=total_impressions,
            total_results=total_results,
            avg_ctr=(sum(ctrs) / len(ctrs)) if ctrs else 0.0,
            avg_cost_per_result=cost_per_result,
            avg_hook_rate=(sum(hook_rates) / len(hook_rates)) if hook_rates else None,
            avg_hold_rate=(sum(hold_rates) / len(hold_rates)) if hold_rates else None,
            ads=group,
        ))

    def sort_key(fp: FormatPerformance):
        # Prioritate: cost per rezultat mic (daca exista date), altfel hook rate mare.
        has_results = fp.avg_cost_per_result is not None
        return (
            0 if has_results else 1,
            fp.avg_cost_per_result if has_results else 0,
            -(fp.avg_hook_rate or 0),
        )

    ranked.sort(key=sort_key)
    return ranked


def best_ad_for_format(format_tag: str, date_preset: str = "last_30d") -> AdPerformance | None:
    """Cea mai buna reclama individuala dintr-un format dat -- folosita ca
    referinta (targeting/placements/buget) cand cream o campanie noua."""
    ads = [a for a in get_ad_performance(date_preset=date_preset) if a.format_tag == format_tag]
    if not ads:
        return None
    ads.sort(key=lambda a: (a.cost_per_result is None, a.cost_per_result or 0))
    return ads[0]
