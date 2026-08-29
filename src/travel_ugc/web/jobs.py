"""Joburile de generare video: pentru un prompt ales, porneste N variante
(implicit 4) in paralel prin ElevenLabs Flows (veo-3.1-fast, 8s, audio ON),
aplica banner-ul peste fiecare rezultat, si actualizeaza contextul salvat
pe masura ce fiecare varianta se termina (progres vizibil in dashboard).
"""
from __future__ import annotations

import threading
import traceback
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from ..trip import make_banner_trip
from ..video.compose import overlay_banner_on_video
from ..video.elevenlabs_flows import DEFAULT_VIDEO_MODEL, VideoGenerationError, generate_video
from . import storage

_executor = ThreadPoolExecutor(max_workers=8)
_lock = threading.Lock()


def _update_context(context_id: str, mutate) -> None:
    with _lock:
        ctx = storage.load_context(context_id)
        if ctx is None:
            return
        mutate(ctx)
        storage.save_context(ctx)


def _run_take(context_id: str, job_id: str, take_index: int, prompt: str, model_id: str,
              duration_secs: int, reference_image_asset_ids: list[str] | None) -> None:
    media_dir = storage.context_media_dir(context_id) / job_id
    media_dir.mkdir(parents=True, exist_ok=True)
    raw_path = media_dir / f"take_{take_index}_raw.mp4"
    final_path = media_dir / f"take_{take_index}_final.mp4"

    def set_take(patch: dict) -> None:
        def mutate(ctx):
            job = ctx["jobs"][job_id]
            job["takes"][take_index].update(patch)
        _update_context(context_id, mutate)

    try:
        set_take({"status": "generating"})
        generate_video(
            prompt=prompt,
            output_path=raw_path,
            model_id=model_id,
            duration_secs=duration_secs,
            reference_image_asset_ids=reference_image_asset_ids,
            on_status=lambda msg: set_take({"status_detail": msg}),
        )

        set_take({"status": "banner"})
        ctx = storage.load_context(context_id)
        banner_trip = make_banner_trip(
            id=f"{context_id}-{job_id}-{take_index}",
            hook_line=ctx["hook_line"],
            start_date=ctx["start_date"],
            end_date=ctx["end_date"],
            objectives_count=ctx["objectives_count"],
            price_line=ctx["price_line"],
            banner_template=ctx.get("banner_template", "config/banner_template.yaml"),
        )
        overlay_banner_on_video(banner_trip, raw_path, output_path=final_path, keep_base_audio=True)

        rel_url = f"/media/{context_id}/{job_id}/take_{take_index}_final.mp4"
        set_take({"status": "completed", "video_url": rel_url})
    except VideoGenerationError as exc:
        set_take({"status": "failed", "error": str(exc)})
    except Exception:  # noqa: BLE001 -- vrem sa capturam orice, sa nu blocheze celelalte takes
        set_take({"status": "failed", "error": traceback.format_exc(limit=3)})
    finally:
        def maybe_finish(ctx):
            job = ctx["jobs"][job_id]
            if all(t["status"] in ("completed", "failed") for t in job["takes"]):
                job["status"] = "done"
        _update_context(context_id, maybe_finish)


def start_generation_job(
    context_id: str,
    prompt: str,
    angle_id: str,
    take_count: int = 4,
    model_id: str = DEFAULT_VIDEO_MODEL,
    duration_secs: int = 8,
    reference_image_asset_ids: list[str] | None = None,
) -> str:
    job_id = storage.new_id()
    job = {
        "id": job_id,
        "angle_id": angle_id,
        "prompt": prompt,
        "model_id": model_id,
        "duration_secs": duration_secs,
        "status": "running",
        "created_at": storage.now_iso(),
        "takes": [
            {"index": i, "status": "pending", "video_url": None, "error": None, "status_detail": None}
            for i in range(take_count)
        ],
    }

    def mutate(ctx):
        ctx.setdefault("jobs", {})[job_id] = job

    _update_context(context_id, mutate)

    for i in range(take_count):
        _executor.submit(
            _run_take, context_id, job_id, i, prompt, model_id, duration_secs, reference_image_asset_ids
        )

    return job_id
