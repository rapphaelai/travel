# Raphael Travel/Academy — Automatizare UGC video + banner + Meta Ads

Pipeline care ia detaliile unei excursii (nume, perioadă, obiective, preț) și
generează automat:

1. **Scriptul de voce** pentru reclama UGC (naratiune scurtă, stil "sfat de la
   un prieten"), în română.
2. **Voiceover AI** prin ElevenLabs, cu vocea ta clonată.
3. **Banner text suprapus** pe video (perioada excursiei + nr. obiective +
   argumentul de conversie), în același stil ca posterele de tip cel din
   `HAI CU NOI IN EXCURSIE / 25 IULIE - 5 OBIECTIVE / EXCURSIE DE O ZI IEFTINA`.
4. **Videoclipul final** (format 9:16, gata de Reels/TikTok/Stories/Meta Ads).
5. **Campania de Meta Ads** pentru videoclipul respectiv, bazată pe formatul
   (tipul de video) care a performat cel mai bine până acum.

Testat local în acest sandbox cu ffmpeg + Pillow — pipeline-ul de video +
banner e verificat funcțional end-to-end (vezi capturile trimise în chat).
Partea de ElevenLabs și Meta Ads e completă ca și cod, dar are nevoie de
cheile tale API ca să ruleze efectiv (n-am avut acces la ele acum).

## Structura proiectului

```
config/
  banner_template.yaml        stilul banner-ului (culori, fonturi, poziții)
  trips/
    2026-07-25-...yaml        un fișier = o excursie = un input al automatizării
assets/
  fonts/                      fonturi bundle-uite (DejaVu Sans, licență liberă)
  footage/<trip-id>/          pozele/videoclipurile brute ale fiecărei excursii
  output/                     rezultatele generate (video, audio, banner) — ignorate de git
src/travel_ugc/
  trip.py                     încarcă și validează un fișier de excursie
  script_builder.py           construiește textul de narațiune + caption
  voice/elevenlabs_client.py  apel către ElevenLabs Text-to-Speech
  video/banner.py             randează banner-ul text (Pillow)
  video/compose.py            asamblează footage + banner + voiceover (ffmpeg)
  pipeline.py                 orchestratorul principal (CLI)
  meta_ads/
    client.py                 client subțire pentru Meta Graph API
    insights.py                statistici brute per reclamă
    performance.py             clasament pe *format de video*, nu doar pe reclamă
    campaign_builder.py         creează campanie/adset/creative/ad
    cli.py                      CLI: `stats`, `create-campaign`
```

## 1. Instalare

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# ffmpeg trebuie instalat separat (nu e pachet python)
sudo apt-get install -y ffmpeg      # Linux/Debian/Ubuntu
brew install ffmpeg                  # macOS
```

Copiază `.env.example` → `.env` și completează cheile (vezi secțiunile de mai
jos). `.env` e deja în `.gitignore`, nu ajunge niciodată în git.

## 2. Adaugi o excursie nouă (inputul automatizării)

Creezi un fișier nou în `config/trips/`, după modelul
`config/trips/2026-07-25-excursie-manastiri.yaml`. Câmpurile cheie:

- `hook_line`, `start_date`/`end_date`, `objectives_count`, `price_line` →
  exact textele care apar pe banner (ca în poza de referință).
- `destination`, `objectives`, `selling_points`, `cta`, `price_details`,
  `tone` → materialul brut din care se construiește scriptul de narațiune.
- `voice.voice_id` → vocea ta din ElevenLabs (vezi secțiunea 3).
- `footage.source_video` **sau** `footage.source_images` → materialul video
  brut peste care se pune banner-ul (pune fișierele în `assets/footage/<trip-id>/`).
- `meta_ads.*` → prefixul campaniei, bugetul zilnic, obiectivul, și
  `format_tag` — eticheta tipului de creativă (ex: `ugc-talking-head-9x16`),
  folosită mai jos ca să comparăm performanța pe *tip de format*, nu doar
  pe reclamă individuală.

## 3. Rulezi pipeline-ul video

Există două moduri de generare a videoclipului:

**A. Video generat integral de AI** (recomandat — nu ai nevoie de footage
propriu, ElevenLabs Flows generează scena + persoana + vocea într-un
singur pas, pornind dintr-un prompt construit automat din fișierul excursiei):

```bash
PYTHONPATH=src python3 -m travel_ugc.pipeline --trip config/trips/2026-07-25-excursie-manastiri.yaml --ai-video
```

Modelul implicit e `veo-3.1-generate-001` (max **8 secunde** per generare,
9:16, audio inclus — verificat direct din specificația API ElevenLabs).
Modelul `bytedance-seedance-v2.5` ar permite până la 30 de secunde, dar e
**dezactivat implicit pe cont** — dacă vrei clipuri mai lungi, contactează
suportul ElevenLabs să-l activeze, apoi rulează cu
`--ai-video-model bytedance-seedance-v2.5 --ai-video-duration 30`.
`gemini-omni-flash` ("Omni Flash", văzut în materialele de marketing
ElevenLabs) **nu e disponibil ca `model_id` prin API public** momentan —
doar prin interfața web Avatars, care nu are API încă.

**B. Footage propriu (poze/video puse de tine) + voce ElevenLabs separată**
(varianta inițială, utilă dacă ai deja imagini reale ale excursiei):

```bash
# doar banner-ul (PNG), rapid, fără ElevenLabs — bun ca preview
PYTHONPATH=src python3 -m travel_ugc.pipeline --trip config/trips/2026-07-25-excursie-manastiri.yaml --banner-only

# video complet, fără voce (dacă ELEVENLABS_API_KEY nu e încă setat)
PYTHONPATH=src python3 -m travel_ugc.pipeline --trip config/trips/2026-07-25-excursie-manastiri.yaml --no-voice

# video complet, cu voiceover ElevenLabs (TTS separat + footage-ul tău)
PYTHONPATH=src python3 -m travel_ugc.pipeline --trip config/trips/2026-07-25-excursie-manastiri.yaml
```

În ambele cazuri, rezultatul apare în `assets/output/<trip-id>.mp4` (sau
`-ai-raw.mp4` + finalul cu banner pentru varianta A), gata de postat sau de
folosit direct ca material pentru campania Meta Ads.

## 4. Conectarea ElevenLabs

1. Din contul tău ElevenLabs (Creative) → **Profile → API Keys** → generezi o
   cheie și o pui în `.env` la `ELEVENLABS_API_KEY`.
2. Găsești `voice_id`-ul vocii tale native/clonate:
   ```bash
   PYTHONPATH=src python3 -c "from travel_ugc.voice.elevenlabs_client import list_voices; [print(v['voice_id'], v['name']) for v in list_voices()]"
   ```
3. Pui `voice_id`-ul găsit în fișierul excursiei, la `voice.voice_id`.

Nu există un conector oficial "ElevenLabs" în acest mediu de lucru care să
țină automat cheia ta — de-asta pipeline-ul o citește direct din `.env`,
lucru care funcționează la fel de bine și rămâne complet sub controlul tău.

## 5. Conectarea Meta Ads (Raphael Travel)

Meta nu are un conector "plug-and-play" pentru chat; se conectează prin API
cu un token generat din Meta Business Suite. Pași:

1. **Business Manager** → **Setări Business** → **Utilizatori de sistem**
   (System Users) → creezi un utilizator de sistem nou (ex: "Automatizare
   Raphael Travel").
2. Îi atribui acces la contul de reclame Raphael Travel (**Ad Account**) cu
   rol de Admin sau Advertiser.
3. **Generate New Token** pentru acest utilizator de sistem, cu permisiunile:
   `ads_management`, `ads_read`, `business_management`. Alege durata cea mai
   lungă disponibilă (token de sistem — nu expiră la 60 de zile ca token-ul
   de user normal).
4. Copiezi token-ul în `.env` → `META_ACCESS_TOKEN`.
5. Iei ID-ul contului de reclame (din Ads Manager, URL sau Business Settings,
   format `123456789012345`) și îl pui în `.env` → `META_AD_ACCOUNT_ID`
   (cu sau fără prefixul `act_`, codul îl adaugă automat dacă lipsește).

### Statistici pe formate de video

```bash
PYTHONPATH=src python3 -m travel_ugc.meta_ads.cli stats --days 30
```

Afișează un clasament al **formatelor** (nu al reclamelor individuale) după
cost per rezultat, hook rate (% care au văzut peste 25% din video) și hold
rate (peste 75%) — exact ce ai nevoie ca să vezi ce *tip* de UGC
funcționează, nu doar care reclamă anume.

### Creezi automat o campanie nouă

```bash
PYTHONPATH=src python3 -m travel_ugc.meta_ads.cli create-campaign --trip config/trips/2026-07-25-excursie-manastiri.yaml
```

- Încarcă automat videoclipul generat la pasul 3.
- Creează Campanie → Ad Set → Creative → Ad.
- Dacă există deja reclame pe același `format_tag`, preia ca referință cea cu
  cel mai bun cost per rezultat.
- **Campania e creată implicit PAUSED** — o activezi manual din Meta Ads
  Manager după ce verifici targetarea/bugetul, ca să nu se cheltuiască buget
  real fără supervizare. Adaugă `--activate` doar când ești sigur.

## 6. Dashboard-ul pe internet (Render)

[![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy?repo=https://github.com/rapphaelai/travel/tree/claude/elevenabs-ugc-meta-ads-4qvosw)

1. Apeși butonul de mai sus (te duce la Render, îți cere să conectezi contul GitHub dacă nu e deja).
2. Render citește `render.yaml` din repo și pregătește automat serviciul (Docker, ffmpeg inclus), pe **planul gratuit ("Free")** -- fără card, fără cost.
3. La pasul de configurare, îți cere valoarea pentru **`ELEVENLABS_API_KEY`** -- o pui acolo (nu ajunge niciodată în git, se salvează doar ca secret în Render).
4. Deploy. Primești un URL public de tip `https://raphael-travel-ugc-dashboard.onrender.com` -- ăla e dashboard-ul tău, accesibil de oriunde.

**Limitările planului gratuit, ca să știi la ce să te aștepți:**
- **Adoarme din inactivitate**: dacă nu-l accesezi ~15 minute, serverul se oprește; următoarea cerere îl trezește, dar durează 30-60 secunde prima încărcare. Normal, nu e o eroare.
- **Fără disc persistent**: contextele excursiilor și video-urile generate trăiesc doar în storage-ul containerului. Rămân acolo cât timp serviciul e "treaz" (inclusiv după ce adoarme și se trezește), dar **se pierd la fiecare redeploy sau restart manual**. Descarcă video-urile importante imediat după generare, nu te baza pe dashboard ca arhivă permanentă.
- Dacă la un moment dat vrei persistență reală între redeploy-uri, treci serviciul pe planul **Starter** (~7$/lună) din Render și adaugă-i un disc -- spune-mi și îți pun eu configul înapoi.
- N-am putut testa build-ul Docker chiar aici (acest mediu de lucru nu permite Docker-in-Docker), dar fiecare pas din `Dockerfile` (Python 3.11-slim, `apt-get install ffmpeg`, `pip install -r requirements.txt`) e identic cu ce am rulat deja cu succes direct în acest sandbox -- verifică doar log-ul primului deploy din Render ca să confirmi.
- Butonul de mai sus pornește deploy-ul din branch-ul curent (`claude/elevenabs-ugc-meta-ads-4qvosw`). După ce faci merge pe branch-ul principal, poți schimba branch-ul serviciului din Render (Settings -> Branch) sau redeploya de acolo.

## 7. Dashboard web (local, gratis -- recomandat)

Pe lângă CLI, există un dashboard local unde adaugi contextul unei excursii
prin formular, primești automat **7 variante de prompt video** (unghiuri de
copywriting diferite: urgență, dovadă socială, storytelling, problemă →
soluție, scarcitate, practic, invitație caldă), poți edita orice variantă,
apoi ceri **4 generări video** (implicit `veo-3.1-fast-generate-001`, 8
secunde, 9:16, audio inclus) pentru varianta aleasă -- fiecare rezultat
primește automat banner-ul text. La final, generezi și **câmpurile de Meta
Ads** (4 variante de text principal, 4 titluri, 3 descrieri ale apelului),
fără linii de pauză (em/en dash), gata de copy-paste în Ads Manager.

### Completare automată din text liber (opțional)

În loc să completezi cele ~15 câmpuri ale formularului unul câte unul, poți
lipi un text liber (exact cum ai descrie excursia într-o conversație
normală) în caseta **"Lipește text liber"** de deasupra formularului și apeși
**"Extrage detaliile automat"** -- Claude extrage datele (dată, preț,
obiectiv, regiune etc.) și pre-completează formularul. Tot le mai poți
verifica/corecta înainte de a salva -- extragerea automată nu sare peste
pasul de revizuire, fiindcă datele de pe banner trebuie să fie exacte.

Necesită o cheie separată **`ANTHROPIC_API_KEY`** în `.env` (cont de pe
[console.anthropic.com](https://console.anthropic.com) -> API Keys). E
opțională -- fără ea, restul dashboard-ului (formular manual, prompturi,
video, Meta Ads) funcționează normal, doar acest buton nu merge.

### Pornire cu un singur script (recomandat)

- **Windows**: dublu-clic pe `scripts\start_dashboard.bat`
- **Mac/Linux**: `./scripts/start_dashboard.sh` (prima dată: `chmod +x scripts/start_dashboard.sh`)

Scriptul face totul singur: creează mediul Python (`.venv`), instalează
dependințele, verifică ffmpeg, creează `.env` din `.env.example` dacă
lipsește și te oprește să completezi cheia ElevenLabs înainte de a porni
(nu trebuie s-o mai pui manual în linia de comandă de fiecare dată -- o
citește automat din `.env` la fiecare rulare). La final deschide singur
`http://localhost:8000` în browser.

Rulează gratuit, pe discul tău -- fără sleep, fără să-ți piardă datele la
redeploy (spre deosebire de planul gratuit Render de mai sus).

### Pornire manuală (dacă nu vrei să folosești scriptul)

```bash
PYTHONPATH=src uvicorn travel_ugc.web.app:app --port 8000
```
(citește tot din `.env` automat, la fel ca scriptul)

Deschizi apoi [http://localhost:8000](http://localhost:8000). Poți încărca
opțional o poză de referință a prezentatorului (persoana din materialele
tale) -- e trimisă către ElevenLabs ca imagine de referință, ca subiectul să
rămână vizual consistent între cele 4 variante generate.

Datele fiecărei excursii (context, prompturi, joburi) se salvează local în
`data/contexts/*.json`, iar video-urile generate în `assets/output/web/` --
ambele foldere sunt în `.gitignore`, nu ajung în git.

**Notă**: motorul de prompturi și de texte Meta Ads nu apelează niciun LLM
extern -- sunt șabloane completate din câmpurile formularului. Verifică
mereu prompturile generate înainte să apeși "Generează video-uri" (poți
edita direct în căsuța de text), mai ales câmpurile de regiune/obiectiv, ca
să sune natural în propoziție.

## 8. Fluxul complet, per excursie nouă (CLI)

```bash
# 1. adaugi config/trips/noua-excursie.yaml + pozele/videoclipul în assets/footage/
# 2. generezi videoclipul UGC
PYTHONPATH=src python3 -m travel_ugc.pipeline --trip config/trips/noua-excursie.yaml
# 3. verifici clasamentul de formate ca sa stii daca merge sa refolosesti reteta
PYTHONPATH=src python3 -m travel_ugc.meta_ads.cli stats
# 4. creezi campania (PAUSED) si o activezi manual dupa verificare
PYTHONPATH=src python3 -m travel_ugc.meta_ads.cli create-campaign --trip config/trips/noua-excursie.yaml
```

## Ce nu e inclus (etapa următoare)

- **Trigger complet automat** (ex: "adaugi fișierul YAML, totul rulează
  singur fără nicio comandă") — momentan pornești manual comenzile de mai
  sus; se poate adăuga un GitHub Actions workflow care rulează pipeline-ul
  la fiecare push pe `config/trips/`, dacă vrei asta.
- **Generare video/imagini AI pentru footage-ul brut** — momentan pipeline-ul
  suprapune banner-ul peste poze/video pe care le pui tu în
  `assets/footage/`; generarea propriu-zisă a scenelor video cu AI e un pas
  separat (ex: Higgsfield, disponibil în acest mediu ca unealtă conectată).
- **Dashboard vizual** pentru statisticile Meta Ads — acum e CLI text; se
  poate adăuga un raport HTML dacă e util.
