"""Construieste scriptul de naratiune (text) pentru voiceover-ul UGC, pornind
de la detaliile excursiei. Textul rezultat e cel trimis catre ElevenLabs TTS.

Structura urmareste un format UGC clasic, scurt, potrivit pentru Reels/TikTok:
  hook (3-5 sec) -> ce oferim -> obiective/highlight-uri -> pret+CTA
"""
from __future__ import annotations

from .trip import Trip


def build_narration_script(trip: Trip) -> str:
    lines: list[str] = []

    # Hook - trebuie sa opreasca scroll-ul in primele secunde.
    lines.append(f"{trip.hook_line}!")

    # Introducere destinatie.
    lines.append(f"Pe {trip.period_line} mergem la {trip.destination}.")

    # Obiective / highlight-uri, ca lista naturala vorbita.
    if trip.objectives:
        if len(trip.objectives) == 1:
            obiective_text = trip.objectives[0]
        else:
            obiective_text = ", ".join(trip.objectives[:-1]) + f" si {trip.objectives[-1]}"
        lines.append(
            f"Vizitam {trip.objectives_count} obiective: {obiective_text}."
        )

    # Argumente de vanzare (transport, ghid, etc.)
    if trip.selling_points:
        lines.append("Vine cu " + ", ".join(trip.selling_points) + ".")

    # Pret si argument de conversie.
    if trip.price_details:
        lines.append(trip.price_details)
    lines.append(trip.price_line + ".")

    # Call to action.
    lines.append(trip.cta)

    return " ".join(lines)


def build_video_prompt(trip: Trip) -> str:
    """Prompt pentru generarea video AI end-to-end (model+audio impreuna,
    ex: bytedance-seedance-v2.5 prin ElevenLabs Flows) -- combina descrierea
    vizuala de scena UGC cu textul exact pe care personajul trebuie sa-l
    spuna, ca sa iasa un video de tip "persoana vorbeste in camera despre
    excursie", nu doar un peisaj generic.
    """
    narration = build_narration_script(trip)
    return (
        "Videoclip UGC, stil selfie filmat cu telefonul, vertical 9:16. "
        "O persoana calda si prietenoasa, gen ghid de excursii, vorbeste direct in camera, "
        f"intr-un cadru autentic legat de {trip.destination}, lumina naturala, energie entuziasta dar naturala, "
        "nu actorie exagerata. Personajul vorbeste in limba romana, clar si cu entuziasm autentic, exact aceste replici: "
        f"\"{narration}\" "
        "Camera usor instabila, stil UGC autentic de social media, nu productie de studio."
    )


def build_caption(trip: Trip) -> str:
    """Text scurt pentru descrierea postarii (Reels/TikTok/Meta ad), separat
    de banner si de voiceover -- util la publicare si la crearea reclamei."""
    tags = "#excursii #Craiova #RaphaelTravel #weekendgetaway"
    return (
        f"{trip.hook_line} ✈️ {trip.period_line} • "
        f"{trip.objectives_count} obiective • {trip.destination}\n"
        f"{trip.cta}\n{tags}"
    )
