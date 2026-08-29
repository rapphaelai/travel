"""Motor de variante de prompt video, dupa formatul UGC selfie folosit deja
in conversatiile anterioare (vezi exemplul din brief): descriere de scena +
replica exacta in romana + note de audio + note de stil.

Nu apeleaza niciun LLM extern -- e un generator pe baza de sabloane (7
"unghiuri" distincte de copywriting), fiecare completat cu detaliile
excursiei (destinatie, perioada, obiective, pret, cta) + un context liber
optional adaugat de tine in dashboard. Rezultatul sunt 6-7 prompturi
distincte, gata de trimis catre generate_video().
"""
from __future__ import annotations

from dataclasses import dataclass, field

STYLE_SUFFIX = (
    "Style: hyper-realistic, mega natural UGC, candid, natural skin texture, "
    "no retouching, slightly imperfect framing. Real person, NOT a model."
)

INTRO = (
    "Vertical 9:16 selfie video, shot on iPhone POV, natural shake, "
    "enthusiastic UGC story vibe."
)


@dataclass
class PromptContext:
    """Toate variabilele libere din care se construiesc prompturile.
    Vine din formularul dashboard-ului (context.py leaga asta de Trip)."""

    presenter_description: str = (
        "a Romanian person in their 60s, dressed well for her age casual"
    )
    location_description: str = "a stunning monastery"          # en, ex: "a stunning Ilfov monastery near Bucharest"
    region_hint: str = ""                                        # ro, folosit in replici, ex: "aproape de Bucuresti"
    region_hint_en: str = ""                                     # en, optional, adaugat in scena vizuala daca location_description nu-l contine deja
    main_objective: str = ""                                     # ex: "Mănăstirea Prislop"
    date_line: str = ""                                          # ex: "19 SEPTEMBRIE"
    period_line: str = ""                                        # ex: "4-5 septembrie"
    price_line: str = ""                                         # ex: "499 lei"
    departure_city: str = "București"
    brand_name: str = "Raphael Travel"
    cta_extra: str = ""                                          # detaliu liber, ex: "Locuri limitate"
    free_context: str = ""                                       # orice altceva scrii tu in dashboard
    reference_image: bool = True                                 # daca ai incarcat o poza a prezentatorului


@dataclass
class PromptVariant:
    angle_id: str
    angle_label: str
    prompt: str


def _subject_clause(ctx: PromptContext) -> str:
    ref = "The subject (from the reference image), " if ctx.reference_image else "The subject, "
    return f"{ref}{ctx.presenter_description}"


def _scene_clause(ctx: PromptContext, lighting: str, expression: str) -> str:
    # location_description e descrierea vizuala principala (en). region_hint_en
    # se adauga DOAR daca nu pare deja continut in ea, ca sa evitam duplicarea
    # (ex: "a stunning Ilfov monastery" + "near Bucharest").
    loc = ctx.location_description
    if ctx.region_hint_en and ctx.region_hint_en.lower() not in loc.lower():
        loc = f"{loc} {ctx.region_hint_en}"
    return f"stands in front of {loc}, {lighting}, {expression}"


def _wrap(ctx: PromptContext, scene: str, dialogue: str, audio: str) -> str:
    return (
        f"{INTRO} {_subject_clause(ctx)}, {scene}.\n\n"
        f'The subject says in Romanian: "{dialogue}"\n\n'
        f"Audio: {audio}.\n\n"
        f"{STYLE_SUFFIX}"
    )


def _angle_urgency(ctx: PromptContext) -> PromptVariant:
    scene = _scene_clause(ctx, "bright daylight", "big genuine smile, gesturing naturally")
    dialogue = (
        f"Dacă vreți ceva frumos {ctx.region_hint or 'aproape de ' + ctx.departure_city} "
        f"pe {ctx.date_line or ctx.period_line}! E perfect! {ctx.main_objective or 'Locuri superbe'}, "
        f"grup prietenos, preț foarte mic. Vă așteptăm și pe voi, cu {ctx.brand_name}!"
    )
    audio = "birds, light ambient, faint bell, a touch of wind on the mic"
    return PromptVariant("urgenta_data", "Urgență + dată (hook direct)", _wrap(ctx, scene, dialogue, audio))


def _angle_social_proof(ctx: PromptContext) -> PromptVariant:
    scene = _scene_clause(ctx, "soft morning light", "calm, warm expression, hand gently gesturing toward the building")
    dialogue = (
        f"Mii de oameni vin în fiecare an la {ctx.main_objective or 'acest loc'}. "
        f"Un pelerinaj de neuitat, {ctx.period_line or 'în câteva zile'}, în inima {ctx.region_hint or 'zonei'}, "
        f"unde credincioșii se roagă și își găsesc liniștea. Totul organizat, cu {ctx.brand_name}."
    )
    audio = "distant church bell, soft wind, quiet birds"
    return PromptVariant("dovada_sociala", "Dovadă socială / pelerinaj", _wrap(ctx, scene, dialogue, audio))


def _angle_storytelling(ctx: PromptContext) -> PromptVariant:
    scene = _scene_clause(ctx, "golden hour light", "nostalgic soft smile, looking around slowly before turning to camera")
    dialogue = (
        f"Știți, m-am dus și eu prima dată puțin sceptic. Dar {ctx.main_objective or 'locul asta'} "
        f"chiar te schimbă. {ctx.period_line or 'Câteva zile'} în care uiți de tot. "
        f"Cred că merită să veniți și voi, cu {ctx.brand_name}."
    )
    audio = "gentle wind, distant footsteps on stone, quiet ambient nature"
    return PromptVariant("storytelling", "Poveste personală / emoțional", _wrap(ctx, scene, dialogue, audio))


def _angle_problem_solution(ctx: PromptContext) -> PromptVariant:
    scene = _scene_clause(ctx, "bright daylight", "friendly reassuring smile, open hand gesture like explaining something easy")
    dialogue = (
        f"Ați vrut mereu să ajungeți la {ctx.main_objective or 'locul acesta'}, dar e departe și complicat? "
        f"Noi ne ocupăm de tot: transport, cazare, program. {ctx.period_line or ''} "
        f"Tu doar te bucuri de drum, cu {ctx.brand_name}."
    )
    audio = "light ambient outdoor sound, faint traffic far in the background, birds"
    return PromptVariant("problema_solutie", "Problemă → soluție", _wrap(ctx, scene, dialogue, audio))


def _angle_scarcity(ctx: PromptContext) -> PromptVariant:
    scene = _scene_clause(ctx, "bright daylight", "excited energetic expression, leaning slightly toward camera")
    dialogue = (
        f"Ultimele locuri la excursia din {ctx.date_line or ctx.period_line}! "
        f"{ctx.main_objective or 'Un traseu superb'}, doar {ctx.price_line or 'la un preț mic'}. "
        f"{ctx.cta_extra or 'Nu rata'}! Rezervă-ți locul acum, cu {ctx.brand_name}."
    )
    audio = "light upbeat outdoor ambient, birds, faint chatter of a group nearby"
    return PromptVariant("scarcitate", "Scarcitate / ultimele locuri", _wrap(ctx, scene, dialogue, audio))


def _angle_practical(ctx: PromptContext) -> PromptVariant:
    scene = _scene_clause(ctx, "clear daylight", "calm confident expression, counting briefly on fingers while speaking")
    dialogue = (
        f"Pe scurt: {ctx.period_line or 'excursia'} la {ctx.main_objective or 'destinație'}, "
        f"plecare din {ctx.departure_city}, transport și ghid incluse, doar {ctx.price_line or 'preț accesibil'}. "
        f"Simplu și organizat, cu {ctx.brand_name}."
    )
    audio = "quiet neutral ambient, faint wind, no music"
    return PromptVariant("practic_informativ", "Practic / informativ", _wrap(ctx, scene, dialogue, audio))


def _angle_warm_invitation(ctx: PromptContext) -> PromptVariant:
    scene = _scene_clause(ctx, "warm afternoon light", "relaxed genuine smile, waving hand slightly like inviting a friend")
    dialogue = (
        f"Hai cu noi, ca la o ieșire cu prietenii! {ctx.period_line or 'O zi'} la {ctx.main_objective or 'un loc superb'}, "
        f"fără grija de nimic. {ctx.cta_extra or 'Te așteptăm'}, cu {ctx.brand_name}."
    )
    audio = "birds, light breeze, distant laughter of a small group"
    return PromptVariant("invitatie_calda", "Invitație caldă / prietenoasă", _wrap(ctx, scene, dialogue, audio))


ANGLE_BUILDERS = [
    _angle_urgency,
    _angle_social_proof,
    _angle_storytelling,
    _angle_problem_solution,
    _angle_scarcity,
    _angle_practical,
    _angle_warm_invitation,
]


def generate_prompt_variants(ctx: PromptContext) -> list[PromptVariant]:
    """Genereaza toate cele 7 variante distincte de prompt video pentru un context dat."""
    return [builder(ctx) for builder in ANGLE_BUILDERS]
