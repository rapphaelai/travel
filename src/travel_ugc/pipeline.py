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

from .script_builder import build_caption, build_narration_script, build_video_prompt
from .trip import load_trip
from .video.banner import save_banner
from .video.compose import compose_video, overlay_banner_on_video
from .video.elevenlabs_flows import DEFAULT_VIDEO_MODEL, VideoGenerationError, generate_video
from .voice.elevenlabs_client import ElevenLabsError, text_to_speech

REPO_ROOT = Path(__file__).resolve().parents[2]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--trip", required=True, help="Calea catre fisierul YAML al excursiei")
    parser.add_argument("--no-voice", action="store_true", help="Sari peste generarea voiceover-ului ElevenLabs")
    parser.add_argument("--banner-only", action="store_true", help="Genereaza doar banner-ul PNG, fara video")
    parser.add_argument("--print-script", action="store_true", help="Afiseaza doar scriptul de naratiune si iese")
    parser.add_argument(
        "--ai-video", action="store_true",
        help="Genereaza tot video-ul (scena+voce) printr-un model AI ElevenLabs Flows "
             "(implicit veo-3.1-generate-001, max 8s), in loc sa asamblezi footage propriu + TTS separat.",
    )
    parser.add_argument("--ai-video-model", default=DEFAULT_VIDEO_MODEL, help="model_id pentru --ai-video")
    parser.add_argument("--ai-video-duration", type=int, default=8, help="Durata in secunde pentru --ai-video (max 8 pentru modelele Veo)")
    args = parser.parse_args(argv)

    trip = load_trip(args.trip)
    script = build_narration_script(trip)

    if args.print_script:
        print("--- Script naratiune (pentru ElevenLabs) ---")
        print(script)
        print("\n--- Prompt video AI (pentru --ai-video) ---")
        print(build_video_prompt(trip))
        print("\n--- Caption sugerat pentru postare ---")
        print(build_caption(trip))
        return 0

    if args.banner_only:
        out = save_banner(trip, REPO_ROOT / "assets" / "output" / f"{trip.id}-banner.png")
        print(f"Banner salvat la: {out}")
        return 0

    if args.ai_video:
        prompt = build_video_prompt(trip)

        def log(msg: str) -> None:
            print(f"[ai-video] {msg}")

        raw_path = REPO_ROOT / "assets" / "output" / f"{trip.id}-ai-raw.mp4"
        try:
            generate_video(
                prompt=prompt,
                output_path=raw_path,
                model_id=args.ai_video_model,
                duration_secs=args.ai_video_duration,
                on_status=log,
            )
        except VideoGenerationError as exc:
            print(f"[EROARE] Generarea video AI a esuat: {exc}", file=sys.stderr)
            return 1

        output_path = overlay_banner_on_video(trip, raw_path, keep_base_audio=True)
        print(f"Videoclip UGC final (AI): {output_path}")
        print("\nCaption sugerat pentru postare:")
        print(build_caption(trip))
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
