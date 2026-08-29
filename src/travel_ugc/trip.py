"""Incarcarea si validarea fisierelor de excursie (config/trips/*.yaml)."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Any

import yaml

MONTHS_RO = {
    1: "ianuarie", 2: "februarie", 3: "martie", 4: "aprilie",
    5: "mai", 6: "iunie", 7: "iulie", 8: "august",
    9: "septembrie", 10: "octombrie", 11: "noiembrie", 12: "decembrie",
}


def _parse_date(value: str) -> date:
    return datetime.strptime(value, "%Y-%m-%d").date()


def _format_ro_date(d: date) -> str:
    return f"{d.day} {MONTHS_RO[d.month]}"


@dataclass
class Trip:
    id: str
    hook_line: str
    start_date: date
    end_date: date
    objectives_count: int
    price_line: str
    destination: str
    objectives: list[str]
    selling_points: list[str]
    cta: str
    price_details: str
    tone: str
    voice: dict[str, Any]
    footage: dict[str, Any]
    banner_template: str
    output_file: str
    meta_ads: dict[str, Any]
    raw: dict[str, Any] = field(repr=False, default_factory=dict)

    @property
    def period_line(self) -> str:
        if self.start_date == self.end_date:
            return _format_ro_date(self.start_date)
        if self.start_date.month == self.end_date.month:
            return f"{self.start_date.day} - {self.end_date.day} {MONTHS_RO[self.start_date.month]}"
        return f"{_format_ro_date(self.start_date)} - {_format_ro_date(self.end_date)}"

    @property
    def objectives_line(self) -> str:
        return f"{self.objectives_count} obiective"

    @property
    def is_day_trip(self) -> bool:
        return self.start_date == self.end_date


def load_trip(path: str | Path) -> Trip:
    path = Path(path)
    data = yaml.safe_load(path.read_text(encoding="utf-8"))

    required = [
        "id", "hook_line", "start_date", "end_date", "objectives_count",
        "price_line", "destination", "objectives", "cta", "voice",
        "footage", "banner_template", "output",
    ]
    missing = [k for k in required if k not in data]
    if missing:
        raise ValueError(
            f"Fisierul de excursie '{path}' nu are campurile obligatorii: {', '.join(missing)}"
        )

    return Trip(
        id=data["id"],
        hook_line=data["hook_line"],
        start_date=_parse_date(str(data["start_date"])),
        end_date=_parse_date(str(data["end_date"])),
        objectives_count=int(data["objectives_count"]),
        price_line=data["price_line"],
        destination=data["destination"],
        objectives=list(data.get("objectives", [])),
        selling_points=list(data.get("selling_points", [])),
        cta=data["cta"],
        price_details=data.get("price_details", ""),
        tone=data.get("tone", "prietenos, natural, ca un sfat intre prieteni"),
        voice=data["voice"],
        footage=data["footage"],
        banner_template=data["banner_template"],
        output_file=data["output"]["file"],
        meta_ads=data.get("meta_ads", {}),
        raw=data,
    )
