# Imagine pentru dashboard-ul UGC Raphael Travel (FastAPI + ffmpeg).
# Ruleaza pe Render (vezi render.yaml) sau orice alt host care porneste
# containere Docker standard.

FROM python:3.11-slim

# ffmpeg (asamblare video) -- fara pachete recomandate, sa ramana imaginea mica.
RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Directoare de date/output -- create la runtime oricum de storage.py, dar le
# pregatim explicit pentru cazul unui volum persistent montat peste ele.
RUN mkdir -p data/contexts data/media

ENV PYTHONPATH=/app/src
ENV PORT=8000
EXPOSE 8000

# Render seteaza $PORT dinamic; alte platforme pot lasa valoarea implicita de mai sus.
CMD ["sh", "-c", "uvicorn travel_ugc.web.app:app --host 0.0.0.0 --port ${PORT}"]
