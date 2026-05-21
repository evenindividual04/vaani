# Vaani — Multilingual FNOL Voice Agent

Vaani is an enterprise-grade AI voice agent for insurance First Notice of Loss (FNOL) operations. It handles inbound calls in Hindi and English, extracts structured incident data in real time, and streams everything to a tactical operator dashboard.

---

## What it does

A caller reports a car accident or theft. Vaani:
1. Transcribes their speech (Sarvam AI STT, Hindi + English)
2. Drives the conversation through a deterministic FSM — greeting → policy verification → incident capture → close
3. Extracts structured FNOL fields (policy number, incident type, date, location, injuries, vehicle damage, callback number) using Groq LLaMA 3.3 70B
4. Synthesizes a natural-language response and streams audio back (Sarvam AI TTS)
5. Pushes live transcript, FNOL completeness, and latency metrics to the operator dashboard over WebSocket

If Groq is down, Gemini 2.0 Flash takes over automatically via circuit breaker fallback.

---

## Tech stack

| Layer | Technology |
|---|---|
| Backend | FastAPI (async), Python 3.12, SQLAlchemy 2 + Alembic |
| STT | Sarvam AI `saarika:v2.5` |
| LLM | Groq `llama-3.3-70b-versatile` → Gemini `gemini-2.0-flash` fallback |
| TTS | Sarvam AI `bulbul:v2` (parallel sentence batching) |
| Frontend | Next.js 15, Tailwind CSS, Zustand, Recharts, Monaco Editor |
| Reliability | Circuit breaker per provider, FSM guardrails, VAD (Silero) |
| Observability | Prometheus + Grafana dashboards, structlog JSON |
| Telephony | Twilio (phone), WhatsApp Business API |
| Auth | JWT (RS256), per-scope enforcement |
| Testing | pytest-asyncio, 111 tests, all green |

---

## Dashboard pages

- **Live Calls** — real-time WebSocket feed, FNOL card updates as caller speaks
- **Call History** — paginated log with channel/outcome filters, soft delete, audio replay
- **Metrics** — latency charts (STT/LLM/TTS P50/P95), provider health, fallback rate
- **Prompts** — version CRUD, one-click deploy, side-by-side diff, rollback
- **Eval** — run the 15-scenario regression suite against any prompt version

---

## Quickstart

### Prerequisites
- Python 3.12+
- Node.js 18+
- API keys: [Sarvam AI](https://console.sarvam.ai), [Groq](https://console.groq.com/keys), [Google AI Studio](https://aistudio.google.com/apikey)

### 1. Clone and configure

```bash
git clone https://github.com/your-org/vaani.git
cd vaani

# Copy the example env and fill in your keys
cp .env.example backend/.env
# Edit backend/.env — add SARVAM_API_KEY, GROQ_API_KEY, GOOGLE_API_KEY,
# a random JWT_SECRET_KEY, and an ADMIN_PASSWORD
```

Generate a JWT secret:
```bash
python3 -c "import secrets; print(secrets.token_hex(32))"
```

### 2. Backend

```bash
cd backend
python3.12 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Create DB tables
alembic upgrade head

# (Optional) seed demo data
python scripts/seed.py

# Start
uvicorn app.main:app --reload --port 8000
```

API docs at [http://localhost:8000/docs](http://localhost:8000/docs)

### 3. Frontend

```bash
cd frontend
npm install
npm run dev
```

Dashboard at [http://localhost:3000](http://localhost:3000)

Login: `admin` / your `ADMIN_PASSWORD` from `.env`

### 4. Full stack with Docker

```bash
docker compose up
```

| Service | URL |
|---|---|
| Dashboard | http://localhost:3000 |
| API + docs | http://localhost:8000/docs |
| Prometheus | http://localhost:9090 |
| Grafana | http://localhost:3001 (admin / admin) |

---

## Running tests

```bash
cd backend
PYTHONPATH=. pytest tests/ -v
```

111 tests, all green. Covers circuit breaker, FSM, FNOL extractor, all API endpoints, pipeline stages, and eval runner.

---

## Project structure

```
vaani/
├── backend/
│   ├── app/
│   │   ├── api/          # REST endpoints (auth, calls, prompts, diagnostics, eval)
│   │   ├── channels/     # WebSocket, Twilio, WhatsApp handlers
│   │   ├── domain/       # FSM, FNOL extractor, prompt loader, validator
│   │   ├── pipeline/     # STT → LLM → TTS orchestrator, circuit breaker, VAD
│   │   └── storage/      # SQLAlchemy models, Alembic migrations
│   ├── migrations/       # Alembic version files
│   ├── scripts/          # seed.py, etc.
│   └── tests/            # 111 pytest tests
├── frontend/
│   └── src/
│       ├── app/          # Next.js 15 pages (calls, metrics, prompts, eval)
│       ├── components/   # LiveCallPanel, FNOLRecord, LatencyChart, ...
│       ├── hooks/        # useCallWebSocket, useWaveform
│       └── store/        # callStore (Zustand)
└── docker-compose.yml
```

---

## Architecture notes

**Circuit breaker** — each provider (Sarvam STT, Groq, Gemini, Sarvam TTS) has its own circuit breaker. After 3 consecutive errors it opens for 60 seconds; after 3 open cycles it disables permanently and pages via Prometheus alert.

**FSM** — the conversation is driven by a 7-state machine (GREETING → POLICY_VERIFICATION → INCIDENT_CAPTURE → DETAIL_COLLECTION → CALLBACK_COLLECTION → SUMMARY_CONFIRMATION → CLOSED). LLM responses that try to skip states are rejected and re-routed.

**Eval suite** — 15 scripted scenarios (Hindi/English, clean/noisy, partial/complete FNOLs) can be run against any prompt version. Results are stored and diffed against a baseline to catch regressions before deploying prompt changes.

---

## Channels

| Channel | Transport | Status |
|---|---|---|
| Browser (demo) | WebSocket + PCM audio | Ready |
| Phone | Twilio Media Streams | Ready |
| WhatsApp | Twilio WhatsApp API | Ready (text-only) |
