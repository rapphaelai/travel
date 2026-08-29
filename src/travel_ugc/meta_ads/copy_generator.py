"""Genereaza textele pentru campania Meta Ads (creativ dinamic): Text
principal (4 variante), Titlu (4 variante), Descrierea apelului (2-4
variante) -- exact campurile din Meta Ads Manager, gata de copy-paste.

Fara linii de pauza lungi (em dash "—" / en dash "–") in text, la cerere.
Nu apeleaza niciun LLM extern -- sabloane completate cu contextul excursiei
(acelasi PromptContext folosit si pentru prompturile video).
"""
from __future__ import annotations

from dataclasses import dataclass, field

from ..prompt_variations import PromptContext


@dataclass
class MetaAdsCopy:
    primary_texts: list[str] = field(default_factory=list)
    headlines: list[str] = field(default_factory=list)
    descriptions: list[str] = field(default_factory=list)


def _no_dash(text: str) -> str:
    """Inlocuieste em/en dash cu punctuatie normala, ca sa respectam cerinta
    'fara linii de pauza' pe campurile de Meta Ads."""
    return text.replace(" — ", ". ").replace("—", ",").replace(" – ", ". ").replace("–", ",")


def _strip_end(text: str) -> str:
    """Scoate punctuatia finala (!/./,), utila cand textul e inserat la
    mijlocul altei propozitii, ca sa evitam '!.' sau ',.' duble."""
    return text.rstrip("!.,; ").strip()


def generate_ad_copy(ctx: PromptContext) -> MetaAdsCopy:
    when = ctx.date_line or ctx.period_line or "în curând"
    # Doar campuri in romana, orientate spre client -- location_description
    # e descrierea vizuala in engleza pentru promptul video, nu se foloseste aici.
    where = ctx.main_objective or "această excursie"
    price = _strip_end(ctx.price_line) or "preț accesibil"
    brand = ctx.brand_name
    region = ctx.region_hint or "zonă"

    primary_texts = [
        (
            f"Mii de oameni vin în fiecare an la {where}. "
            f"Un pelerinaj de neuitat, {ctx.period_line or when}, în inima {region}. "
            f"✅ Transport + cazare cu mic dejun, totul asigurat."
        ),
        (
            f"{where}, {when}, cu totul asigurat, doar {price}. 🚌 "
            f"Transport, cazare cu mic dejun, program organizat. Tu doar te bucuri de drum."
        ),
        (
            f"O oază de liniște, {region}. 🙏 "
            f"{when}, cu transport și cazare cu mic dejun, totul asigurat. "
            f"📅 {ctx.period_line or when} din {ctx.departure_city} • {price}."
        ),
        (
            f"Ai vrut mereu să ajungi la {where}, dar e departe și complicat? Ne ocupăm noi de tot. 🚌 "
            f"Transport, cazare, program, totul organizat. Tu doar urci în autocar, cu {brand}."
        ),
    ]

    headlines = [
        f"{where}, {when}".strip(", "),
        f"{where}, {when}. {price}".strip(", "),
        f"La {where}" if ctx.main_objective else f"{brand}, {when}",
        f"{when}, doar {price}",
    ]

    descriptions = [
        f"Hai acum cu noi în cea mai frumoasă excursie!",
        f"Plecare din {ctx.departure_city}, {when}. Locuri limitate, rezervă ți locul.",
        f"{ctx.cta_extra or 'Nu rata'}. {price}, totul inclus.",
    ]

    copy = MetaAdsCopy(
        primary_texts=[_no_dash(t) for t in primary_texts],
        headlines=[_no_dash(t) for t in headlines],
        descriptions=[_no_dash(t) for t in descriptions],
    )
    return copy
