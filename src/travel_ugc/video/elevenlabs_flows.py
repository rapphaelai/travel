"""Client pentru ElevenLabs Flows -- generarea video propriu-zisa (nu doar
voce). Foloseste endpoint-ul real /v1/flows/video (verificat direct din
specificatia OpenAPI live a ElevenLabs), care genereaza video + audio
impreuna dintr-un singur prompt text, fara pas separat de TTS.

Modelul implicit e `bytedance-seedance-v2.5`: singurul model video din
Flows care accepta prompt text + genereaza audio + suporta pana la 30
secunde durata si aspect ratio 9:16 (potrivit pentru Reels/TikTok/Stories).
`gemini-omni-flash`, mentionat in materialele de marketing ElevenLabs, NU
e (inca) un model_id valid in acest endpoint public -- verificat din spec.

Flux: POST /v1/flows/video (creeaza generarea, status "pending")
      -> polling GET /v1/flows/video/{id} pana la status "completed"/"failed"
      -> download de la `content_url` (semnat, expira ~1h).
"""
from __future__ import annotations

import time
from pathlib import Path

import requests

from ..voice.elevenlabs_client import API_BASE, ElevenLabsError, _api_key

DEFAULT_VIDEO_MODEL = "veo-3.1-fast-generate-001"


class VideoGenerationError(ElevenLabsError):
    pass


def upload_asset(file_path: str | Path, name: str | None = None) -> str:
    """Incarca un fisier (ex: poza de referinta a prezentatorului) ca asset
    ElevenLabs si returneaza asset_id, folosibil apoi ca referinta de imagine
    intr-o generare video (subiect consistent intre variante)."""
    file_path = Path(file_path)
    if not file_path.exists():
        raise VideoGenerationError(f"Fisierul de referinta nu exista: {file_path}")
    with open(file_path, "rb") as f:
        resp = requests.post(
            f"{API_BASE}/assets",
            headers={"xi-api-key": _api_key()},
            data={"name": name or file_path.name},
            files={"file": (file_path.name, f)},
            timeout=60,
        )
    if resp.status_code != 200:
        raise VideoGenerationError(f"Upload-ul imaginii de referinta a esuat ({resp.status_code}): {resp.text}")
    return resp.json()["asset_id"]


def create_video_generation(
    prompt: str,
    model_id: str = DEFAULT_VIDEO_MODEL,
    duration_secs: int = 8,
    aspect_ratio: str = "9:16",
    resolution: str = "1080p",
    generate_audio: bool = True,
    reference_image_asset_ids: list[str] | None = None,
) -> str:
    """Porneste o generare video async si returneaza generation_id.

    `reference_image_asset_ids` (optional, max 3, doar pentru modelele Veo):
    id-uri de assets (vezi upload_asset) folosite ca referinta vizuala, ca
    subiectul (prezentatorul) sa ramana consistent intre generari diferite.
    """
    payload = {
        "model_id": model_id,
        "prompt": prompt,
        "duration_secs": duration_secs,
        "aspect_ratio": aspect_ratio,
        "resolution": resolution,
        "generate_audio": generate_audio,
    }
    if reference_image_asset_ids:
        payload["images"] = [
            {"type": "asset", "asset_id": asset_id} for asset_id in reference_image_asset_ids
        ]

    resp = requests.post(
        f"{API_BASE}/flows/video",
        headers={"xi-api-key": _api_key(), "Content-Type": "application/json"},
        json=payload,
        timeout=60,
    )
    if resp.status_code != 200:
        raise VideoGenerationError(f"Crearea generarii video a esuat ({resp.status_code}): {resp.text}")
    data = resp.json()
    return data["id"]


def get_video_generation(generation_id: str) -> dict:
    resp = requests.get(
        f"{API_BASE}/flows/video/{generation_id}",
        headers={"xi-api-key": _api_key()},
        timeout=30,
    )
    if resp.status_code != 200:
        raise VideoGenerationError(f"Interogarea generarii video a esuat ({resp.status_code}): {resp.text}")
    return resp.json()


def wait_for_video(generation_id: str, poll_interval: float = 5.0, timeout: float = 900.0) -> dict:
    """Asteapta pana cand generarea e completed/failed. Returneaza raspunsul final."""
    start = time.monotonic()
    while True:
        result = get_video_generation(generation_id)
        status = result.get("status")
        if status == "completed":
            return result
        if status == "failed":
            raise VideoGenerationError(
                f"Generarea video a esuat ({result.get('failure_reason')}): {result.get('error_message')}"
            )
        if time.monotonic() - start > timeout:
            raise VideoGenerationError(f"Timeout asteptand generarea video (id={generation_id}, ultim status={status})")
        time.sleep(poll_interval)


def download_video(content_url: str, output_path: str | Path) -> Path:
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    resp = requests.get(content_url, timeout=180)
    if resp.status_code != 200:
        raise VideoGenerationError(f"Descarcarea video-ului generat a esuat ({resp.status_code})")
    output_path.write_bytes(resp.content)
    return output_path


def generate_video(
    prompt: str,
    output_path: str | Path,
    model_id: str = DEFAULT_VIDEO_MODEL,
    duration_secs: int = 8,
    aspect_ratio: str = "9:16",
    resolution: str = "1080p",
    reference_image_asset_ids: list[str] | None = None,
    on_status: callable | None = None,
) -> Path:
    """Fluxul complet: creeaza generarea, asteapta finalizarea, descarca fisierul."""
    generation_id = create_video_generation(
        prompt=prompt,
        model_id=model_id,
        duration_secs=duration_secs,
        aspect_ratio=aspect_ratio,
        resolution=resolution,
        reference_image_asset_ids=reference_image_asset_ids,
    )
    if on_status:
        on_status(f"Generare video pornita (id={generation_id}, model={model_id}, durata={duration_secs}s)")
    result = wait_for_video(generation_id)
    if on_status:
        on_status(f"Generare video completa: {result.get('content_mime_type')}")
    return download_video(result["content_url"], output_path)
