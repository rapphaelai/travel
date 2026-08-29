"""CLI pentru statistici si crearea campaniilor Meta Ads.

Rulare:
    # vezi clasamentul formatelor dupa performanta (ultimele 30 zile)
    python -m travel_ugc.meta_ads.cli stats --days 30

    # creeaza campania pentru o excursie, folosind videoclipul deja generat
    # (implicit PAUSED -- o activezi manual din Meta Ads Manager dupa ce verifici)
    python -m travel_ugc.meta_ads.cli create-campaign --trip config/trips/2026-07-25-excursie-manastiri.yaml
"""
from __future__ import annotations

import argparse
from pathlib import Path

from dotenv import load_dotenv

from ..trip import load_trip
from .campaign_builder import create_campaign_for_trip
from .client import MetaAdsError
from .performance import rank_formats

REPO_ROOT = Path(__file__).resolve().parents[3]
load_dotenv(REPO_ROOT / ".env")

DATE_PRESET_BY_DAYS = {7: "last_7d", 14: "last_14d", 30: "last_30d", 90: "last_90d"}


def _cmd_stats(args: argparse.Namespace) -> int:
    date_preset = DATE_PRESET_BY_DAYS.get(args.days, "last_30d")
    ranked = rank_formats(date_preset=date_preset)

    if not ranked:
        print("Nu exista date de performanta pentru perioada selectata.")
        return 0

    print(f"Clasament formate dupa performanta ({date_preset}):\n")
    header = f"{'Format':<28} {'#Ads':>5} {'Spend RON':>11} {'Rezultate':>10} {'Cost/rez':>10} {'Hook %':>8} {'Hold %':>8}"
    print(header)
    print("-" * len(header))
    for fp in ranked:
        cost = f"{fp.avg_cost_per_result:.1f}" if fp.avg_cost_per_result is not None else "-"
        hook = f"{fp.avg_hook_rate * 100:.1f}" if fp.avg_hook_rate is not None else "-"
        hold = f"{fp.avg_hold_rate * 100:.1f}" if fp.avg_hold_rate is not None else "-"
        print(f"{fp.format_tag:<28} {fp.ad_count:>5} {fp.total_spend:>11.2f} {fp.total_results:>10} {cost:>10} {hook:>8} {hold:>8}")

    print("\nRecomandare: formatul din primul rand a avut cel mai bun cost per rezultat")
    print("(sau hook rate, daca inca nu are rezultate) -- foloseste-l ca model pentru urmatoarele videoclipuri UGC.")
    return 0


def _cmd_create_campaign(args: argparse.Namespace) -> int:
    trip = load_trip(args.trip)
    video_path = args.video or (REPO_ROOT / trip.output_file)
    if not Path(video_path).exists():
        print(f"Videoclipul nu exista la {video_path}. Ruleaza intai pipeline-ul principal:")
        print(f"  python -m travel_ugc.pipeline --trip {args.trip}")
        return 1

    result = create_campaign_for_trip(trip, video_path, activate=args.activate)
    print("Campanie creata cu succes:")
    print(f"  campaign_id : {result.campaign_id}")
    print(f"  adset_id    : {result.adset_id}")
    print(f"  creative_id : {result.creative_id}")
    print(f"  ad_id       : {result.ad_id}")
    print(f"  video_id    : {result.video_id}")
    if result.based_on_ad_id:
        print(f"  targetare mostenita de la reclama: {result.based_on_ad_id} (cel mai bun cost/rezultat pe acest format)")
    status = "ACTIVA" if args.activate else "PAUSED (activeaz-o manual din Meta Ads Manager dupa verificare)"
    print(f"  status      : {status}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)

    stats_p = sub.add_parser("stats", help="Clasamentul formatelor de video dupa performanta")
    stats_p.add_argument("--days", type=int, default=30, choices=list(DATE_PRESET_BY_DAYS))
    stats_p.set_defaults(func=_cmd_stats)

    cc_p = sub.add_parser("create-campaign", help="Creeaza o campanie noua pentru o excursie")
    cc_p.add_argument("--trip", required=True, help="Calea catre fisierul YAML al excursiei")
    cc_p.add_argument("--video", help="Cale custom catre videoclip (implicit: output-ul din fisierul excursiei)")
    cc_p.add_argument("--activate", action="store_true", help="Porneste campania imediat (implicit ramane PAUSED)")
    cc_p.set_defaults(func=_cmd_create_campaign)

    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except MetaAdsError as exc:
        print(f"[EROARE Meta Ads] {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
