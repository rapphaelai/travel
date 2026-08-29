"""Client subtire pentru ElevenLabs Text-to-Speech.

Nu depinde de SDK-ul oficial (evitam o dependinta grea) -- apeleaza direct
REST API-ul ElevenLabs cu `requests`. Are nevoie de variabila de mediu
ELEVENLABS_API_KEY (vezi .env.example).

Docs API: https://elevenlabs.io/docs/api-reference/text-to-speech
"""
from __future__ import annotations

import os
from pathlib import Path

import requests

API_BASE = "https://api.elevenlabs.io/v1"


class ElevenLabsError(RuntimeError):
    pass


def _api_key() -> str:
    key = os.environ.get("ELEVENLABS_API_KEY")
    if not key:
        raise ElevenLabsError(
            "Lipseste ELEVENLABS_API_KEY. Seteaza-l ca variabila de mediu sau in .env "
            "(vezi .env.example). Cheia se genereaza din contul tau ElevenLabs, "
            "sectiunea Profile -> API Keys."
        )
    return key


def list_voices() -> list[dict]:
    resp = requests.get(
        f"{API_BASE}/voices",
        headers={"xi-api-key": _api_key()},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json().get("voices", [])


def text_to_speech(
    text: str,
    voice_id: str,
    output_path: str | Path,
    model_id: str = "eleven_multilingual_v2",
    stability: float = 0.5,
    similarity_boost: float = 0.8,
    style: float = 0.35,
) -> Path:
    """Genereaza voiceover MP3 din text si il salveaza la output_path.

    `voice_id` e id-ul vocii tale native ElevenLabs (poate fi o voce clonata
    din contul de agentie / Creative). Foloseste list_voices() pentru a-l gasi.
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    resp = requests.post(
        f"{API_BASE}/text-to-speech/{voice_id}",
        headers={
            "xi-api-key": _api_key(),
            "Content-Type": "application/json",
            "Accept": "audio/mpeg",
        },
        json={
            "text": text,
            "model_id": model_id,
            "voice_settings": {
                "stability": stability,
                "similarity_boost": similarity_boost,
                "style": style,
            },
        },
        timeout=120,
    )
    if resp.status_code != 200:
        raise ElevenLabsError(
            f"ElevenLabs a raspuns cu eroare {resp.status_code}: {resp.text}"
        )

    output_path.write_bytes(resp.content)
    return output_path
