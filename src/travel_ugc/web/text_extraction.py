"""Extrage automat detaliile structurate ale unei excursii dintr-un text
liber (exact cum ai descrie excursia intr-o conversatie), folosind Claude.

Rezultatul e folosit doar ca sa pre-completeze formularul din dashboard --
tu revezi/corectezi inainte de a salva, nu se sare peste verificare (datele
de pe banner si prompturile video trebuie sa fie exacte).

Necesita ANTHROPIC_API_KEY in .env (cont separat de ElevenLabs/Meta, de pe
console.anthropic.com).
"""
from __future__ import annotations

import os
from datetime import date

import anthropic

EXTRACTION_TOOL = {
    "name": "extract_trip_details",
    "description": (
        "Extrage detaliile structurate ale unei excursii turistice romanesti "
        "dintr-un text liber, ca sa completeze automat un formular."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "hook_line": {
                "type": "string",
                "description": "Propozitia scurta de hook pentru banner, ex: 'Hai cu noi in excursie'.",
            },
            "start_date": {
                "type": "string",
                "description": "Data de inceput, format YYYY-MM-DD. Daca anul lipseste, alege cea mai apropiata data viitoare.",
            },
            "end_date": {
                "type": "string",
                "description": "Data de sfarsit, format YYYY-MM-DD. Pentru excursie de o zi, egala cu start_date.",
            },
            "objectives_count": {
                "type": "integer",
                "description": "Numarul de obiective turistice mentionate sau enumerate in text.",
            },
            "price_line": {
                "type": "string",
                "description": "Textul de pret pentru banner, scurt, ex: 'Excursie de o zi, ieftina!' sau 'Doar 499 lei, totul asigurat'.",
            },
            "price_line_dialogue": {
                "type": "string",
                "description": "Doar suma/pretul brut, FARA cuvinte ca 'doar' in fata (ex: '499 lei', nu 'doar 499 lei') -- sabloanele adauga singure acel cuvant.",
            },
            "location_description": {
                "type": "string",
                "description": "Descriere vizuala scurta IN ENGLEZA a locatiei/scenei, pentru generarea video AI, ex: 'a stunning Romanian Orthodox monastery'.",
            },
            "region_hint_en": {
                "type": "string",
                "description": "Regiunea IN ENGLEZA, optional, pentru descrierea scenei video, ex: 'near Bucharest'.",
            },
            "region_hint": {
                "type": "string",
                "description": (
                    "O FRAZA COMPLETA in romana despre regiune, gata de inserat direct intr-o "
                    "propozitie -- include prepozitia (ex: 'aproape de Bucuresti' sau "
                    "'in inima Tarii Hategului'), nu doar un nume de loc."
                ),
            },
            "main_objective": {
                "type": "string",
                "description": "Obiectivul turistic principal, in romana, ex: 'Manastirea Prislop'.",
            },
            "date_line": {
                "type": "string",
                "description": "Data pentru replica vorbita, cu majuscule, ex: '19 SEPTEMBRIE' sau '4-5 SEPTEMBRIE'.",
            },
            "period_line": {
                "type": "string",
                "description": "Perioada pentru replica vorbita, scrisa natural, ex: '19 septembrie' sau '4-5 septembrie'.",
            },
            "departure_city": {
                "type": "string",
                "description": "Orasul de plecare, ex: 'Bucuresti'. Implicit 'Bucuresti' daca nu se mentioneaza.",
            },
            "brand_name": {
                "type": "string",
                "description": "Numele brandului/agentiei, ex: 'Raphael Travel'. Implicit 'Raphael Travel' daca nu se mentioneaza altul.",
            },
            "cta_extra": {
                "type": "string",
                "description": "Un detaliu scurt de call-to-action mentionat in text, ex: 'Locuri limitate'. Sir gol daca nu exista.",
            },
        },
        "required": [
            "hook_line", "start_date", "end_date", "objectives_count", "price_line",
            "price_line_dialogue", "location_description", "region_hint",
            "main_objective", "date_line", "period_line", "departure_city", "brand_name",
            "cta_extra",
        ],
    },
}


class ExtractionError(RuntimeError):
    pass


def extract_trip_details(raw_text: str) -> dict:
    """Trimite textul liber catre Claude si returneaza campurile extrase,
    ca dict, gata de folosit pentru a pre-completa formularul excursiei."""
    if not raw_text or not raw_text.strip():
        raise ExtractionError("Textul e gol -- lipeste detaliile excursiei inainte de extragere.")

    if not os.environ.get("ANTHROPIC_API_KEY"):
        raise ExtractionError(
            "Lipseste ANTHROPIC_API_KEY. Seteaza-l in .env (cheie separata, de pe "
            "console.anthropic.com -> API Keys) ca sa poti folosi extragerea automata din text."
        )

    client = anthropic.Anthropic()

    today = date.today().isoformat()

    try:
        response = client.messages.create(
            model="claude-opus-5",
            max_tokens=2000,
            system=(
                f"Data de azi este {today}. Extragi detalii despre o excursie turistica "
                "romaneasca dintr-un text liber (scris de un agent de turism, informal), "
                "ca sa completezi automat un formular. Daca anul nu e mentionat explicit, "
                "alege cea mai apropiata data viitoare fata de data de azi. Nu inventa "
                "detalii care nu apar deloc in text sau nu pot fi deduse rezonabil -- "
                "foloseste valorile implicite descrise in schema."
            ),
            tools=[EXTRACTION_TOOL],
            tool_choice={"type": "tool", "name": "extract_trip_details"},
            messages=[{"role": "user", "content": raw_text}],
        )
    except anthropic.AuthenticationError as exc:
        raise ExtractionError(
            "Cheia ANTHROPIC_API_KEY e invalida sau lipseste. "
            "O iei de pe console.anthropic.com -> API Keys."
        ) from exc
    except anthropic.APIStatusError as exc:
        raise ExtractionError(f"Anthropic API a raspuns cu eroare: {exc}") from exc

    for block in response.content:
        if block.type == "tool_use":
            return dict(block.input)

    raise ExtractionError("Claude nu a returnat datele extrase (niciun tool_use in raspuns).")
