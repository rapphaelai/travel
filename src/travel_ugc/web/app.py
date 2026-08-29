"""Dashboard web pentru automatizarea UGC Raphael Travel.

Rulare:
    PYTHONPATH=src uvicorn travel_ugc.web.app:app --reload --port 8000

Citeste automat cheia din fisierul .env de la radacina proiectului (vezi
.env.example) -- nu mai trebuie pusa manual in linia de comanda.

Apoi deschizi http://localhost:8000 in browser.

Flux:
  1. Completezi contextul excursiei (formular) + optional o poza de referinta
     a prezentatorului (ca subiectul sa ramana consistent intre variante).
  2. Ceri generarea a 7 variante de prompt (unghiuri de copywriting diferite).
  3. Alegi o varianta (sau o editezi) si ceri 4 generari video
     (veo-3.1-fast, 8s, audio ON) -- ruleaza in fundal, cu banner text
     suprapus automat la final pe fiecare din cele 4 rezultate.
  4. Ceri campurile de Meta Ads (text principal x4, titlu x4, descriere x3),
     gata de copy-paste in Ads Manager.
"""
from __future__ import annotations

import shutil
import tempfile
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from fastapi import FastAPI, File, Form, HTTPException, UploadFile

# Incarca .env de la radacina proiectului (langa README.md), daca exista --
# in productie (ex: Render), variabilele vin din mediu si load_dotenv() e un no-op.
load_dotenv(Path(__file__).resolve().parents[3] / ".env")
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from ..meta_ads.copy_generator import generate_ad_copy
from ..prompt_variations import PromptContext, generate_prompt_variants
from ..video.elevenlabs_flows import DEFAULT_VIDEO_MODEL, VideoGenerationError, upload_asset
from ..voice.elevenlabs_client import ElevenLabsError
from . import jobs, storage

REPO_ROOT = Path(__file__).resolve().parents[3]
STATIC_DIR = Path(__file__).resolve().parent / "static"

storage._ensure_dirs()

app = FastAPI(title="Raphael Travel UGC Dashboard")
app.mount("/media", StaticFiles(directory=str(storage.MEDIA_DIR)), name="media")
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/")
def index() -> FileResponse:
    return FileResponse(str(STATIC_DIR / "index.html"))


def _context_to_prompt_ctx(ctx: dict) -> PromptContext:
    return PromptContext(
        presenter_description=ctx.get("presenter_description") or PromptContext().presenter_description,
        location_description=ctx.get("location_description") or PromptContext().location_description,
        region_hint=ctx.get("region_hint", ""),
        region_hint_en=ctx.get("region_hint_en", ""),
        main_objective=ctx.get("main_objective", ""),
        date_line=ctx.get("date_line", ""),
        period_line=ctx.get("period_line", ""),
        price_line=ctx.get("price_line", ""),
        departure_city=ctx.get("departure_city") or "București",
        brand_name=ctx.get("brand_name") or "Raphael Travel",
        cta_extra=ctx.get("cta_extra", ""),
        free_context=ctx.get("free_context", ""),
        reference_image=bool(ctx.get("reference_image_asset_id")),
    )


@app.post("/api/contexts")
async def create_context(
    hook_line: str = Form(...),
    start_date: str = Form(...),
    end_date: str = Form(...),
    objectives_count: int = Form(...),
    price_line: str = Form(...),
    location_description: str = Form(...),
    region_hint: str = Form(""),
    region_hint_en: str = Form(""),
    main_objective: str = Form(""),
    date_line: str = Form(""),
    period_line: str = Form(""),
    departure_city: str = Form("București"),
    brand_name: str = Form("Raphael Travel"),
    presenter_description: str = Form(""),
    cta_extra: str = Form(""),
    free_context: str = Form(""),
    reference_image: Optional[UploadFile] = File(None),
):
    context_id = storage.new_id()
    ctx = {
        "id": context_id,
        "created_at": storage.now_iso(),
        "hook_line": hook_line,
        "start_date": start_date,
        "end_date": end_date,
        "objectives_count": objectives_count,
        "price_line": price_line,
        "location_description": location_description,
        "region_hint": region_hint,
        "region_hint_en": region_hint_en,
        "main_objective": main_objective,
        "date_line": date_line,
        "period_line": period_line,
        "departure_city": departure_city,
        "brand_name": brand_name,
        "presenter_description": presenter_description or PromptContext().presenter_description,
        "cta_extra": cta_extra,
        "free_context": free_context,
        "banner_template": "config/banner_template.yaml",
        "reference_image_asset_id": None,
        "reference_image_filename": None,
        "prompts": [],
        "meta_ads_copy": None,
        "jobs": {},
    }

    if reference_image is not None and reference_image.filename:
        with tempfile.NamedTemporaryFile(delete=False, suffix=Path(reference_image.filename).suffix) as tmp:
            shutil.copyfileobj(reference_image.file, tmp)
            tmp_path = Path(tmp.name)
        try:
            asset_id = upload_asset(tmp_path, name=reference_image.filename)
            ctx["reference_image_asset_id"] = asset_id
            ctx["reference_image_filename"] = reference_image.filename
        except (VideoGenerationError, ElevenLabsError) as exc:
            raise HTTPException(status_code=502, detail=f"Upload poza de referinta a esuat: {exc}") from exc
        finally:
            tmp_path.unlink(missing_ok=True)

    storage.save_context(ctx)
    return ctx


@app.get("/api/contexts")
def list_contexts():
    return storage.list_contexts()


@app.get("/api/contexts/{context_id}")
def get_context(context_id: str):
    ctx = storage.load_context(context_id)
    if ctx is None:
        raise HTTPException(status_code=404, detail="Context inexistent")
    return ctx


@app.delete("/api/contexts/{context_id}")
def delete_context(context_id: str):
    if not storage.delete_context(context_id):
        raise HTTPException(status_code=404, detail="Context inexistent")
    return {"ok": True}


@app.post("/api/contexts/{context_id}/prompts")
def generate_prompts(context_id: str):
    ctx = storage.load_context(context_id)
    if ctx is None:
        raise HTTPException(status_code=404, detail="Context inexistent")
    variants = generate_prompt_variants(_context_to_prompt_ctx(ctx))
    ctx["prompts"] = [{"angle_id": v.angle_id, "angle_label": v.angle_label, "prompt": v.prompt} for v in variants]
    storage.save_context(ctx)
    return ctx["prompts"]


class PromptEdit(BaseModel):
    prompt: str


@app.patch("/api/contexts/{context_id}/prompts/{angle_id}")
def edit_prompt(context_id: str, angle_id: str, body: PromptEdit):
    ctx = storage.load_context(context_id)
    if ctx is None:
        raise HTTPException(status_code=404, detail="Context inexistent")
    for p in ctx.get("prompts", []):
        if p["angle_id"] == angle_id:
            p["prompt"] = body.prompt
            storage.save_context(ctx)
            return p
    raise HTTPException(status_code=404, detail="Prompt inexistent")


@app.post("/api/contexts/{context_id}/meta-ads")
def generate_meta_ads(context_id: str):
    ctx = storage.load_context(context_id)
    if ctx is None:
        raise HTTPException(status_code=404, detail="Context inexistent")
    copy = generate_ad_copy(_context_to_prompt_ctx(ctx))
    ctx["meta_ads_copy"] = {
        "primary_texts": copy.primary_texts,
        "headlines": copy.headlines,
        "descriptions": copy.descriptions,
    }
    storage.save_context(ctx)
    return ctx["meta_ads_copy"]


class GenerateRequest(BaseModel):
    angle_id: str
    prompt: str
    take_count: int = 4
    model_id: str = DEFAULT_VIDEO_MODEL
    duration_secs: int = 8


@app.post("/api/contexts/{context_id}/generate")
def start_generate(context_id: str, body: GenerateRequest):
    ctx = storage.load_context(context_id)
    if ctx is None:
        raise HTTPException(status_code=404, detail="Context inexistent")
    ref_ids = [ctx["reference_image_asset_id"]] if ctx.get("reference_image_asset_id") else None
    job_id = jobs.start_generation_job(
        context_id=context_id,
        prompt=body.prompt,
        angle_id=body.angle_id,
        take_count=body.take_count,
        model_id=body.model_id,
        duration_secs=body.duration_secs,
        reference_image_asset_ids=ref_ids,
    )
    return {"job_id": job_id}


@app.get("/api/contexts/{context_id}/jobs/{job_id}")
def get_job(context_id: str, job_id: str):
    ctx = storage.load_context(context_id)
    if ctx is None or job_id not in ctx.get("jobs", {}):
        raise HTTPException(status_code=404, detail="Job inexistent")
    return ctx["jobs"][job_id]
