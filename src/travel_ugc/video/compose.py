"""Asambleaza videoclipul final cu ffmpeg: footage (video sau slideshow din
poze) + banner text suprapus + voiceover audio.

Nu depinde de moviepy/alte librarii grele -- construieste direct comenzi
ffmpeg, ceea ce e mai usor de rulat pe orice masina/CI cu ffmpeg instalat.
"""
from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path

from ..trip import Trip
from .banner import save_banner

REPO_ROOT = Path(__file__).resolve().parents[3]


class ComposeError(RuntimeError):
    pass


def _require_ffmpeg() -> str:
    ffmpeg_bin = shutil.which("ffmpeg")
    if not ffmpeg_bin:
        raise ComposeError(
            "ffmpeg nu este instalat/gasit in PATH. Instaleaza-l (ex: `apt-get install ffmpeg`) "
            "inainte de a rula pipeline-ul."
        )
    return ffmpeg_bin


def _build_footage_video(trip: Trip, work_dir: Path, canvas_w: int, canvas_h: int) -> Path:
    """Returneaza calea unui clip video (fara audio necesar) reprezentand
    footage-ul brut al excursiei, adus la formatul 9:16 al canvasului."""
    ffmpeg_bin = _require_ffmpeg()
    footage_cfg = trip.footage

    source_video = footage_cfg.get("source_video")
    if source_video:
        source_path = REPO_ROOT / source_video if not Path(source_video).is_absolute() else Path(source_video)
        if not source_path.exists():
            raise ComposeError(f"Fisierul video sursa nu exista: {source_path}")
        out_path = work_dir / "footage_normalized.mp4"
        cmd = [
            ffmpeg_bin, "-y", "-i", str(source_path),
            "-vf", f"scale={canvas_w}:{canvas_h}:force_original_aspect_ratio=increase,"
                   f"crop={canvas_w}:{canvas_h}",
            "-an", "-r", "30",
            str(out_path),
        ]
        subprocess.run(cmd, check=True, capture_output=True)
        return out_path

    images = footage_cfg.get("source_images") or []
    if not images:
        raise ComposeError(
            "Excursia nu are nici `footage.source_video`, nici `footage.source_images` setate."
        )
    duration = footage_cfg.get("image_duration_seconds", 4)

    clips = []
    for idx, img_rel in enumerate(images):
        img_path = REPO_ROOT / img_rel if not Path(img_rel).is_absolute() else Path(img_rel)
        if not img_path.exists():
            raise ComposeError(f"Poza din footage.source_images nu exista: {img_path}")
        clip_out = work_dir / f"slide_{idx:03d}.mp4"
        # Ken Burns simplu (zoom lent) pentru dinamism, fara librarii externe.
        cmd = [
            ffmpeg_bin, "-y", "-loop", "1", "-i", str(img_path),
            "-t", str(duration),
            "-vf",
            f"scale={canvas_w * 2}:{canvas_h * 2}:force_original_aspect_ratio=increase,"
            f"crop={canvas_w * 2}:{canvas_h * 2},"
            f"zoompan=z='min(zoom+0.0015,1.15)':d={duration * 30}:s={canvas_w}x{canvas_h}:fps=30",
            "-c:v", "libx264", "-pix_fmt", "yuv420p",
            str(clip_out),
        ]
        subprocess.run(cmd, check=True, capture_output=True)
        clips.append(clip_out)

    concat_list = work_dir / "concat.txt"
    concat_list.write_text("\n".join(f"file '{c.name}'" for c in clips), encoding="utf-8")
    out_path = work_dir / "footage_normalized.mp4"
    cmd = [
        ffmpeg_bin, "-y", "-f", "concat", "-safe", "0", "-i", str(concat_list),
        "-c", "copy", str(out_path),
    ]
    subprocess.run(cmd, check=True, capture_output=True, cwd=work_dir)
    return out_path


def overlay_banner_on_video(
    trip: Trip,
    base_video_path: str | Path,
    output_path: str | Path | None = None,
    voiceover_path: str | Path | None = None,
    keep_base_audio: bool = True,
) -> Path:
    """Suprapune banner-ul text peste un videoclip deja existent (de exemplu
    unul generat de un model AI, cu audio propriu inclus).

    Daca `voiceover_path` e dat, inlocuieste audio-ul din `base_video_path`
    (folosit pentru fluxul cu voce ElevenLabs separata). Altfel, daca
    `keep_base_audio` e True (implicit), pastreaza audio-ul din video-ul
    de baza (folosit cand audio-ul e generat deja odata cu video-ul de AI).
    """
    ffmpeg_bin = _require_ffmpeg()
    base_video_path = Path(base_video_path)
    if not base_video_path.exists():
        raise ComposeError(f"Videoclipul de baza nu exista: {base_video_path}")

    output_path = Path(output_path) if output_path else (
        REPO_ROOT / trip.output_file if not Path(trip.output_file).is_absolute() else Path(trip.output_file)
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="travel_ugc_") as tmp:
        work_dir = Path(tmp)
        banner_path = save_banner(trip, work_dir / "banner.png")

        inputs = ["-i", str(base_video_path), "-i", str(banner_path)]
        filter_complex = "[0:v][1:v]overlay=0:0:format=auto[outv]"
        map_args = ["-map", "[outv]"]

        if voiceover_path:
            voiceover_path = Path(voiceover_path)
            if not voiceover_path.exists():
                raise ComposeError(f"Fisierul de voiceover nu exista: {voiceover_path}")
            inputs += ["-i", str(voiceover_path)]
            map_args += ["-map", "2:a"]
        elif keep_base_audio:
            map_args += ["-map", "0:a?"]

        cmd = [
            ffmpeg_bin, "-y",
            *inputs,
            "-filter_complex", filter_complex,
            *map_args,
            "-c:v", "libx264", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "192k",
            "-shortest",
            str(output_path),
        ]
        result = subprocess.run(cmd, capture_output=True)
        if result.returncode != 0:
            raise ComposeError(f"ffmpeg a esuat la suprapunerea banner-ului:\n{result.stderr.decode(errors='ignore')}")

    return output_path


def compose_video(trip: Trip, voiceover_path: str | Path | None = None) -> Path:
    """Genereaza videoclipul final: footage (din poze/video puse de tine)
    + banner + (optional) voiceover.

    Daca `voiceover_path` e None, videoclipul e generat fara sunet vorbit
    (util pentru preview rapid sau cand ElevenLabs inca nu e configurat).
    """
    from .banner import _load_template  # reutilizam parsarea template-ului
    template = _load_template(trip.banner_template)
    canvas_w = template["canvas"]["width"]
    canvas_h = template["canvas"]["height"]

    with tempfile.TemporaryDirectory(prefix="travel_ugc_footage_") as tmp:
        work_dir = Path(tmp)
        footage_path = _build_footage_video(trip, work_dir, canvas_w, canvas_h)
        return overlay_banner_on_video(trip, footage_path, voiceover_path=voiceover_path, keep_base_audio=False)
