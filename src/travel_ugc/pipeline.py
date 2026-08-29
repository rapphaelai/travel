"""Punctul de intrare al automatizarii: dai un fisier de excursie, primesti
videoclipul UGC final cu banner text si voiceover suprapuse.

Rulare:
    python -m travel_ugc.pipeline --trip config/trips/2026-07-25-excursie-manastiri.yaml

Optiuni utile:
    --no-voice        genereaza doar footage + banner, fara ElevenLabs
                       (nu necesita ELEVENLABS_API_KEY, bun pentru preview rapid)
    --banner-only      genereaza doar imaginea de banner (PNG), fara video
    --print-script      afiseaza doar scriptul de naratiune generat, fara sa produca fisiere
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .script_builder import build_caption, build_narration_script
from .trip import load_trip
from .video.banner import save_banner
from .video.compose import compose_video
from .voice.elevenlabs_client import ElevenLabsError, text_to_speech

REPO_ROOT = Path(__file__).resolve().parents[2]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--trip", required=True, help="Calea catre fisierul YAML al excursiei")
    parser.add_argument("--no-voice", action="store_true", help="Sari peste generarea voiceover-ului ElevenLabs")
    parser.add_argument("--banner-only", action="store_true", help="Genereaza doar banner-ul PNG, fara video")
    parser.add_argument("--print-script", action="store_true", help="Afiseaza doar scriptul de naratiune si iese")
    args = parser.parse_args(argv)

    trip = load_trip(args.trip)
    script = build_narration_script(trip)

    if args.print_script:
        print("--- Script naratiune (pentru ElevenLabs) ---")
        print(script)
        print("\n--- Caption sugerat pentru postare ---")
        print(build_caption(trip))
        return 0

    if args.banner_only:
        out = save_banner(trip, REPO_ROOT / "assets" / "output" / f"{trip.id}-banner.png")
        print(f"Banner salvat la: {out}")
        return 0

    voiceover_path = None
    if not args.no_voice:
        voice_cfg = trip.voice
        try:
            voiceover_path = text_to_speech(
                text=script,
                voice_id=voice_cfg["voice_id"],
                output_path=REPO_ROOT / "assets" / "output" / f"{trip.id}-voiceover.mp3",
                model_id=voice_cfg.get("model_id", "eleven_multilingual_v2"),
            )
            print(f"Voiceover generat la: {voiceover_path}")
        except ElevenLabsError as exc:
            print(f"[ATENTIE] Nu am putut genera voiceover ElevenLabs: {exc}", file=sys.stderr)
            print("Continui fara sunet vorbit (foloseste --no-voice ca sa opresti acest mesaj).", file=sys.stderr)

    output_path = compose_video(trip, voiceover_path=voiceover_path)
    print(f"Videoclip UGC final: {output_path}")
    print("\nCaption sugerat pentru postare:")
    print(build_caption(trip))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
