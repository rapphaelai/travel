"""Genereaza banner-ul text (panglicile cu perioada excursiei, obiective,
pret) ca imagine PNG transparenta, dupa stilul din config/banner_template.yaml.

Rezultatul e o imagine cu acelasi format ca video-ul (implicit 1080x1920,
9:16) care se suprapune peste footage cu ffmpeg in compose.py.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
from PIL import Image, ImageDraw, ImageFont

from ..trip import Trip

REPO_ROOT = Path(__file__).resolve().parents[3]


@dataclass
class RibbonSpec:
    id: str
    text: str
    position: str  # "top" | "bottom"
    offset_y: int
    background_color: tuple[int, int, int, int]
    text_color: tuple[int, int, int, int]
    font_path: Path
    font_size: int
    padding_x: int
    padding_y: int
    max_width_ratio: float
    align: str
    uppercase: bool


def _load_template(template_path: str | Path) -> dict[str, Any]:
    template_path = Path(template_path)
    if not template_path.is_absolute():
        template_path = REPO_ROOT / template_path
    return yaml.safe_load(template_path.read_text(encoding="utf-8"))


def _resolve_font(template: dict, template_path: Path, key: str, size: int) -> ImageFont.FreeTypeFont:
    font_rel = template["fonts"][key]
    font_path = Path(font_rel)
    if not font_path.is_absolute():
        font_path = REPO_ROOT / font_rel
    if not font_path.exists():
        raise FileNotFoundError(
            f"Fontul '{font_path}' din template-ul de banner nu a fost gasit. "
            "Verifica assets/fonts/ sau calea din banner_template.yaml."
        )
    return ImageFont.truetype(str(font_path), size)


def _wrap_text(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont, max_width: int) -> list[str]:
    words = text.split()
    lines: list[str] = []
    current = ""
    for word in words:
        candidate = f"{current} {word}".strip()
        bbox = draw.textbbox((0, 0), candidate, font=font)
        if bbox[2] - bbox[0] <= max_width or not current:
            current = candidate
        else:
            lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def render_banner(trip: Trip, template_path: str | Path | None = None) -> Image.Image:
    """Randeaza banner-ul complet ca imagine RGBA, gata de suprapus pe video."""
    template = _load_template(template_path or trip.banner_template)
    template_path_resolved = Path(template_path or trip.banner_template)

    canvas_w = template["canvas"]["width"]
    canvas_h = template["canvas"]["height"]
    canvas = Image.new("RGBA", (canvas_w, canvas_h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(canvas)

    field_values = {
        "hook_line": trip.hook_line,
        "period_line": trip.period_line,
        "objectives_line": trip.objectives_line,
        "price_line": trip.price_line,
    }

    for ribbon_cfg in template["ribbons"]:
        text = field_values.get(ribbon_cfg["text_field"], "")
        if not text:
            continue
        if ribbon_cfg.get("uppercase"):
            text = text.upper()

        font = _resolve_font(template, template_path_resolved, ribbon_cfg["font"], ribbon_cfg["font_size"])
        max_text_width = int(canvas_w * ribbon_cfg["max_width_ratio"]) - 2 * ribbon_cfg["padding_x"]
        lines = _wrap_text(draw, text, font, max_text_width)

        line_heights = []
        line_widths = []
        for line in lines:
            bbox = draw.textbbox((0, 0), line, font=font)
            line_widths.append(bbox[2] - bbox[0])
            line_heights.append(bbox[3] - bbox[1])
        line_spacing = int(ribbon_cfg["font_size"] * 0.25)
        text_block_h = sum(line_heights) + line_spacing * (len(lines) - 1)
        block_w = max(line_widths) if line_widths else 0

        ribbon_w = block_w + 2 * ribbon_cfg["padding_x"]
        ribbon_h = text_block_h + 2 * ribbon_cfg["padding_y"]
        ribbon_x = (canvas_w - ribbon_w) // 2

        if ribbon_cfg["position"] == "top":
            ribbon_y = ribbon_cfg["offset_y"]
        else:
            ribbon_y = canvas_h - ribbon_cfg["offset_y"] - ribbon_h

        draw.rounded_rectangle(
            [ribbon_x, ribbon_y, ribbon_x + ribbon_w, ribbon_y + ribbon_h],
            radius=18,
            fill=tuple(ribbon_cfg["background_color"]),
        )

        cursor_y = ribbon_y + ribbon_cfg["padding_y"]
        for line, lw, lh in zip(lines, line_widths, line_heights):
            if ribbon_cfg["align"] == "center":
                line_x = ribbon_x + (ribbon_w - lw) // 2
            else:
                line_x = ribbon_x + ribbon_cfg["padding_x"]
            draw.text((line_x, cursor_y), line, font=font, fill=tuple(ribbon_cfg["text_color"]))
            cursor_y += lh + line_spacing

    return canvas


def save_banner(trip: Trip, output_path: str | Path, template_path: str | Path | None = None) -> Path:
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    img = render_banner(trip, template_path)
    img.save(output_path)
    return output_path
