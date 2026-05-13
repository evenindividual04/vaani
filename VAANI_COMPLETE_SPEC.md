# VAANI — Complete Project Specification & Implementation Plan
## Multilingual FNOL Voice Agent | Flagship Production Build

**Version**: 1.0  
**Target**: Sarvam AI — FDSE, Backend Inference, Backend General, Frontend  
**Stack**: FastAPI + Next.js 15 + Sarvam APIs + Groq + Prometheus + Grafana  
**Deployment**: Docker Compose (local) + Railway (cloud)

---

## Table of Contents

1. [Project Overview](#1-project-overview)
2. [Architecture](#2-architecture)
3. [Tech Stack & Justifications](#3-tech-stack--justifications)
4. [Repository Structure](#4-repository-structure)
5. [Environment Variables](#5-environment-variables)
6. [API Contracts](#6-api-contracts)
7. [WebSocket Message Protocol](#7-websocket-message-protocol)
8. [Sarvam API Reference](#8-sarvam-api-reference)
9. [Twilio Audio Handling](#9-twilio-audio-handling)
10. [Database Schema](#10-database-schema)
11. [Domain Logic Specs](#11-domain-logic-specs)
12. [Inference Pipeline Specs](#12-inference-pipeline-specs)
13. [Observability Specs](#13-observability-specs)
14. [Eval Suite Specs](#14-eval-suite-specs)
15. [Frontend Design & Component Specs](#15-frontend-design--component-specs)
16. [Testing Strategy](#16-testing-strategy)
17. [Docker & Deployment](#17-docker--deployment)
18. [Implementation Plan — Phase by Phase](#18-implementation-plan--phase-by-phase)
19. [Resume Bullets](#19-resume-bullets)

---

## 1. Project Overview

### What It Is

Vaani is a production-grade multilingual voice agent for insurance First Notice of Loss (FNOL). It handles inbound calls from policyholders in Hindi, English, and Hinglish, extracts structured claim data through natural conversation, and produces a validated FNOL record. It serves as a production reference architecture for Sarvam AI's core deployment pattern: Indian-language voice AI integrated into enterprise client workflows.

### Why FNOL

Sarvam's named clients — SBI Life, LIC, Tata Capital, IDFC — all have FNOL as an explicit use case. FNOL calls are structured enough to build a reliable agent (fixed required fields) but conversational enough to require genuine NLU and FSM management. A hiring manager at Sarvam who sees "FNOL agent for insurance clients" reads it as pre-sales work, not a portfolio project.

### Four Resume Stories From One Project

| Role | What They See |
|------|---------------|
| FDSE | End-to-end deployed conversational AI across 3 channels, structured client deliverable (FNOL JSON), prompt management, monitoring, and regression testing |
| Backend - Inference Pipelines | Instrumented STT→LLM→TTS pipeline with per-stage Prometheus metrics, circuit breaker with provider fallback, parallel batch TTS, /diagnostics API |
| Backend - General | FastAPI with 25+ REST endpoints, JWT auth, rate limiting, audit log, async SQLite, 60+ pytest tests, Docker |
| Frontend | Next.js 15 + TypeScript ops dashboard: real-time WebSocket call monitor, Web Audio API waveform, pipeline latency viz, conversation replay, prompt management UI |

---

## 2. Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                          CHANNEL LAYER                               │
│                                                                      │
│   ┌──────────────┐   ┌─────────────────┐   ┌────────────────────┐  │
│   │ Twilio Voice │   │ Browser WebSocket│   │  WhatsApp Webhook  │  │
│   │ (phone calls)│   │  (web client)   │   │  (text + audio)    │  │
│   └──────┬───────┘   └────────┬────────┘   └─────────┬──────────┘  │
└──────────┼────────────────────┼─────────────────────┼──────────────┘
           │                    │                     │
           └────────────────────┴─────────────────────┘
                                │
                    ┌───────────▼───────────┐
                    │   AUDIO PROCESSING    │
                    │  Silero VAD           │
                    │  μ-law→PCM conversion │
                    │  Streaming buffer     │
                    │  300ms chunk assembly │
                    └───────────┬───────────┘
                                │
          ┌─────────────────────▼──────────────────────┐
          │          INFERENCE PIPELINE                  │
          │                                              │
          │  ┌──────────┐  ┌──────────┐  ┌──────────┐  │
          │  │   STT    │→ │   LLM    │→ │   TTS    │  │
          │  │ Sarvam   │  │  Groq    │  │ Sarvam   │  │
          │  │Saarika   │  │Llama 3.3 │  │ Bulbul   │  │
          │  │  v2.5    │  │  70B     │  │   v2     │  │
          │  └──────────┘  └──────────┘  └──────────┘  │
          │                                              │
          │  Per-stage: latency_ms, errors, provider    │
          │  Circuit breaker per provider               │
          │  Fallback: Gemini Flash / gTTS              │
          │  Parallel batch TTS queue                   │
          │  Prometheus metrics on every call           │
          └─────────────────┬──────────────────────────┘
                            │
          ┌─────────────────▼──────────────────────────┐
          │            DOMAIN LOGIC                      │
          │                                              │
          │  Language Detection → Prompt Routing        │
          │  Conversation FSM (7 states)                │
          │  FNOL Extractor (JSON-constrained LLM)      │
          │  Completeness Validator                     │
          └─────────────────┬──────────────────────────┘
                            │
          ┌─────────────────▼──────────────────────────┐
          │             FASTAPI LAYER                    │
          │                                              │
          │  /voice  /ws  /webhook  /calls              │
          │  /prompts  /eval  /diagnostics  /auth       │
          │  /metrics (Prometheus scrape)               │
          │                                              │
          │  JWT auth │ Rate limiting │ Audit log       │
          └─────────────────┬──────────────────────────┘
                            │
          ┌─────────────────▼──────────────────────────┐
          │           OBSERVABILITY LAYER                │
          │                                              │
          │  Prometheus → Grafana (3 dashboards)        │
          │  Langfuse (LLM tracing)                     │
          │  Structlog (JSON structured logs)           │
          │  SQLite artifacts per call                  │
          └─────────────────┬──────────────────────────┘
                            │
          ┌─────────────────▼──────────────────────────┐
          │          NEXT.JS FRONTEND                    │
          │                                              │
          │  Live call dashboard (WebSocket)            │
          │  Waveform + pipeline latency viz            │
          │  Conversation replay                        │
          │  Prompt management + diff/deploy            │
          │  Regression test runner + results           │
          └─────────────────────────────────────────────┘
```

---

## 3. Tech Stack & Justifications

### Backend

| Package | Version | Purpose | Why |
|---------|---------|---------|-----|
| fastapi | 0.115+ | Web framework | Async-native, WebSocket support, auto OpenAPI |
| uvicorn | 0.30+ | ASGI server | Production-grade, supports ws |
| sarvamai | latest | Sarvam STT/TTS | Official SDK, wraps auth + retry |
| groq | 0.9+ | LLM primary | Free tier, 14,400 req/day, Llama 3.3 70B |
| google-generativeai | 0.7+ | LLM fallback | Free tier Gemini Flash |
| silero-vad | latest | Voice activity detection | Accurate, runs locally, no API cost |
| prometheus-client | 0.20+ | Metrics | Industry standard, Grafana-compatible |
| langfuse | 2.0+ | LLM tracing | Free cloud tier, per-call trace |
| structlog | 24.0+ | Structured logging | JSON logs, context binding per call |
| sqlalchemy | 2.0+ | ORM | Async support, type-safe |
| aiosqlite | 0.20+ | Async SQLite driver | Free, no infra needed |
| alembic | 1.13+ | DB migrations | Schema versioning |
| pydantic | 2.0+ | Validation + settings | JSON-constrained LLM output parsing |
| pydantic-settings | 2.0+ | Config from env | 12-factor app |
| python-jose | 3.3+ | JWT | Auth tokens |
| slowapi | 0.1+ | Rate limiting | FastAPI-native |
| pytest | 8.0+ | Testing | Industry standard |
| pytest-asyncio | 0.23+ | Async tests | Required for FastAPI testing |
| httpx | 0.27+ | Test HTTP client | FastAPI TestClient async support |
| twilio | 9.0+ | Telephony | Twilio Media Streams |
| audioop-lts | latest | Audio conversion | μ-law↔PCM (stdlib audioop deprecated in 3.13) |

### Frontend

| Package | Version | Purpose |
|---------|---------|---------|
| next | 15.x | Framework, App Router |
| react | 19.x | UI |
| typescript | 5.x | Type safety |
| tailwindcss | 3.x | Styling |
| recharts | 2.x | Charts (pipeline latency, metrics) |
| @monaco-editor/react | 4.x | Prompt editor with syntax highlight |
| diff | 5.x | Prompt version diffing |
| zustand | 4.x | Global state (active calls, ws) |
| swr | 2.x | Data fetching + revalidation |
| framer-motion | 11.x | Animations |
| date-fns | 3.x | Timestamp formatting |

---

## 4. Repository Structure

```
vaani/
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py
│   │   ├── config.py
│   │   │
│   │   ├── channels/
│   │   │   ├── __init__.py
│   │   │   ├── twilio_handler.py
│   │   │   ├── websocket_handler.py
│   │   │   └── whatsapp_handler.py
│   │   │
│   │   ├── pipeline/
│   │   │   ├── __init__.py
│   │   │   ├── orchestrator.py
│   │   │   ├── stt.py
│   │   │   ├── llm.py
│   │   │   ├── tts.py
│   │   │   ├── vad.py
│   │   │   ├── circuit_breaker.py
│   │   │   └── metrics.py
│   │   │
│   │   ├── domain/
│   │   │   ├── __init__.py
│   │   │   ├── fsm.py
│   │   │   ├── extractor.py
│   │   │   ├── validator.py
│   │   │   ├── language.py
│   │   │   └── prompts/
│   │   │       ├── __init__.py
│   │   │       ├── loader.py
│   │   │       └── templates/
│   │   │           ├── v1/
│   │   │           │   ├── greeting_hi.txt
│   │   │           │   ├── greeting_en.txt
│   │   │           │   ├── policy_verify_hi.txt
│   │   │           │   ├── policy_verify_en.txt
│   │   │           │   ├── incident_capture_hi.txt
│   │   │           │   ├── incident_capture_en.txt
│   │   │           │   ├── details_capture_hi.txt
│   │   │           │   ├── details_capture_en.txt
│   │   │           │   ├── summary_hi.txt
│   │   │           │   ├── summary_en.txt
│   │   │           │   └── extractor_system.txt
│   │   │           └── v2/               (created after first eval run)
│   │   │
│   │   ├── api/
│   │   │   ├── __init__.py
│   │   │   ├── router.py
│   │   │   ├── calls.py
│   │   │   ├── prompts.py
│   │   │   ├── eval.py
│   │   │   ├── diagnostics.py
│   │   │   └── auth.py
│   │   │
│   │   ├── storage/
│   │   │   ├── __init__.py
│   │   │   ├── database.py
│   │   │   ├── models.py
│   │   │   ├── call_store.py
│   │   │   └── audit_log.py
│   │   │
│   │   └── eval/
│   │       ├── __init__.py
│   │       ├── scenarios.py
│   │       ├── runner.py
│   │       └── reporter.py
│   │
│   ├── tests/
│   │   ├── conftest.py
│   │   ├── test_pipeline_stt.py
│   │   ├── test_pipeline_llm.py
│   │   ├── test_pipeline_tts.py
│   │   ├── test_pipeline_orchestrator.py
│   │   ├── test_circuit_breaker.py
│   │   ├── test_domain_fsm.py
│   │   ├── test_domain_extractor.py
│   │   ├── test_domain_validator.py
│   │   ├── test_api_calls.py
│   │   ├── test_api_auth.py
│   │   ├── test_api_prompts.py
│   │   ├── test_api_diagnostics.py
│   │   └── test_eval_runner.py
│   │
│   ├── migrations/
│   │   ├── env.py
│   │   └── versions/
│   │
│   ├── prometheus/
│   │   └── prometheus.yml
│   │
│   ├── grafana/
│   │   ├── provisioning/
│   │   │   ├── datasources/
│   │   │   │   └── prometheus.yml
│   │   │   └── dashboards/
│   │   │       └── dashboards.yml
│   │   └── dashboards/
│   │       ├── pipeline_health.json
│   │       ├── call_analytics.json
│   │       └── fnol_accuracy.json
│   │
│   ├── Dockerfile
│   ├── requirements.txt
│   └── pyproject.toml
│
├── frontend/
│   ├── src/
│   │   ├── app/
│   │   │   ├── layout.tsx
│   │   │   ├── page.tsx                  (live dashboard)
│   │   │   ├── calls/
│   │   │   │   ├── page.tsx              (call history)
│   │   │   │   └── [id]/
│   │   │   │       └── page.tsx          (replay)
│   │   │   ├── metrics/
│   │   │   │   └── page.tsx
│   │   │   ├── prompts/
│   │   │   │   └── page.tsx
│   │   │   └── eval/
│   │   │       └── page.tsx
│   │   │
│   │   ├── components/
│   │   │   ├── layout/
│   │   │   │   ├── Sidebar.tsx
│   │   │   │   └── TopBar.tsx
│   │   │   ├── calls/
│   │   │   │   ├── LiveCallPanel.tsx
│   │   │   │   ├── CallCard.tsx
│   │   │   │   └── CallHistoryTable.tsx
│   │   │   ├── pipeline/
│   │   │   │   ├── PipelineStages.tsx
│   │   │   │   └── ProviderHealth.tsx
│   │   │   ├── audio/
│   │   │   │   ├── WaveformVisualizer.tsx
│   │   │   │   └── AudioPlayer.tsx
│   │   │   ├── fnol/
│   │   │   │   ├── FNOLRecord.tsx
│   │   │   │   └── CompletenessBar.tsx
│   │   │   ├── replay/
│   │   │   │   └── ConversationReplay.tsx
│   │   │   ├── prompts/
│   │   │   │   ├── PromptEditor.tsx
│   │   │   │   └── VersionDiff.tsx
│   │   │   └── eval/
│   │   │       ├── RegressionRunner.tsx
│   │   │       └── ScenarioResultCard.tsx
│   │   │
│   │   ├── hooks/
│   │   │   ├── useCallWebSocket.ts
│   │   │   ├── useWaveform.ts
│   │   │   ├── useAudioPlayer.ts
│   │   │   └── useMetrics.ts
│   │   │
│   │   ├── store/
│   │   │   ├── callStore.ts
│   │   │   └── uiStore.ts
│   │   │
│   │   ├── lib/
│   │   │   ├── api.ts
│   │   │   ├── types.ts
│   │   │   └── utils.ts
│   │   │
│   │   └── styles/
│   │       └── globals.css
│   │
│   ├── public/
│   ├── Dockerfile
│   ├── package.json
│   ├── tsconfig.json
│   └── tailwind.config.ts
│
├── docker-compose.yml
├── docker-compose.dev.yml
├── .env.example
├── .env                              (gitignored)
├── Makefile
└── README.md
```

---

## 5. Environment Variables

### `.env.example`

```bash
# ─── Sarvam AI ────────────────────────────────────────────────────────────────
SARVAM_API_KEY=                        # From https://dashboard.sarvam.ai
SARVAM_STT_MODEL=saarika:v2.5
SARVAM_TTS_MODEL=bulbul:v2
SARVAM_TTS_SPEAKER=meera              # meera | pavithra | arvind | kalpana

# ─── LLM Providers ────────────────────────────────────────────────────────────
GROQ_API_KEY=                          # From https://console.groq.com
GROQ_MODEL=llama-3.3-70b-versatile
GOOGLE_API_KEY=                        # From https://aistudio.google.com
GEMINI_MODEL=gemini-2.0-flash-exp

# ─── Langfuse (LLM Tracing) ───────────────────────────────────────────────────
LANGFUSE_PUBLIC_KEY=
LANGFUSE_SECRET_KEY=
LANGFUSE_HOST=https://cloud.langfuse.com

# ─── Twilio ────────────────────────────────────────────────────────────────────
TWILIO_ACCOUNT_SID=
TWILIO_AUTH_TOKEN=
TWILIO_PHONE_NUMBER=                   # E.164 format: +1XXXXXXXXXX
TWILIO_WHATSAPP_NUMBER=whatsapp:+14155238886  # Sandbox number

# ─── Auth ─────────────────────────────────────────────────────────────────────
JWT_SECRET_KEY=                        # Generate: openssl rand -hex 32
JWT_ALGORITHM=HS256
JWT_EXPIRY_MINUTES=60
ADMIN_USERNAME=admin
ADMIN_PASSWORD=                        # Hash with bcrypt before storing

# ─── App ──────────────────────────────────────────────────────────────────────
DATABASE_URL=sqlite+aiosqlite:///./vaani.db
AUDIO_STORAGE_DIR=./audio_artifacts
LOG_LEVEL=INFO
LOG_FORMAT=json                        # json | console
ENVIRONMENT=development               # development | production

# ─── Pipeline Tuning ──────────────────────────────────────────────────────────
ACTIVE_PROMPT_VERSION=v1
MAX_CONCURRENT_CALLS=10
STT_BUFFER_MS=300                     # Audio buffer before sending to STT
VAD_THRESHOLD=0.5                     # Silero VAD confidence threshold
LANGUAGE_DETECTION_TURNS=1           # How many turns before locking language

# ─── Circuit Breaker ──────────────────────────────────────────────────────────
CB_ERROR_THRESHOLD=3                  # Consecutive errors → cooling_down
CB_COOLDOWN_SECONDS=60
CB_DISABLE_THRESHOLD=3               # Cooldown cycles without recovery → disabled

# ─── Rate Limiting ────────────────────────────────────────────────────────────
RATE_LIMIT_API=100/minute
RATE_LIMIT_CALLS=30/minute
RATE_LIMIT_AUTH=10/minute

# ─── Frontend ─────────────────────────────────────────────────────────────────
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_WS_URL=ws://localhost:8000
```

---

## 6. API Contracts

All routes require `Authorization: Bearer <token>` except `/auth/login`, `/voice/*`, `/webhook/*`, and `/metrics`.

### Auth

```
POST /auth/login
  body:  { username: str, password: str }
  200:   { access_token: str, token_type: "bearer", expires_in: int }
  401:   { detail: "Invalid credentials" }

POST /auth/refresh
  header: Authorization: Bearer <token>
  200:   { access_token: str }

POST /auth/revoke
  header: Authorization: Bearer <token>
  204:   (no content)
```

### Calls

```
GET /calls
  query: page=1, page_size=20, channel=phone|web|whatsapp,
         language=hi-IN|en-IN, outcome=complete|abandoned|error,
         date_from=ISO8601, date_to=ISO8601
  200: {
    items: CallSummary[],
    total: int,
    page: int,
    page_size: int
  }

GET /calls/{call_id}
  200: {
    call_id: str,
    channel: str,
    language: str,
    started_at: datetime,
    ended_at: datetime | null,
    duration_seconds: float | null,
    outcome: str,
    transcript: Turn[],
    fnol_record: FNOLRecord | null,
    pipeline_metrics: PipelineMetrics,
    prompt_version: str,
    audio_available: bool
  }

GET /calls/{call_id}/audio
  200: audio/wav binary stream
  404: { detail: "Audio not available for web channel" }

GET /calls/{call_id}/replay
  200: {
    transcript: Turn[],
    per_turn_metrics: TurnMetrics[],
    fnol_snapshots: FNOLSnapshot[],   // FNOL state after each turn
    fsm_trace: FsmTransition[],
    final_fnol: FNOLRecord | null
  }

DELETE /calls/{call_id}
  204: (soft delete, audit log entry created)
```

### Prompts

```
GET /prompts
  200: {
    versions: PromptVersion[],
    active_version: str
  }

POST /prompts
  body: {
    version_id: str,        // e.g. "v2"
    description: str,
    templates: {            // map of state_language → prompt text
      greeting_hi: str,
      greeting_en: str,
      ...
      extractor_system: str
    }
  }
  201: PromptVersion

GET /prompts/{version_id}
  200: PromptVersion (full templates included)

POST /prompts/{version_id}/deploy
  body: { confirm: true }
  200: { active_version: str, deployed_at: datetime }

GET /prompts/diff/{version_a}/{version_b}
  200: {
    diffs: {
      [template_key]: {
        a: str,
        b: str,
        unified_diff: str
      }
    }
  }

POST /prompts/{version_id}/rollback
  200: { active_version: str, rolled_back_from: str }
```

### Diagnostics

```
GET /diagnostics
  200: {
    timestamp: datetime,
    pipeline: {
      stt: StageHealth,
      llm: StageHealth,
      tts: StageHealth
    },
    active_calls: int,
    calls_last_1h: int,
    calls_last_24h: int,
    fnol_completion_rate_1h: float,
    avg_call_duration_1h: float,
    fallback_rate_1h: float,
    providers: {
      groq: ProviderStatus,
      gemini: ProviderStatus,
      sarvam_stt: ProviderStatus,
      sarvam_tts: ProviderStatus
    }
  }

# StageHealth:
{
  provider: str,
  status: "healthy" | "cooling_down" | "disabled",
  p50_ms: float,
  p95_ms: float,
  p99_ms: float,
  error_rate_1h: float,
  last_error: str | null
}
```

### Eval

```
POST /eval/runs
  body: {
    prompt_version_id: str,
    scenario_ids: list[str] | "all",
    baseline_version_id: str | null   // compare against this version
  }
  202: { run_id: str, status: "queued" }

GET /eval/runs
  200: EvalRunSummary[]

GET /eval/runs/{run_id}
  200: {
    run_id: str,
    prompt_version_id: str,
    status: "queued" | "running" | "complete" | "failed",
    started_at: datetime,
    completed_at: datetime | null,
    summary: {
      total_scenarios: int,
      passed: int,
      failed: int,
      overall_accuracy: float,
      per_field_accuracy: dict[str, float],
      baseline_delta: dict[str, float] | null
    },
    scenario_results: ScenarioResult[]
  }

GET /eval/runs/{run_id}/report
  200: text/markdown — formatted accuracy report
```

### Channels

```
POST /voice/incoming
  (Twilio webhook — TwiML response)
  No auth required, Twilio signature validated

WebSocket /voice/stream
  (Twilio Media Streams — upgradeConnection)
  No auth required, validated via call SID

POST /voice/status
  (Twilio call status callback)

POST /webhook/whatsapp
  (Twilio WhatsApp webhook)

WebSocket /ws/call
  (Browser WebSocket channel)
  query: ?token=<jwt>

WebSocket /ws/live
  (Frontend monitoring — live call events broadcast)
  query: ?token=<jwt>
```

---

## 7. WebSocket Message Protocol

All messages are JSON. Every message has `type` and `call_id` fields.

### Backend → Frontend (via `/ws/live`)

```typescript
// New call started
{
  type: "call_started",
  call_id: string,
  channel: "phone" | "web" | "whatsapp",
  language: string,          // initial detection, may update
  started_at: string         // ISO8601
}

// New transcript turn completed
{
  type: "transcript_turn",
  call_id: string,
  turn_index: number,
  speaker: "user" | "agent",
  text: string,
  language: string,
  timestamp_ms: number       // ms since call start
}

// Pipeline metrics after each agent turn
{
  type: "pipeline_metrics",
  call_id: string,
  turn_index: number,
  stt_ms: number,
  llm_ms: number,
  llm_ttft_ms: number,
  tts_ms: number,
  total_ms: number,
  providers: {
    stt: string,
    llm: string,
    tts: string
  },
  fallback_triggered: boolean
}

// FNOL extraction update after each user turn
{
  type: "fnol_update",
  call_id: string,
  fields: Partial<FNOLRecord>,     // only newly extracted fields
  completeness_score: number,      // 0-1
  missing_fields: string[]
}

// FSM state transition
{
  type: "fsm_transition",
  call_id: string,
  from_state: string,
  to_state: string,
  trigger: string
}

// Call ended
{
  type: "call_ended",
  call_id: string,
  outcome: "complete" | "abandoned" | "error" | "timeout",
  duration_seconds: number,
  fnol_complete: boolean
}

// Provider health change
{
  type: "provider_health_change",
  provider: string,
  stage: "stt" | "llm" | "tts",
  old_status: string,
  new_status: string,
  timestamp: string
}
```

### Browser Client → Backend (via `/ws/call`)

```typescript
// Start a web channel call
{
  type: "start_call",
  language: "hi-IN" | "en-IN" | "auto"
}

// Stream audio chunk (Web Audio API → base64)
{
  type: "audio_chunk",
  call_id: string,
  audio_b64: string,          // base64-encoded PCM 16-bit 16000Hz
  sample_rate: 16000,
  chunk_index: number
}

// End call
{
  type: "end_call",
  call_id: string
}

// Text input (WhatsApp / fallback)
{
  type: "text_input",
  call_id: string,
  text: string
}
```

### Backend → Browser Client (via `/ws/call`)

```typescript
// Call initialized
{
  type: "call_ready",
  call_id: string
}

// Agent audio response
{
  type: "agent_audio",
  call_id: string,
  audio_b64: string,          // base64-encoded WAV
  turn_index: number
}

// Agent text (for WhatsApp or display)
{
  type: "agent_text",
  call_id: string,
  text: string,
  turn_index: number
}

// VAD state
{
  type: "vad_state",
  call_id: string,
  speaking: boolean
}

// Error
{
  type: "error",
  call_id: string,
  code: string,
  message: string
}
```

---

## 8. Sarvam API Reference

**Base URL**: `https://api.sarvam.ai`  
**Auth header**: `api-subscription-key: {SARVAM_API_KEY}`  
**SDK**: `pip install sarvamai` — use the SDK, not raw requests.

### Speech-to-Text

```python
from sarvamai import SarvamAI

client = SarvamAI(api_subscription_key=SARVAM_API_KEY)

# For file-based input
with open("audio.wav", "rb") as f:
    response = client.speech_to_text.transcribe(
        file=("audio.wav", f, "audio/wav"),
        model="saarika:v2.5",
        language_code="hi-IN",      # or "en-IN" or omit for auto-detect
        with_timestamps=False
    )
# response.transcript: str
# response.language_code: str (detected language)
# response.time_taken: float (seconds)

# For bytes input (in-memory)
import io
audio_bytes_io = io.BytesIO(audio_bytes)
audio_bytes_io.name = "audio.wav"
response = client.speech_to_text.transcribe(
    file=audio_bytes_io,
    model="saarika:v2.5"
)
```

**Supported languages**: hi-IN, en-IN, bn-IN, gu-IN, kn-IN, ml-IN, mr-IN, od-IN, pa-IN, ta-IN, te-IN  
**Audio requirements**: WAV format, 16-bit PCM, 16000 Hz mono (convert from other formats before sending)  
**Max audio duration**: 60 seconds per request  
**Free tier**: Generous — check dashboard for current limits

### Text-to-Speech

```python
response = client.text_to_speech.convert(
    text="नमस्ते, मैं आपकी बीमा क्लेम में मदद करूंगा।",
    target_language_code="hi-IN",
    speaker="meera",           # meera | pavithra | arvind | kalpana
    model="bulbul:v2",
    pitch=0,                   # -1.0 to 1.0
    pace=1.0,                  # 0.5 to 2.0
    loudness=1.0               # 0.5 to 2.0
)
# response.audios: list[str]  — base64-encoded WAV strings, one per sentence
# Decode: base64.b64decode(response.audios[0]) → bytes

# For English
response = client.text_to_speech.convert(
    text="Hello, I will help you with your insurance claim.",
    target_language_code="en-IN",
    speaker="meera",
    model="bulbul:v2"
)
```

**Note**: Response gives one audio per sentence. This is the parallel batch opportunity — use `asyncio.gather()` across all sentences in a response.

**Speaker characteristics**:
- `meera`: Female, neutral, clear — best for customer service
- `pavithra`: Female, warm
- `arvind`: Male, professional
- `kalpana`: Female, energetic

### Text Translation (bonus — use in WhatsApp channel)

```python
response = client.translate.translate(
    input="मेरी कार दुर्घटना हो गई",
    source_language_code="hi-IN",
    target_language_code="en-IN",
    model="mayura:v1"
)
# response.translated_text: str
```

---

## 9. Twilio Audio Handling

This is the most implementation-critical section. Get this wrong and the pipeline produces garbage.

### The Format Problem

Twilio Media Streams sends audio as:
- **Encoding**: μ-law (MULAW), 8-bit
- **Sample rate**: 8000 Hz
- **Channels**: Mono
- **Delivery**: Base64-encoded chunks via WebSocket, ~160 bytes each (~20ms audio)

Sarvam STT expects:
- **Encoding**: PCM 16-bit signed little-endian
- **Sample rate**: 16000 Hz
- **Format**: WAV (with header) or raw PCM
- **Minimum duration**: ~300ms for reliable transcription

### Conversion Pipeline

```python
import audioop
import base64
import wave
import io

def convert_twilio_chunk(b64_payload: str) -> bytes:
    """Convert single Twilio μ-law chunk to PCM 16-bit 8kHz"""
    mulaw_bytes = base64.b64decode(b64_payload)
    # audioop.ulaw2lin: μ-law → 16-bit linear PCM at 8kHz
    pcm_8k = audioop.ulaw2lin(mulaw_bytes, 2)  # 2 = 16-bit
    return pcm_8k

def upsample_to_16k(pcm_8k: bytes) -> bytes:
    """Upsample PCM from 8kHz to 16kHz"""
    pcm_16k, _ = audioop.ratecv(
        pcm_8k,
        2,      # sample width (bytes) — 16-bit = 2
        1,      # channels — mono
        8000,   # input rate
        16000,  # output rate
        None    # state (None for first call)
    )
    return pcm_16k

def build_wav_bytes(pcm_data: bytes, sample_rate: int = 16000) -> bytes:
    """Wrap raw PCM in WAV container for Sarvam STT"""
    buf = io.BytesIO()
    with wave.open(buf, 'wb') as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)        # 16-bit = 2 bytes
        wav.setframerate(sample_rate)
        wav.writeframes(pcm_data)
    return buf.getvalue()

# Package: audioop is deprecated in Python 3.13+
# Use: pip install audioop-lts (drop-in replacement)
```

### Buffering Strategy

Do NOT send each 20ms chunk to Sarvam individually. Buffer until:
- VAD detects end of speech (silence after speech), OR
- Buffer reaches 300ms (15 chunks × 20ms), OR
- 10 seconds accumulated (force flush)

```python
class AudioBuffer:
    CHUNK_MS = 20           # Each Twilio chunk is ~20ms
    FLUSH_MS = 300          # Min buffer before STT
    MAX_MS = 10000          # Force flush at 10s
    
    def __init__(self):
        self.chunks: list[bytes] = []
        self.total_ms: int = 0
    
    def add(self, pcm_chunk: bytes) -> bytes | None:
        self.chunks.append(pcm_chunk)
        self.total_ms += self.CHUNK_MS
        
        if self.total_ms >= self.MAX_MS:
            return self.flush()
        return None
    
    def flush(self) -> bytes:
        audio = b"".join(self.chunks)
        self.chunks = []
        self.total_ms = 0
        return build_wav_bytes(audio)
    
    def should_flush_on_silence(self) -> bool:
        return self.total_ms >= self.FLUSH_MS
```

### TwiML Response

```python
from twilio.twiml.voice_response import VoiceResponse, Connect, Stream

def make_stream_twiml(websocket_url: str) -> str:
    response = VoiceResponse()
    connect = Connect()
    connect.stream(url=websocket_url)
    response.append(connect)
    return str(response)
# Returns TwiML XML that tells Twilio to stream audio to our WebSocket
```

### Twilio WebSocket Message Types

Twilio sends these message types over the WebSocket. Handle all of them:

```python
# message["event"] values:
"connected"   → initial connection, contains protocol info
"start"       → stream started, contains callSid, streamSid, customParameters
"media"       → audio chunk, contains payload (base64 mulaw)
"stop"        → call ended
"mark"        → playback marker (for sync)
"dtmf"        → keypad input
```

### Sending Audio Back to Twilio

To play audio back to the caller, send JSON over the WebSocket:

```python
import json

async def send_audio_to_twilio(ws, stream_sid: str, wav_bytes: bytes):
    """Convert WAV back to μ-law and send to Twilio"""
    # Strip WAV header if present, get raw PCM
    pcm_16k = strip_wav_header(wav_bytes)
    
    # Downsample 16kHz → 8kHz
    pcm_8k, _ = audioop.ratecv(pcm_16k, 2, 1, 16000, 8000, None)
    
    # PCM → μ-law
    mulaw_bytes = audioop.lin2ulaw(pcm_8k, 2)
    
    # Base64 encode
    audio_b64 = base64.b64encode(mulaw_bytes).decode('utf-8')
    
    # Send media message
    await ws.send_json({
        "event": "media",
        "streamSid": stream_sid,
        "media": {
            "payload": audio_b64
        }
    })
```

---

## 10. Database Schema

```python
# storage/models.py — SQLAlchemy 2.0 declarative style

from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy import String, DateTime, Float, Boolean, JSON, ForeignKey, Text
from datetime import datetime
import uuid

class Base(DeclarativeBase):
    pass

class CallRecord(Base):
    __tablename__ = "call_records"
    
    call_id: Mapped[str] = mapped_column(String, primary_key=True, 
                                          default=lambda: str(uuid.uuid4()))
    channel: Mapped[str] = mapped_column(String(20))          # phone|web|whatsapp
    language: Mapped[str] = mapped_column(String(10))         # hi-IN|en-IN
    started_at: Mapped[datetime] = mapped_column(DateTime)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    duration_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)
    outcome: Mapped[str] = mapped_column(String(20))          # complete|abandoned|error
    prompt_version: Mapped[str] = mapped_column(String(20))
    twilio_call_sid: Mapped[str | None] = mapped_column(String(50), nullable=True)
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False)
    
    turns: Mapped[list["ConversationTurn"]] = relationship(back_populates="call")
    fnol_record: Mapped["FNOLRecord | None"] = relationship(back_populates="call")
    pipeline_metrics: Mapped[list["TurnMetrics"]] = relationship(back_populates="call")
    audio_artifact: Mapped["AudioArtifact | None"] = relationship(back_populates="call")


class ConversationTurn(Base):
    __tablename__ = "conversation_turns"
    
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    call_id: Mapped[str] = mapped_column(ForeignKey("call_records.call_id"))
    turn_index: Mapped[int] = mapped_column()
    speaker: Mapped[str] = mapped_column(String(10))          # user|agent
    text: Mapped[str] = mapped_column(Text)
    language: Mapped[str] = mapped_column(String(10))
    timestamp_ms: Mapped[int] = mapped_column()               # ms since call start
    fsm_state: Mapped[str] = mapped_column(String(30))        # state at this turn
    
    call: Mapped["CallRecord"] = relationship(back_populates="turns")


class FNOLRecord(Base):
    __tablename__ = "fnol_records"
    
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    call_id: Mapped[str] = mapped_column(ForeignKey("call_records.call_id"), unique=True)
    policy_number: Mapped[str | None] = mapped_column(String(50), nullable=True)
    incident_type: Mapped[str | None] = mapped_column(String(30), nullable=True)
    incident_date: Mapped[str | None] = mapped_column(String(30), nullable=True)
    incident_location: Mapped[str | None] = mapped_column(Text, nullable=True)
    injuries_reported: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    injury_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    vehicle_damage: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    damage_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    third_party_involved: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    callback_number: Mapped[str | None] = mapped_column(String(20), nullable=True)
    preferred_language: Mapped[str] = mapped_column(String(10))
    extraction_confidence: Mapped[dict] = mapped_column(JSON)  # per-field 0-1
    completeness_score: Mapped[float] = mapped_column(Float)
    extracted_at: Mapped[datetime] = mapped_column(DateTime)
    
    call: Mapped["CallRecord"] = relationship(back_populates="fnol_record")


class TurnMetrics(Base):
    __tablename__ = "turn_metrics"
    
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    call_id: Mapped[str] = mapped_column(ForeignKey("call_records.call_id"))
    turn_index: Mapped[int] = mapped_column()
    stt_ms: Mapped[float] = mapped_column(Float)
    llm_ms: Mapped[float] = mapped_column(Float)
    llm_ttft_ms: Mapped[float] = mapped_column(Float)
    tts_ms: Mapped[float] = mapped_column(Float)
    total_ms: Mapped[float] = mapped_column(Float)
    stt_provider: Mapped[str] = mapped_column(String(30))
    llm_provider: Mapped[str] = mapped_column(String(30))
    tts_provider: Mapped[str] = mapped_column(String(30))
    fallback_triggered: Mapped[bool] = mapped_column(Boolean, default=False)
    
    call: Mapped["CallRecord"] = relationship(back_populates="pipeline_metrics")


class PromptVersion(Base):
    __tablename__ = "prompt_versions"
    
    version_id: Mapped[str] = mapped_column(String(20), primary_key=True)
    description: Mapped[str] = mapped_column(Text)
    templates: Mapped[dict] = mapped_column(JSON)             # template_key → text
    created_at: Mapped[datetime] = mapped_column(DateTime)
    is_active: Mapped[bool] = mapped_column(Boolean, default=False)
    eval_score: Mapped[float | None] = mapped_column(Float, nullable=True)


class EvalRun(Base):
    __tablename__ = "eval_runs"
    
    run_id: Mapped[str] = mapped_column(String(36), primary_key=True,
                                         default=lambda: str(uuid.uuid4()))
    prompt_version_id: Mapped[str] = mapped_column(String(20))
    baseline_version_id: Mapped[str | None] = mapped_column(String(20), nullable=True)
    status: Mapped[str] = mapped_column(String(20))           # queued|running|complete|failed
    started_at: Mapped[datetime] = mapped_column(DateTime)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    summary: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    scenario_results: Mapped[dict | None] = mapped_column(JSON, nullable=True)


class AuditLog(Base):
    __tablename__ = "audit_log"
    
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime)
    actor: Mapped[str] = mapped_column(String(100))           # username or "system"
    action: Mapped[str] = mapped_column(String(50))           # call_started, fnol_created, etc.
    resource_type: Mapped[str] = mapped_column(String(30))
    resource_id: Mapped[str] = mapped_column(String(100))
    detail: Mapped[dict] = mapped_column(JSON)
    # No updates or deletes on this table ever


class AudioArtifact(Base):
    __tablename__ = "audio_artifacts"
    
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    call_id: Mapped[str] = mapped_column(ForeignKey("call_records.call_id"), unique=True)
    file_path: Mapped[str] = mapped_column(Text)
    file_size_bytes: Mapped[int] = mapped_column()
    duration_seconds: Mapped[float] = mapped_column(Float)
    
    call: Mapped["CallRecord"] = relationship(back_populates="audio_artifact")
```

---

## 11. Domain Logic Specs

### 11.1 Conversation FSM

```python
from enum import Enum

class FsmState(str, Enum):
    GREETING         = "GREETING"
    POLICY_VERIFY    = "POLICY_VERIFY"
    INCIDENT_CAPTURE = "INCIDENT_CAPTURE"
    DETAILS_CAPTURE  = "DETAILS_CAPTURE"
    CONTACT_VERIFY   = "CONTACT_VERIFY"
    SUMMARY          = "SUMMARY"
    COMPLETE         = "COMPLETE"
    ERROR            = "ERROR"

# State machine behavior:
# Each state has:
#   - entry_prompt_key: which prompt template to use on entering
#   - exit_conditions: functions that evaluate transcript → bool
#   - max_reprompts: before advancing or escalating
#   - next_state: normal progression
#   - fallback_state: on max_reprompts exceeded

STATE_CONFIG = {
    FsmState.GREETING: {
        "entry_prompt": "greeting",
        "exit_condition": "language_detected and caller_acknowledged",
        "max_reprompts": 2,
        "next": FsmState.POLICY_VERIFY,
        "fallback": FsmState.ERROR
    },
    FsmState.POLICY_VERIFY: {
        "entry_prompt": "policy_verify",
        "exit_condition": "policy_number_captured",
        "max_reprompts": 3,
        "next": FsmState.INCIDENT_CAPTURE,
        "fallback": FsmState.INCIDENT_CAPTURE  # proceed without policy
    },
    FsmState.INCIDENT_CAPTURE: {
        "entry_prompt": "incident_capture",
        "exit_condition": "incident_type_and_date_captured",
        "max_reprompts": 3,
        "next": FsmState.DETAILS_CAPTURE,
        "fallback": FsmState.DETAILS_CAPTURE
    },
    FsmState.DETAILS_CAPTURE: {
        "entry_prompt": "details_capture",
        "exit_condition": "completeness_score >= 0.8",
        "max_reprompts": 5,   # loops asking for missing fields
        "next": FsmState.CONTACT_VERIFY,
        "fallback": FsmState.CONTACT_VERIFY  # proceed with partial
    },
    FsmState.CONTACT_VERIFY: {
        "entry_prompt": "contact_verify",
        "exit_condition": "callback_number_confirmed",
        "max_reprompts": 2,
        "next": FsmState.SUMMARY,
        "fallback": FsmState.SUMMARY
    },
    FsmState.SUMMARY: {
        "entry_prompt": "summary",
        "exit_condition": "caller_confirmed_or_corrected",
        "max_reprompts": 2,
        "next": FsmState.COMPLETE,
        "fallback": FsmState.COMPLETE
    },
    FsmState.COMPLETE: {
        "entry_prompt": "closing",
        "exit_condition": None,   # terminal state
        "next": None,
        "fallback": None
    },
}
```

### 11.2 FNOL Extractor Prompt

**`templates/v1/extractor_system.txt`**:

```
You are an FNOL (First Notice of Loss) extraction system for an Indian insurance company.
Given a conversation transcript between a caller and an insurance agent, extract structured claim information.

Extract the following fields:
- policy_number: The policy/contract number (any format)
- incident_type: One of: accident, theft, fire, flood, natural_disaster, medical, other
- incident_date: Date of the incident (normalize to YYYY-MM-DD if possible, else return as spoken)
- incident_location: Where the incident occurred (city, address, landmark)
- injuries_reported: boolean — were any injuries mentioned?
- injury_description: Details of injuries if mentioned
- vehicle_damage: boolean — was vehicle damage mentioned?
- damage_description: Description of damage if mentioned
- third_party_involved: boolean — was any third party involved?
- callback_number: Phone number for follow-up
- preferred_language: "hi-IN" if conversation was Hindi/Hinglish, "en-IN" if English

For each field also provide a confidence score 0.0-1.0.
0.9-1.0: explicitly stated and unambiguous
0.6-0.8: inferred from context, likely correct
0.3-0.5: guessed, uncertain
0.0: not mentioned, null

IMPORTANT:
- Handle Hindi text and Hinglish (mixed Hindi/English) correctly
- Indian date formats: "15 March ko", "teen tarikh ko" = March 3rd
- Indian number formats: "nine eight seven six" spoken as individual digits
- Return ONLY valid JSON. No preamble, no explanation.

Output format:
{
  "policy_number": string | null,
  "incident_type": string | null,
  "incident_date": string | null,
  "incident_location": string | null,
  "injuries_reported": boolean | null,
  "injury_description": string | null,
  "vehicle_damage": boolean | null,
  "damage_description": string | null,
  "third_party_involved": boolean | null,
  "callback_number": string | null,
  "preferred_language": "hi-IN" | "en-IN",
  "confidence": {
    "policy_number": float,
    "incident_type": float,
    "incident_date": float,
    "incident_location": float,
    "injuries_reported": float,
    "vehicle_damage": float,
    "third_party_involved": float,
    "callback_number": float
  }
}
```

### 11.3 Language Detection

```python
# Simple but effective approach:
# 1. Check Sarvam STT response language_code field — most reliable
# 2. If auto-detected as hi-IN → use Hindi prompts
# 3. If en-IN → use English prompts
# 4. Lock language after first user turn (LANGUAGE_DETECTION_TURNS=1)
# 5. If Hinglish detected (mixed) → use Hindi prompts (more inclusive)

# Hinglish detection heuristic:
# If >30% of words are Devanagari script → hi-IN
# If >80% Latin script → en-IN
# Mixed → hi-IN (treat as Hinglish, Hindi prompts)

def detect_hinglish(text: str) -> bool:
    devanagari_chars = sum(1 for c in text if '\u0900' <= c <= '\u097F')
    total_alpha = sum(1 for c in text if c.isalpha())
    if total_alpha == 0:
        return False
    return 0.1 < (devanagari_chars / total_alpha) < 0.9
```

---

## 12. Inference Pipeline Specs

### 12.1 Circuit Breaker

```python
# pipeline/circuit_breaker.py

from enum import Enum
from dataclasses import dataclass, field
from datetime import datetime, timedelta

class CircuitState(str, Enum):
    HEALTHY      = "healthy"
    COOLING_DOWN = "cooling_down"
    DISABLED     = "disabled"

@dataclass
class CircuitBreaker:
    name: str
    error_threshold: int = 3
    cooldown_seconds: int = 60
    disable_threshold: int = 3
    
    state: CircuitState = CircuitState.HEALTHY
    consecutive_errors: int = 0
    cooldown_cycles: int = 0
    last_error_at: datetime | None = None
    cooling_until: datetime | None = None
    
    def record_success(self):
        self.consecutive_errors = 0
        if self.state == CircuitState.COOLING_DOWN:
            self.state = CircuitState.HEALTHY
            self.cooldown_cycles = 0
    
    def record_failure(self):
        self.consecutive_errors += 1
        self.last_error_at = datetime.utcnow()
        
        if self.consecutive_errors >= self.error_threshold:
            if self.state == CircuitState.HEALTHY:
                self.state = CircuitState.COOLING_DOWN
                self.cooling_until = datetime.utcnow() + timedelta(
                    seconds=self.cooldown_seconds
                )
                self.cooldown_cycles += 1
                
                if self.cooldown_cycles >= self.disable_threshold:
                    self.state = CircuitState.DISABLED
    
    def is_available(self) -> bool:
        if self.state == CircuitState.HEALTHY:
            return True
        if self.state == CircuitState.DISABLED:
            return False
        # COOLING_DOWN: check if cooldown expired
        if self.cooling_until and datetime.utcnow() > self.cooling_until:
            self.state = CircuitState.HEALTHY
            self.consecutive_errors = 0
            return True
        return False
```

### 12.2 Parallel Batch TTS

```python
# pipeline/tts.py

import asyncio
import base64
import time
from sarvamai import AsyncSarvamAI

async def synthesize_parallel(
    sentences: list[str],
    language_code: str,
    client: AsyncSarvamAI
) -> tuple[list[bytes], float]:
    """
    Fire all sentences simultaneously, return in order.
    Returns (audio_chunks, total_latency_ms)
    
    Latency = max(t1...tN) not sum(t1...tN)
    """
    start = time.perf_counter()
    
    async def synthesize_one(text: str, index: int) -> tuple[int, bytes]:
        resp = await client.text_to_speech.convert(
            text=text,
            target_language_code=language_code,
            speaker="meera",
            model="bulbul:v2"
        )
        audio = base64.b64decode(resp.audios[0])
        return index, audio
    
    tasks = [
        synthesize_one(sentence, i)
        for i, sentence in enumerate(sentences)
    ]
    
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    # Sort by index to maintain order, handle exceptions gracefully
    audio_chunks = []
    for result in sorted(
        [r for r in results if not isinstance(r, Exception)],
        key=lambda x: x[0]
    ):
        audio_chunks.append(result[1])
    
    # For failed sentences, append silence
    silent_chunk = generate_silence_wav(duration_ms=500)
    for i, result in enumerate(results):
        if isinstance(result, Exception):
            audio_chunks.insert(i, silent_chunk)
    
    total_ms = (time.perf_counter() - start) * 1000
    return audio_chunks, total_ms

def split_into_sentences(text: str, language: str) -> list[str]:
    """Split LLM response into sentences for parallel TTS"""
    import re
    # Handle Hindi sentence endings (। Devanagari danda)
    if language == "hi-IN":
        sentences = re.split(r'[।\.\!\?]+', text)
    else:
        sentences = re.split(r'[\.!\?]+', text)
    
    # Filter empty, strip whitespace, max 200 chars per sentence
    sentences = [s.strip() for s in sentences if s.strip()]
    
    # If a sentence is too long for TTS, chunk it
    result = []
    for s in sentences:
        if len(s) > 200:
            # Split on comma or natural break
            parts = re.split(r'[,،]+', s)
            result.extend([p.strip() for p in parts if p.strip()])
        else:
            result.append(s)
    
    return result if result else [text]
```

### 12.3 Prometheus Metrics

```python
# pipeline/metrics.py

from prometheus_client import Histogram, Counter, Gauge, REGISTRY

# Latency histograms — buckets in milliseconds
STT_LATENCY = Histogram(
    "vaani_stt_latency_ms",
    "STT stage latency in milliseconds",
    ["provider", "language", "channel"],
    buckets=[50, 100, 200, 300, 500, 750, 1000, 1500, 2000, 5000]
)

LLM_LATENCY = Histogram(
    "vaani_llm_latency_ms",
    "LLM stage total latency in milliseconds",
    ["provider", "model"],
    buckets=[100, 200, 500, 750, 1000, 1500, 2000, 3000, 5000, 10000]
)

LLM_TTFT = Histogram(
    "vaani_llm_ttft_ms",
    "LLM time-to-first-token in milliseconds",
    ["provider", "model"],
    buckets=[50, 100, 150, 200, 300, 500, 750, 1000, 2000]
)

TTS_LATENCY = Histogram(
    "vaani_tts_latency_ms",
    "TTS stage latency in milliseconds (parallel batch)",
    ["provider", "language"],
    buckets=[50, 100, 200, 300, 500, 750, 1000, 1500, 2000]
)

PIPELINE_LATENCY = Histogram(
    "vaani_pipeline_total_latency_ms",
    "Total pipeline latency per turn",
    ["channel"],
    buckets=[200, 500, 750, 1000, 1500, 2000, 3000, 5000]
)

# Counters
CALLS_TOTAL = Counter(
    "vaani_calls_total",
    "Total calls by outcome",
    ["channel", "language", "outcome"]
)

PROVIDER_ERRORS = Counter(
    "vaani_provider_errors_total",
    "Provider errors by type",
    ["stage", "provider", "error_type"]
)

FALLBACKS_TRIGGERED = Counter(
    "vaani_fallback_triggered_total",
    "Number of times fallback provider was used",
    ["stage", "from_provider", "to_provider"]
)

CIRCUIT_BREAKER_OPENS = Counter(
    "vaani_circuit_breaker_opens_total",
    "Number of times a circuit breaker opened",
    ["provider"]
)

FNOL_COMPLETENESS = Histogram(
    "vaani_fnol_completeness_score",
    "FNOL extraction completeness score distribution",
    buckets=[0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]
)

# Gauges
ACTIVE_CALLS = Gauge(
    "vaani_active_calls",
    "Currently active calls",
    ["channel"]
)

PROVIDER_HEALTH = Gauge(
    "vaani_provider_health",
    "Provider health status: 1=healthy, 0.5=cooling_down, 0=disabled",
    ["stage", "provider"]
)
```

---

## 13. Observability Specs

### 13.1 Structured Logging

```python
# Use structlog throughout — every log entry is JSON in production

import structlog

log = structlog.get_logger()

# Bind call context at the start of each call
log = log.bind(call_id=call_id, channel=channel, language=language)

# Usage throughout the call
log.info("stt_complete", latency_ms=stt_ms, transcript_length=len(transcript))
log.warning("circuit_breaker_opened", provider="groq", error_count=3)
log.error("tts_failed", provider="sarvam", error=str(e), fallback="gtts")

# Configuration in main.py
structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.add_log_level,
        structlog.processors.CallsiteParameterAdder(
            [structlog.processors.CallsiteParameter.FUNC_NAME]
        ),
        structlog.processors.JSONRenderer()  # in production
        # structlog.dev.ConsoleRenderer()    # in development
    ]
)
```

### 13.2 Grafana Dashboards

**Dashboard 1: Pipeline Health** (`pipeline_health.json`)
- Panels: STT P50/P95 by provider, LLM P50/P95/TTFT by provider, TTS P50/P95
- Time series for each metric over last 1h/6h/24h
- Provider health status (gauge panels: green/amber/red)
- Circuit breaker event log
- Fallback rate time series

**Dashboard 2: Call Analytics** (`call_analytics.json`)
- Active calls gauge (real-time)
- Calls per hour (bar chart)
- Call outcome breakdown (pie: complete/abandoned/error)
- Channel distribution (pie: phone/web/whatsapp)
- Language distribution (pie: hi-IN/en-IN)
- Average call duration trend
- P95 pipeline latency trend (target: <2000ms)

**Dashboard 3: FNOL Accuracy** (`fnol_accuracy.json`)
- FNOL completeness score distribution (histogram)
- Per-field extraction rate (how often each field is captured)
- Completion rate by language
- Completion rate by channel
- Recent eval run scores (table)

### 13.3 Langfuse Integration

```python
# In pipeline/llm.py — wrap all LLM calls

from langfuse import Langfuse
from langfuse.decorators import observe, langfuse_context

langfuse = Langfuse()

@observe(name="fnol_llm_call")
async def call_llm(
    messages: list[dict],
    call_id: str,
    purpose: str  # "conversation" | "extraction"
) -> str:
    langfuse_context.update_current_observation(
        metadata={"call_id": call_id, "purpose": purpose},
        tags=["fnol", purpose]
    )
    
    response = await groq_client.chat.completions.create(
        model=settings.GROQ_MODEL,
        messages=messages
    )
    
    return response.choices[0].message.content
```

---

## 14. Eval Suite Specs

### 14.1 The 15 Scenarios

```python
# eval/scenarios.py

SCENARIOS = [
    # ─── Hindi Scenarios ────────────────────────────────────────────────────
    {
        "id": "H1",
        "name": "Clean complete FNOL in Hindi",
        "language": "hi-IN",
        "transcript": [
            {"speaker": "agent", "text": "नमस्ते, मैं आपकी बीमा क्लेम में मदद करूंगा। कृपया अपना पॉलिसी नंबर बताएं।"},
            {"speaker": "user", "text": "मेरा पॉलिसी नंबर है SBI-2024-789456"},
            {"speaker": "agent", "text": "धन्यवाद। क्या हुआ था? घटना के बारे में बताएं।"},
            {"speaker": "user", "text": "कल रात मेरी कार का एक्सीडेंट हो गया। मुंबई हाईवे पर, दूसरी गाड़ी ने टक्कर मारी।"},
            {"speaker": "agent", "text": "क्या कोई चोट लगी?"},
            {"speaker": "user", "text": "नहीं, चोट नहीं लगी लेकिन कार को काफी नुकसान हुआ है। दूसरी गाड़ी वाले भी थे।"},
            {"speaker": "agent", "text": "कब हुआ यह?"},
            {"speaker": "user", "text": "15 मार्च को, रात करीब 9 बजे।"},
            {"speaker": "agent", "text": "आपका कॉलबैक नंबर?"},
            {"speaker": "user", "text": "9876543210"},
        ],
        "expected": {
            "policy_number": "SBI-2024-789456",
            "incident_type": "accident",
            "incident_date": "2024-03-15",
            "incident_location": "मुंबई हाईवे",
            "injuries_reported": False,
            "vehicle_damage": True,
            "third_party_involved": True,
            "callback_number": "9876543210",
            "preferred_language": "hi-IN"
        },
        "acceptable_alternatives": {
            "incident_date": ["15 March", "March 15", "15-03-2024"],
            "incident_location": ["Mumbai Highway", "mumbai highway"]
        }
    },
    
    {
        "id": "H2",
        "name": "Hindi with Hinglish numbers and dates",
        "language": "hi-IN",
        "transcript": [
            {"speaker": "user", "text": "Policy number है P-two-four-five-six-seven"},
            {"speaker": "user", "text": "Three April ko accident hua, near Andheri station"},
            {"speaker": "user", "text": "Number है nine-eight-seven-six-five-four-three-two-one-zero"},
        ],
        "expected": {
            "policy_number": "P-24567",
            "incident_type": "accident",
            "incident_date": "2024-04-03",
            "incident_location": "Andheri station",
            "callback_number": "9876543210"
        },
        "acceptable_alternatives": {
            "policy_number": ["P24567", "P 24567"],
            "incident_date": ["April 3", "3 April", "03-04-2024"]
        }
    },
    
    {
        "id": "H3",
        "name": "Caller confused about policy number",
        "language": "hi-IN",
        "transcript": [
            {"speaker": "user", "text": "Policy number... wait, mujhe nahi pata exactly"},
            {"speaker": "user", "text": "Ek minute, dekh raha hoon... haan, LIC-987-654321"},
            {"speaker": "user", "text": "Gaadi chori ho gayi, 20 February ko, Pune mein"},
            {"speaker": "user", "text": "Phone number 9988776655 hai"},
        ],
        "expected": {
            "policy_number": "LIC-987-654321",
            "incident_type": "theft",
            "incident_date": "2024-02-20",
            "incident_location": "Pune",
            "callback_number": "9988776655"
        }
    },
    
    {
        "id": "H4",
        "name": "Multiple vehicles, injuries",
        "language": "hi-IN",
        "transcript": [
            {"speaker": "user", "text": "Policy TATA-2023-112233 hai mera"},
            {"speaker": "user", "text": "Teen gaadiyaan thi accident mein, Bangalore-Mysore road pe"},
            {"speaker": "user", "text": "Haan, mere ko thoda chot lagi, haath mein"},
            {"speaker": "user", "text": "5 January ko shaam 4 baje"},
            {"speaker": "user", "text": "Callback ke liye 7766554433 pe call karo"},
        ],
        "expected": {
            "policy_number": "TATA-2023-112233",
            "incident_type": "accident",
            "injuries_reported": True,
            "third_party_involved": True,
            "callback_number": "7766554433"
        }
    },
    
    {
        "id": "H5",
        "name": "Distressed caller, incomplete information",
        "language": "hi-IN",
        "transcript": [
            {"speaker": "user", "text": "Bahut mushkil mein hoon, meri gaadi jal gayi"},
            {"speaker": "user", "text": "Policy... nahi yaad, SBI ka hai bas"},
            {"speaker": "user", "text": "Aaj subah Mumbai mein"},
            {"speaker": "user", "text": "Haan haan injuries hain, hospital mein hoon"},
            {"speaker": "user", "text": "9900112233"},
        ],
        "expected": {
            "incident_type": "fire",
            "injuries_reported": True,
            "vehicle_damage": True,
            "callback_number": "9900112233"
        },
        "acceptable_alternatives": {
            "incident_location": ["Mumbai", "mumbai"]
        }
    },
    
    # ─── English Scenarios ───────────────────────────────────────────────────
    {
        "id": "E1",
        "name": "Clean complete FNOL in English",
        "language": "en-IN",
        "transcript": [
            {"speaker": "user", "text": "My policy number is HDFC-2024-445566"},
            {"speaker": "user", "text": "I had an accident on March 10th on the Delhi-Agra highway"},
            {"speaker": "user", "text": "No injuries but significant damage to the front of my car"},
            {"speaker": "user", "text": "Another vehicle was involved, he ran a red light"},
            {"speaker": "user", "text": "Please call me on 9123456789"},
        ],
        "expected": {
            "policy_number": "HDFC-2024-445566",
            "incident_type": "accident",
            "incident_date": "2024-03-10",
            "incident_location": "Delhi-Agra highway",
            "injuries_reported": False,
            "vehicle_damage": True,
            "third_party_involved": True,
            "callback_number": "9123456789",
            "preferred_language": "en-IN"
        }
    },
    
    {
        "id": "E2",
        "name": "Ambiguous date formats",
        "language": "en-IN",
        "transcript": [
            {"speaker": "user", "text": "Policy ICICI-789-012"},
            {"speaker": "user", "text": "The flood happened on 15/3 at my Hyderabad property"},
            {"speaker": "user", "text": "No one was hurt but the ground floor is completely damaged"},
            {"speaker": "user", "text": "9876001234"},
        ],
        "expected": {
            "policy_number": "ICICI-789-012",
            "incident_type": "flood",
            "incident_location": "Hyderabad",
            "injuries_reported": False,
            "callback_number": "9876001234"
        },
        "acceptable_alternatives": {
            "incident_date": ["2024-03-15", "15/3", "March 15"]
        }
    },
    
    {
        "id": "E3",
        "name": "Third party and legal concern",
        "language": "en-IN",
        "transcript": [
            {"speaker": "user", "text": "Bajaj Allianz policy BA-2023-667788"},
            {"speaker": "user", "text": "A truck hit my car from behind yesterday evening on NH44"},
            {"speaker": "user", "text": "I have neck pain, went to the hospital this morning"},
            {"speaker": "user", "text": "The truck driver is saying it was my fault but I have dashcam footage"},
            {"speaker": "user", "text": "Call me at 9900887766"},
        ],
        "expected": {
            "policy_number": "BA-2023-667788",
            "incident_type": "accident",
            "incident_location": "NH44",
            "injuries_reported": True,
            "third_party_involved": True,
            "callback_number": "9900887766"
        }
    },
    
    {
        "id": "E4",
        "name": "Non-vehicle claim (theft)",
        "language": "en-IN",
        "transcript": [
            {"speaker": "user", "text": "My home insurance policy is MAX-HOME-334455"},
            {"speaker": "user", "text": "Someone broke into my house two days ago in Chennai"},
            {"speaker": "user", "text": "They took electronics and jewelry, about 3 lakhs worth"},
            {"speaker": "user", "text": "I filed an FIR this morning"},
            {"speaker": "user", "text": "9988001122"},
        ],
        "expected": {
            "policy_number": "MAX-HOME-334455",
            "incident_type": "theft",
            "incident_location": "Chennai",
            "injuries_reported": False,
            "vehicle_damage": False,
            "callback_number": "9988001122"
        }
    },
    
    {
        "id": "E5",
        "name": "Caller repeats and self-corrects",
        "language": "en-IN",
        "transcript": [
            {"speaker": "user", "text": "Policy number... let me check... it's SBI-2024-111222"},
            {"speaker": "user", "text": "Wait no, SBI-2024-111333, I was reading it wrong"},
            {"speaker": "user", "text": "Accident happened... it was on March 5th no wait, March 6th"},
            {"speaker": "user", "text": "March 6th, near Bandra station"},
            {"speaker": "user", "text": "No injuries, minor damage, 9876543000"},
        ],
        "expected": {
            "policy_number": "SBI-2024-111333",
            "incident_type": "accident",
            "incident_date": "2024-03-06",
            "incident_location": "Bandra station",
            "injuries_reported": False,
            "callback_number": "9876543000"
        }
    },
    
    # ─── Edge Cases ──────────────────────────────────────────────────────────
    {
        "id": "X1",
        "name": "Language switch mid-call",
        "transcript": [
            {"speaker": "user", "text": "Mera policy number hai LIC-2024-999888"},
            {"speaker": "user", "text": "Actually let me continue in English, it's easier"},
            {"speaker": "user", "text": "My car was stolen last Tuesday from Navi Mumbai"},
            {"speaker": "user", "text": "9123009876"},
        ],
        "expected": {
            "policy_number": "LIC-2024-999888",
            "incident_type": "theft",
            "incident_location": "Navi Mumbai",
            "callback_number": "9123009876"
        }
    },
    
    {
        "id": "X2",
        "name": "Correction of wrong policy number",
        "transcript": [
            {"speaker": "user", "text": "Policy 1234567"},
            {"speaker": "agent", "text": "Can you confirm that's 1234567?"},
            {"speaker": "user", "text": "Sorry, I made a mistake, it's actually HDFC-1234567"},
            {"speaker": "user", "text": "Fire broke out in my warehouse on January 20th in Surat"},
            {"speaker": "user", "text": "9000112233"},
        ],
        "expected": {
            "policy_number": "HDFC-1234567",
            "incident_type": "fire",
            "incident_location": "Surat",
            "callback_number": "9000112233"
        }
    },
    
    {
        "id": "X3",
        "name": "Vague location requiring follow-up",
        "transcript": [
            {"speaker": "user", "text": "Policy TATA-AIG-556677"},
            {"speaker": "user", "text": "Accident happened near the flyover"},
            {"speaker": "agent", "text": "Which city and which flyover?"},
            {"speaker": "user", "text": "In Kolkata, near the Ultadanga flyover"},
            {"speaker": "user", "text": "February 28th, morning"},
            {"speaker": "user", "text": "Minor injuries to my knee, other car also damaged"},
            {"speaker": "user", "text": "9988776600"},
        ],
        "expected": {
            "policy_number": "TATA-AIG-556677",
            "incident_type": "accident",
            "incident_location": "Ultadanga flyover, Kolkata",
            "incident_date": "2024-02-28",
            "injuries_reported": True,
            "third_party_involved": True,
            "callback_number": "9988776600"
        }
    },
    
    {
        "id": "X4",
        "name": "Caller wants to abort",
        "transcript": [
            {"speaker": "user", "text": "Policy HDFC-2024-445566"},
            {"speaker": "user", "text": "I'll call back later, I don't have time right now"},
        ],
        "expected": {
            "policy_number": "HDFC-2024-445566",
        },
        "expected_partial": True  # Don't penalize for missing fields
    },
    
    {
        "id": "X5",
        "name": "STT errors simulated (garbled text)",
        "transcript": [
            {"speaker": "user", "text": "Policy um SB eye two zero two four dash seven eight nine"},
            {"speaker": "user", "text": "Accident happen near uh Bandra Kurla Complex BKC area"},
            {"speaker": "user", "text": "10 February uh in the evening"},
            {"speaker": "user", "text": "Nine eight seven six five four three two one zero"},
        ],
        "expected": {
            "incident_type": "accident",
            "incident_location": "BKC",
            "callback_number": "9876543210"
        },
        "acceptable_alternatives": {
            "policy_number": ["SBI-2024-789", "SBI2024-789"],
            "incident_location": ["Bandra Kurla Complex", "BKC", "Bandra-Kurla Complex"]
        }
    }
]
```

### 14.2 Scoring Logic

```python
# eval/runner.py

def score_scenario(
    extracted: FNOLRecord,
    expected: dict,
    acceptable_alternatives: dict = {},
    expected_partial: bool = False
) -> ScenarioScore:
    
    field_scores = {}
    
    for field, expected_value in expected.items():
        extracted_value = getattr(extracted, field, None)
        
        if extracted_value is None:
            field_scores[field] = 0.0
            continue
        
        # Exact match
        if str(extracted_value).lower() == str(expected_value).lower():
            field_scores[field] = 1.0
            continue
        
        # Check acceptable alternatives
        alternatives = acceptable_alternatives.get(field, [])
        if any(str(extracted_value).lower() == str(alt).lower() 
               for alt in alternatives):
            field_scores[field] = 1.0
            continue
        
        # Partial match for strings (e.g. location contained in extracted)
        if isinstance(expected_value, str) and isinstance(extracted_value, str):
            if expected_value.lower() in extracted_value.lower():
                field_scores[field] = 0.8
                continue
        
        field_scores[field] = 0.0
    
    overall = sum(field_scores.values()) / len(field_scores) if field_scores else 0.0
    
    return ScenarioScore(
        scenario_id=...,
        field_scores=field_scores,
        overall_accuracy=overall,
        passed=overall >= 0.8
    )
```

---

## 15. Frontend Design & Component Specs

### 15.1 Aesthetic Direction

**Theme**: Industrial precision. Think Bloomberg Terminal meets modern DevOps dashboard. Dark background (`#0D0D0D`), amber accents (`#F59E0B`), teal for healthy states (`#14B8A6`), red for errors (`#EF4444`). Monospace for data values, condensed sans for labels.

**Why**: Ops dashboards are functional artifacts used under pressure. The aesthetic should signal reliability and density of information, not consumer friendliness. This is also deliberately differentiated from the generic "AI startup purple gradient" look that every other candidate will have.

**Typography**:
- Display / Nav: `IBM Plex Sans Condensed` (Google Fonts)
- Data values / metrics: `JetBrains Mono` or `IBM Plex Mono`
- Body / labels: `IBM Plex Sans`

**Color tokens** (`globals.css`):
```css
:root {
  --bg-primary: #0D0D0D;
  --bg-secondary: #141414;
  --bg-tertiary: #1A1A1A;
  --bg-elevated: #222222;
  --border: #2A2A2A;
  --border-bright: #3A3A3A;
  
  --text-primary: #F5F5F5;
  --text-secondary: #A0A0A0;
  --text-muted: #606060;
  
  --amber: #F59E0B;
  --amber-dim: #78490A;
  --teal: #14B8A6;
  --teal-dim: #0A4A44;
  --red: #EF4444;
  --red-dim: #5A1A1A;
  --blue: #3B82F6;
  
  /* Latency status colors */
  --latency-fast: #22C55E;    /* <p50 */
  --latency-ok: #F59E0B;      /* p50-p95 */
  --latency-slow: #EF4444;    /* >p95 */
}
```

### 15.2 Component Specs

#### `LiveCallPanel.tsx`

Real-time call monitoring. Connects to `/ws/live` WebSocket. Shows all active calls as cards.

```typescript
// Each active call card shows:
// - Channel badge: [📞 PHONE] [🌐 WEB] [💬 WHATSAPP]
// - Language badge: [HI] [EN]  
// - Duration: 01:23 (live counter)
// - FSM state badge: INCIDENT_CAPTURE (color-coded by progress)
// - Last user utterance (last 60 chars, truncated)
// - FNOL completeness: colored progress bar 0-100%
// - Pipeline latency for last turn (STT/LLM/TTS mini bars)
// - Click to expand: full transcript stream, FNOL fields extracted so far

// Empty state: "No active calls. Waiting..."
// Animate new calls in with slide-in from top
```

#### `WaveformVisualizer.tsx`

```typescript
// Props:
interface WaveformVisualizerProps {
  audioStream?: MediaStream;    // live mic input
  audioBuffer?: AudioBuffer;    // for replay
  isActive: boolean;
  vadState: "silence" | "speech" | "processing";
}

// Implementation:
// - Web Audio API: AudioContext → AnalyserNode → Uint8Array frequency data
// - Canvas rendering at 60fps using requestAnimationFrame
// - Bar chart style (not waveform) — 64 frequency buckets
// - Color: based on vadState
//   silence    → #3A3A3A (muted grey)
//   speech     → #14B8A6 (teal, animated)
//   processing → #F59E0B (amber, pulsing)
// - Smooth falloff: bars don't snap to zero, decay by 0.85x per frame
// - Width: fill container, height: 80px
```

#### `PipelineStages.tsx`

```typescript
// Shows 3 horizontal bars: STT | LLM | TTS
// For each stage:
//   - Label: "STT" / "LLM" / "TTS"
//   - Provider badge: "sarvam" / "groq" / "gemini"
//   - Latency value: "183ms" (monospace)
//   - Bar: width proportional to latency vs. P95 baseline
//   - Color: green if <P50, amber if P50-P95, red if >P95
//   - P50 baseline values (hardcoded initially, updated from /diagnostics):
//       STT: 200ms, LLM: 500ms, TTS: 250ms
//   - If fallback_triggered: show orange "↩ FALLBACK" badge
// 
// Animation: bars animate from 0 to final width on new turn (300ms ease-out)
// Click any bar: show sparkline of last 20 measurements
```

#### `FNOLRecord.tsx`

```typescript
// Displays extracted FNOL fields with confidence indicators
// Layout: 2-column grid on desktop, 1-column on mobile
//
// Each field row:
//   - Field name (label): "Policy Number", "Incident Type", etc.
//   - Value: shown in monospace if extracted, "—" if null
//   - Confidence dot: 
//       ●  green  (0.85-1.0)
//       ●  amber  (0.5-0.84)
//       ●  red    (0.0-0.49)
//       ○  grey   (null / not extracted)
//   - Animate newly extracted fields: brief amber flash on update
//
// Bottom: completeness progress bar with percentage
// "FNOL COMPLETE ✓" badge when completeness_score >= 0.8
```

#### `ConversationReplay.tsx`

```typescript
// Full conversation replay with synchronized audio
// Components:
//   - AudioPlayer: play/pause/seek, speed controls (0.5x / 1x / 1.5x / 2x)
//   - Timeline scrubber: draggable, shows turn boundaries
//   - Transcript: scrolling list of turns
//     - Active turn highlighted as audio plays
//     - Speaker badge: [USER] amber / [AGENT] teal
//     - Each agent turn: show pipeline metrics (STT ms | LLM ms | TTS ms)
//   - FNOLRecord panel (right side): updates as turns pass during replay
//   - FSM state indicator: updates as turns pass
//   - Export button: downloads transcript as text or PDF
```

#### `PromptEditor.tsx`

```typescript
// Prompt version management
// Left panel: version selector (list of versions with status badges)
//   - ACTIVE badge (teal) for deployed version
//   - eval_score if available: "Acc: 87%"
//   - Created date
//
// Main area: Monaco Editor
//   - Language: plaintext with custom tokenizer for {{variable}} highlights
//   - Shows selected prompt template (dropdown: greeting_hi, extractor_system, etc.)
//   - Read-only for deployed version, editable for drafts
//
// Side panel: diff view (toggle)
//   - Select two versions to compare
//   - Unified diff with line-level highlights
//
// Action bar:
//   - Save Draft
//   - Run Eval (opens eval modal)
//   - Deploy (requires confirmation modal showing diff from current active)
//   - Rollback (button visible only when not on active version)
```

#### `RegressionRunner.tsx`

```typescript
// Eval run management
// Trigger section:
//   - Select prompt version dropdown
//   - Select baseline version dropdown (optional)
//   - Scenario checkboxes (H1-H5, E1-E5, X1-X5 + "All")
//   - Run button → calls POST /eval/runs, polls GET /eval/runs/{run_id}
//
// Active run: progress indicator, current scenario running
//
// Results table (on completion):
//   - Scenario ID | Name | Overall Acc | Per-field pass/fail dots | vs Baseline delta
//   - Row color: green if passed, red if failed
//   - Summary row: "12/15 passed | Overall: 83.4% | Δ +2.1% vs v1"
//
// Click scenario row: expand field-level breakdown
//   - Field | Expected | Extracted | Match? | Confidence
```

---

## 16. Testing Strategy

### Structure

```python
# conftest.py — shared fixtures

@pytest.fixture
async def db_session():
    """In-memory SQLite for tests"""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with AsyncSession(engine) as session:
        yield session

@pytest.fixture
def mock_sarvam_stt(monkeypatch):
    """Mock Sarvam STT to avoid API calls in unit tests"""
    async def fake_transcribe(*args, **kwargs):
        return Mock(transcript="mock transcript", language_code="hi-IN", time_taken=0.1)
    monkeypatch.setattr("app.pipeline.stt.client.speech_to_text.transcribe", fake_transcribe)

@pytest.fixture  
def mock_groq(monkeypatch):
    """Mock Groq LLM"""
    async def fake_complete(*args, **kwargs):
        return Mock(choices=[Mock(message=Mock(content="Mock agent response"))])
    monkeypatch.setattr("app.pipeline.llm.groq_client.chat.completions.create", fake_complete)

@pytest.fixture
async def test_client(db_session):
    """FastAPI test client with dependency overrides"""
    app.dependency_overrides[get_db] = lambda: db_session
    async with AsyncClient(app=app, base_url="http://test") as client:
        yield client

@pytest.fixture
def auth_headers(test_client):
    """Get JWT token for authenticated requests"""
    response = test_client.post("/auth/login", json={
        "username": "admin",
        "password": "test_password"
    })
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}
```

### Test Coverage Targets

| Module | Target Coverage | Key Test Cases |
|--------|----------------|----------------|
| pipeline/stt.py | 90% | Success, timeout, audio format error, circuit breaker trigger |
| pipeline/llm.py | 90% | Success, fallback triggered, circuit breaker open, streaming TTFT |
| pipeline/tts.py | 90% | Parallel batch success, partial failure, sentence splitting |
| pipeline/circuit_breaker.py | 100% | All state transitions, cooldown expiry, disable threshold |
| domain/fsm.py | 95% | All state transitions, max reprompts, timeout handling |
| domain/extractor.py | 85% | Each scenario type, partial extraction, JSON parse failure |
| domain/validator.py | 95% | All completeness thresholds, per-field confidence |
| api/calls.py | 85% | CRUD, pagination, filters, soft delete |
| api/auth.py | 95% | Login, refresh, revoke, expired token, wrong scope |
| api/prompts.py | 85% | CRUD, deploy, rollback, diff |
| api/diagnostics.py | 80% | Health calculation, provider status aggregation |
| eval/runner.py | 85% | Scenario execution, scoring, baseline comparison |

### Example Tests

```python
# test_circuit_breaker.py

async def test_healthy_to_cooling_on_threshold_errors():
    cb = CircuitBreaker(name="test", error_threshold=3)
    assert cb.state == CircuitState.HEALTHY
    
    cb.record_failure()
    cb.record_failure()
    assert cb.state == CircuitState.HEALTHY  # not yet
    
    cb.record_failure()
    assert cb.state == CircuitState.COOLING_DOWN

async def test_cooling_recovers_after_cooldown():
    cb = CircuitBreaker(name="test", error_threshold=2, cooldown_seconds=1)
    cb.record_failure()
    cb.record_failure()
    assert cb.state == CircuitState.COOLING_DOWN
    
    # Mock time passage
    cb.cooling_until = datetime.utcnow() - timedelta(seconds=2)
    assert cb.is_available() == True
    assert cb.state == CircuitState.HEALTHY

# test_domain_extractor.py

async def test_extract_scenario_H1(mock_groq_extraction):
    """Test extraction against scenario H1 transcript"""
    scenario = next(s for s in SCENARIOS if s["id"] == "H1")
    transcript_text = format_transcript(scenario["transcript"])
    
    mock_groq_extraction.return_value = json.dumps({
        "policy_number": "SBI-2024-789456",
        "incident_type": "accident",
        "incident_date": "2024-03-15",
        "incident_location": "मुंबई हाईवे",
        "injuries_reported": False,
        "vehicle_damage": True,
        "third_party_involved": True,
        "callback_number": "9876543210",
        "preferred_language": "hi-IN",
        "confidence": {k: 0.95 for k in scenario["expected"]}
    })
    
    extractor = FNOLExtractor()
    result = await extractor.extract(transcript_text)
    
    assert result.policy_number == "SBI-2024-789456"
    assert result.incident_type == "accident"
    assert result.injuries_reported == False
    assert result.completeness_score >= 0.9

# test_api_auth.py

async def test_scope_restricted_access(test_client, auth_headers):
    """Read-scoped token cannot deploy prompts"""
    read_token = create_token(scopes=["read"])
    headers = {"Authorization": f"Bearer {read_token}"}
    
    response = await test_client.post(
        "/prompts/v2/deploy",
        json={"confirm": True},
        headers=headers
    )
    assert response.status_code == 403
```

---

## 17. Docker & Deployment

### `docker-compose.yml` (Production)

```yaml
version: "3.9"

services:
  backend:
    build:
      context: ./backend
      dockerfile: Dockerfile
    ports:
      - "8000:8000"
    env_file: .env
    volumes:
      - audio_artifacts:/app/audio_artifacts
      - ./backend/domain/prompts/templates:/app/app/domain/prompts/templates
    depends_on:
      - prometheus
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
    
  frontend:
    build:
      context: ./frontend
      dockerfile: Dockerfile
    ports:
      - "3000:3000"
    environment:
      - NEXT_PUBLIC_API_URL=http://localhost:8000
      - NEXT_PUBLIC_WS_URL=ws://localhost:8000
    depends_on:
      - backend
    restart: unless-stopped
    
  prometheus:
    image: prom/prometheus:v2.51.0
    ports:
      - "9090:9090"
    volumes:
      - ./backend/prometheus/prometheus.yml:/etc/prometheus/prometheus.yml
      - prometheus_data:/prometheus
    command:
      - '--config.file=/etc/prometheus/prometheus.yml'
      - '--storage.tsdb.retention.time=15d'
    restart: unless-stopped
    
  grafana:
    image: grafana/grafana:10.4.0
    ports:
      - "3001:3000"
    volumes:
      - grafana_data:/var/lib/grafana
      - ./backend/grafana/provisioning:/etc/grafana/provisioning
      - ./backend/grafana/dashboards:/var/lib/grafana/dashboards
    environment:
      - GF_AUTH_ANONYMOUS_ENABLED=true
      - GF_AUTH_ANONYMOUS_ORG_ROLE=Viewer
      - GF_AUTH_DISABLE_LOGIN_FORM=false
      - GF_SECURITY_ADMIN_PASSWORD=${GRAFANA_ADMIN_PASSWORD:-admin}
    depends_on:
      - prometheus
    restart: unless-stopped

volumes:
  audio_artifacts:
  prometheus_data:
  grafana_data:
```

### `docker-compose.dev.yml` (Development — mounts code for hot reload)

```yaml
version: "3.9"

services:
  backend:
    build:
      context: ./backend
      target: dev
    volumes:
      - ./backend:/app
    command: uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
    
  frontend:
    build:
      context: ./frontend
      target: dev
    volumes:
      - ./frontend:/app
      - /app/node_modules
    command: npm run dev
```

### Backend `Dockerfile`

```dockerfile
FROM python:3.12-slim AS base
WORKDIR /app
RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*

FROM base AS dev
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 8000

FROM base AS production
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
RUN alembic upgrade head
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
```

### `Makefile` (convenience commands)

```makefile
.PHONY: dev prod test migrate lint clean

dev:
	docker compose -f docker-compose.yml -f docker-compose.dev.yml up

prod:
	docker compose up --build

test:
	cd backend && python -m pytest tests/ -v --cov=app --cov-report=term-missing

migrate:
	cd backend && alembic upgrade head

lint:
	cd backend && ruff check app/ && mypy app/
	cd frontend && npx tsc --noEmit && npx eslint src/

seed-prompts:
	cd backend && python -c "from app.storage.seed import seed_prompts; import asyncio; asyncio.run(seed_prompts())"

clean:
	docker compose down -v
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -name "*.pyc" -delete
```

---

## 18. Implementation Plan — Phase by Phase

**Golden rule**: Never start the next phase until the current one has passing tests. Each phase is independently runnable.

---

### Phase 0 — Scaffolding (1 session)

**Goal**: Repository exists, Docker runs, health check returns 200.

**Files to create**:
- `docker-compose.yml`, `docker-compose.dev.yml`
- `backend/requirements.txt` (all packages listed in section 3)
- `backend/pyproject.toml` (ruff + mypy config)
- `backend/app/main.py` — FastAPI app with `/health` endpoint and lifespan
- `backend/app/config.py` — pydantic-settings Settings class loading all env vars
- `backend/app/storage/database.py` — async SQLite engine + session factory
- `backend/app/storage/models.py` — all SQLAlchemy models (section 10)
- `backend/migrations/` — Alembic init + first migration
- `frontend/package.json` with all dependencies
- `frontend/src/app/layout.tsx` — root layout, font imports, color tokens
- `.env.example`
- `Makefile`

**Done when**: `make dev` runs, `curl localhost:8000/health` returns `{"status": "ok"}`, `curl localhost:3000` returns Next.js app, Grafana is accessible at `localhost:3001`.

**Key implementation notes for `main.py`**:
```python
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from prometheus_client import make_asgi_app
import structlog

log = structlog.get_logger()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    await init_db()
    await seed_initial_prompt_version()
    log.info("vaani_started", environment=settings.ENVIRONMENT)
    yield
    # Shutdown
    log.info("vaani_shutdown")

app = FastAPI(title="Vaani FNOL API", version="1.0.0", lifespan=lifespan)

app.add_middleware(CORSMiddleware, allow_origins=["*"],
                   allow_methods=["*"], allow_headers=["*"])

# Mount Prometheus metrics
metrics_app = make_asgi_app()
app.mount("/metrics", metrics_app)

@app.get("/health")
async def health():
    return {"status": "ok", "version": "1.0.0"}
```

---

### Phase 1 — Inference Pipeline (2-3 sessions)

**Goal**: `PipelineOrchestrator.run_turn(audio_bytes, call_id, language)` works end-to-end with real APIs, emits Prometheus metrics, and handles provider failure gracefully.

**Build order within phase**:

**1a. Circuit Breaker** (`pipeline/circuit_breaker.py`)
- Implement `CircuitBreaker` class exactly as specified in section 12.1
- Write `tests/test_circuit_breaker.py` — all state transitions, cooldown expiry
- No external dependencies. Fully unit testable.

**1b. Metrics** (`pipeline/metrics.py`)
- Define all Prometheus metrics as specified in section 13
- No logic — just metric definitions and a `record_pipeline_turn()` helper function
- Test: verify metrics are registered, values increment correctly

**1c. STT Client** (`pipeline/stt.py`)
```python
class SarvamSTT:
    def __init__(self):
        self.client = SarvamAI(api_subscription_key=settings.SARVAM_API_KEY)
        self.circuit_breaker = CircuitBreaker(name="sarvam_stt")
    
    async def transcribe(
        self,
        audio_wav: bytes,
        language_code: str = "hi-IN",
        call_id: str = ""
    ) -> STTResult:
        # Wrap in timing context
        # Check circuit breaker
        # Call Sarvam SDK
        # Record success/failure on CB
        # Emit Prometheus histogram
        # Return STTResult(transcript, language_code, latency_ms)
```

**1d. LLM Client** (`pipeline/llm.py`)
```python
class GroqLLM:
    # Primary provider
    # Circuit breaker
    # On circuit open: try GeminiLLM fallback
    # Track TTFT: time from request send to first token received
    # Langfuse tracing via @observe decorator
    
class GeminiLLM:
    # Fallback provider
    # Same interface as GroqLLM
    
class LLMRouter:
    def __init__(self):
        self.primary = GroqLLM()
        self.fallback = GeminiLLM()
    
    async def complete(self, messages, call_id, purpose) -> LLMResult:
        if self.primary.circuit_breaker.is_available():
            try:
                result = await self.primary.complete(messages, call_id, purpose)
                FALLBACKS_TRIGGERED.labels(...).inc(0)  # don't increment
                return result
            except Exception as e:
                log.warning("llm_primary_failed", error=str(e))
        
        # Fallback
        FALLBACKS_TRIGGERED.labels("llm", "groq", "gemini").inc()
        return await self.fallback.complete(messages, call_id, purpose)
```

**1e. TTS Client** (`pipeline/tts.py`)
- Implement `synthesize_parallel()` exactly as specified in section 12.2
- Implement `split_into_sentences()` with Hindi danda support
- Implement `generate_silence_wav()` for failed sentence substitution

**1f. VAD** (`pipeline/vad.py`)
```python
# Use silero-vad package
# Wrap in simple interface:
class SileroVAD:
    def __init__(self):
        import torch
        self.model, self.utils = torch.hub.load(
            repo_or_dir='snakers4/silero-vad',
            model='silero_vad',
            force_reload=False
        )
    
    def is_speech(self, audio_chunk_pcm: bytes, sample_rate: int = 16000) -> bool:
        # Convert bytes to tensor
        # Run model
        # Return True if confidence > VAD_THRESHOLD setting
```

**1g. Orchestrator** (`pipeline/orchestrator.py`)
```python
class PipelineOrchestrator:
    def __init__(self):
        self.stt = SarvamSTT()
        self.llm = LLMRouter()
        self.tts = SarvamTTS()
    
    async def run_turn(
        self,
        audio_wav: bytes | None,   # None for text input (WhatsApp)
        text_input: str | None,    # None for audio input
        conversation_history: list[dict],
        call_id: str,
        language: str,
        prompt_version: str
    ) -> PipelineTurnResult:
        
        start = time.perf_counter()
        
        # STT (skip if text_input provided)
        transcript = text_input
        stt_ms = 0.0
        if audio_wav:
            stt_result = await self.stt.transcribe(audio_wav, language, call_id)
            transcript = stt_result.transcript
            stt_ms = stt_result.latency_ms
        
        # LLM
        messages = build_messages(conversation_history, transcript, prompt_version)
        llm_result = await self.llm.complete(messages, call_id, "conversation")
        
        # TTS (only for voice channels)
        tts_ms = 0.0
        audio_chunks = []
        if audio_wav is not None:  # voice channel
            sentences = split_into_sentences(llm_result.text, language)
            audio_chunks, tts_ms = await synthesize_parallel(
                sentences, language, self.tts.async_client
            )
        
        total_ms = (time.perf_counter() - start) * 1000
        
        # Record all metrics
        PIPELINE_LATENCY.labels(channel=...).observe(total_ms)
        STT_LATENCY.labels(...).observe(stt_ms)
        LLM_LATENCY.labels(...).observe(llm_result.latency_ms)
        TTS_LATENCY.labels(...).observe(tts_ms)
        
        return PipelineTurnResult(
            transcript=transcript,
            response_text=llm_result.text,
            audio_chunks=audio_chunks,
            stt_ms=stt_ms,
            llm_ms=llm_result.latency_ms,
            llm_ttft_ms=llm_result.ttft_ms,
            tts_ms=tts_ms,
            total_ms=total_ms,
            fallback_triggered=llm_result.fallback_used
        )
```

**Tests**: `test_pipeline_stt.py`, `test_pipeline_llm.py`, `test_pipeline_tts.py`, `test_pipeline_orchestrator.py`  
Use mocks for all external API calls in unit tests.  
Add one integration test (marked `@pytest.mark.integration`) that calls real APIs.

**Done when**: `pytest tests/test_pipeline* -v` all pass (mocked). Manual test of orchestrator with real audio file produces transcript + agent response + audio.

---

### Phase 2 — Domain Logic (2 sessions)

**Goal**: FSM manages conversation state correctly. FNOL extractor produces valid structured output from transcript.

**2a. Language detection** (`domain/language.py`)
- Detect from Sarvam STT `language_code` response (primary)
- Fallback: Devanagari character ratio heuristic (section 11.3)
- Lock language after first turn

**2b. Prompt loader** (`domain/prompts/loader.py`)
```python
class PromptLoader:
    """Loads prompt templates from filesystem or DB.
    Falls back to v1 filesystem templates if DB version not found."""
    
    def get(self, key: str, version: str, language: str) -> str:
        # key: "greeting", "incident_capture", "extractor_system", etc.
        # language: "hi-IN" | "en-IN"
        # Maps to: templates/{version}/{key}_{lang_suffix}.txt
        # where lang_suffix: "hi" for hi-IN, "en" for en-IN
```

Write all 11 prompt template files for v1:
- `greeting_hi.txt`, `greeting_en.txt`
- `policy_verify_hi.txt`, `policy_verify_en.txt`
- `incident_capture_hi.txt`, `incident_capture_en.txt`
- `details_capture_hi.txt`, `details_capture_en.txt`
- `contact_verify_hi.txt`, `contact_verify_en.txt`  
- `summary_hi.txt`, `summary_en.txt`
- `extractor_system.txt` (language-agnostic)

Each prompt must:
- Be in the specified language
- Include `{{missing_fields}}` placeholder in details_capture for targeted follow-up
- Be professional, empathetic, concise (max 2 sentences per prompt)

**2c. Conversation FSM** (`domain/fsm.py`)
- Implement all states and transitions from section 11.1
- Track reprompt count per state
- Emit structured log on every transition
- `determine_next_state(current_state, fnol_record, reprompt_count) -> FsmState`

**2d. FNOL Extractor** (`domain/extractor.py`)
- System prompt from `extractor_system.txt`
- User message: formatted transcript
- Parse JSON response → `FNOLRecord` Pydantic model
- On JSON parse failure: retry once with `"RESPOND ONLY WITH JSON. NO EXPLANATIONS."` appended
- On second failure: return empty `FNOLRecord` with all None fields

**2e. Completeness Validator** (`domain/validator.py`)
```python
REQUIRED_FIELDS = [
    "policy_number", "incident_type", "incident_date",
    "incident_location", "callback_number"
]

OPTIONAL_FIELDS = [
    "injuries_reported", "vehicle_damage",
    "third_party_involved", "injury_description"
]

def compute_completeness(record: FNOLRecord) -> float:
    # Required fields worth 0.15 each (0.75 total)
    # Optional fields worth 0.05 each (0.25 total)
    # A field counts if value is not None AND confidence > 0.5
```

**Tests**: `test_domain_fsm.py`, `test_domain_extractor.py`, `test_domain_validator.py`

**Done when**: Full conversation flow from GREETING → COMPLETE works in a simple async script test without any HTTP/WebSocket layer.

---

### Phase 3 — Channel Handlers (2 sessions)

**Goal**: Web browser can make a real voice call through the pipeline. Twilio handler connects.

**3a. WebSocket Browser Channel** (`channels/websocket_handler.py`)

This is the most important channel for testing — no Twilio account needed.

```python
@app.websocket("/ws/call")
async def websocket_call_endpoint(websocket: WebSocket, token: str = Query(...)):
    # Validate JWT token
    await websocket.accept()
    
    call_id = str(uuid.uuid4())
    fsm = ConversationFSM()
    orchestrator = PipelineOrchestrator()
    audio_buffer = AudioBuffer()
    
    # Increment active calls gauge
    ACTIVE_CALLS.labels(channel="web").inc()
    
    try:
        # Send call_ready
        await websocket.send_json({"type": "call_ready", "call_id": call_id})
        
        while True:
            data = await websocket.receive_json()
            
            if data["type"] == "audio_chunk":
                pcm = base64.b64decode(data["audio_b64"])
                flushed = audio_buffer.add(pcm)
                
                if flushed or vad.detects_end_of_speech(pcm):
                    wav_bytes = audio_buffer.flush() if not flushed else flushed
                    await process_turn(websocket, orchestrator, fsm, wav_bytes, call_id)
            
            elif data["type"] == "end_call":
                break
    
    except WebSocketDisconnect:
        pass
    finally:
        ACTIVE_CALLS.labels(channel="web").dec()
        await finalize_call(call_id, fsm)

async def process_turn(ws, orchestrator, fsm, wav_bytes, call_id):
    # Run pipeline
    result = await orchestrator.run_turn(wav_bytes, None, fsm.history, call_id, fsm.language, ...)
    
    # Update FSM + extractor
    fsm.add_turn("user", result.transcript)
    agent_text = result.response_text
    fsm.add_turn("agent", agent_text)
    
    # Extract FNOL
    fnol = await extractor.extract(fsm.history)
    fsm.advance(fnol)  # may transition state
    
    # Send agent audio
    for chunk in result.audio_chunks:
        await ws.send_json({
            "type": "agent_audio",
            "call_id": call_id,
            "audio_b64": base64.b64encode(chunk).decode()
        })
    
    # Broadcast to live monitor
    await broadcast_to_live_monitors(call_id, result, fnol, fsm.state)
```

**3b. Live Monitor WebSocket** (`channels/websocket_handler.py` — add to same file)

```python
# ConnectionManager for broadcasting to dashboard
class LiveMonitorManager:
    def __init__(self):
        self.connections: list[WebSocket] = []
    
    async def connect(self, ws: WebSocket):
        await ws.accept()
        self.connections.append(ws)
    
    async def broadcast(self, message: dict):
        dead = []
        for ws in self.connections:
            try:
                await ws.send_json(message)
            except:
                dead.append(ws)
        for ws in dead:
            self.connections.remove(ws)

live_manager = LiveMonitorManager()

@app.websocket("/ws/live")
async def websocket_live_endpoint(websocket: WebSocket, token: str = Query(...)):
    # Validate JWT
    await live_manager.connect(websocket)
    try:
        while True:
            await asyncio.sleep(30)  # Keep alive
            await websocket.send_json({"type": "ping"})
    except WebSocketDisconnect:
        live_manager.connections.remove(websocket)
```

**3c. Twilio Handler** (`channels/twilio_handler.py`)

```python
@app.post("/voice/incoming")
async def twilio_incoming(request: Request):
    """Twilio calls this when someone calls our number"""
    # Validate Twilio signature (important for security)
    validator = RequestValidator(settings.TWILIO_AUTH_TOKEN)
    signature = request.headers.get("X-Twilio-Signature", "")
    url = str(request.url)
    form_data = await request.form()
    
    if not validator.validate(url, dict(form_data), signature):
        raise HTTPException(status_code=403, detail="Invalid Twilio signature")
    
    # Build TwiML to start Media Stream
    call_sid = form_data.get("CallSid")
    ws_url = f"wss://{request.headers['host']}/voice/stream"
    
    response = VoiceResponse()
    connect = Connect()
    stream = connect.stream(url=ws_url)
    stream.parameter(name="callSid", value=call_sid)
    response.append(connect)
    
    return Response(content=str(response), media_type="application/xml")

@app.websocket("/voice/stream")
async def twilio_stream(websocket: WebSocket):
    await websocket.accept()
    
    call_id = None
    stream_sid = None
    audio_buffer = AudioBuffer()
    fsm = ConversationFSM()
    orchestrator = PipelineOrchestrator()
    
    async for raw_message in websocket.iter_text():
        message = json.loads(raw_message)
        event = message.get("event")
        
        if event == "start":
            call_id = str(uuid.uuid4())
            stream_sid = message["streamSid"]
            twilio_call_sid = message.get("customParameters", {}).get("callSid")
            ACTIVE_CALLS.labels(channel="phone").inc()
            
            # Send greeting audio
            greeting_wav = await tts.synthesize_single(
                get_prompt("greeting", "v1", "hi-IN"),
                "hi-IN"
            )
            await send_audio_to_twilio(websocket, stream_sid, greeting_wav)
        
        elif event == "media":
            # Convert μ-law chunk to PCM
            mulaw_chunk = base64.b64decode(message["media"]["payload"])
            pcm_chunk = upsample_to_16k(audioop.ulaw2lin(mulaw_chunk, 2))
            
            flushed = audio_buffer.add(pcm_chunk)
            if flushed:
                # Process turn
                result = await orchestrator.run_turn(flushed, None, fsm.history, call_id, fsm.language, "v1")
                # ... update FSM, extract FNOL, send response audio back
                for wav_chunk in result.audio_chunks:
                    await send_audio_to_twilio(websocket, stream_sid, wav_chunk)
        
        elif event == "stop":
            ACTIVE_CALLS.labels(channel="phone").dec()
            await finalize_call(call_id, fsm)
            break
```

**3d. WhatsApp Handler** (`channels/whatsapp_handler.py`)

Text-only. Simpler — no audio conversion needed.

```python
@app.post("/webhook/whatsapp")
async def whatsapp_webhook(request: Request):
    form_data = await request.form()
    body = form_data.get("Body", "")
    from_number = form_data.get("From", "")
    
    # Session management: from_number → call_id mapping (in-memory dict is fine)
    call_id = get_or_create_session(from_number)
    fsm = get_or_create_fsm(call_id)
    
    # Run pipeline (text input, skip STT)
    result = await orchestrator.run_turn(
        audio_wav=None,
        text_input=body,
        conversation_history=fsm.history,
        call_id=call_id,
        language=fsm.language,
        prompt_version=settings.ACTIVE_PROMPT_VERSION
    )
    
    # Send text response via Twilio WhatsApp
    twilio_client.messages.create(
        from_=settings.TWILIO_WHATSAPP_NUMBER,
        to=from_number,
        body=result.response_text
    )
    
    return Response(content="", status_code=204)
```

**Done when**: Browser can complete a full FNOL conversation via web client. Audio flows both ways. Transcript appears in DB. FNOL record extracted and stored.

---

### Phase 4 — API Layer + Storage (2 sessions)

**Goal**: All REST endpoints work, auth protects them, audit log captures everything, tests pass.

**4a. Storage** (`storage/call_store.py`, `storage/audit_log.py`)
- `CallStore`: async CRUD for `CallRecord`, `ConversationTurn`, `FNOLRecord`, `TurnMetrics`
- `AuditLog`: append-only insert, never update/delete
- Both classes take `AsyncSession` as dependency

**4b. All API routes** (section 6)
- Implement exactly as specified
- Use `Depends(get_db)` for DB session injection
- Use `Depends(get_current_user)` for auth
- Paginate all list endpoints

**4c. Auth**
```python
# Simple but correct JWT implementation
# Scopes: "read", "write", "admin"
# Admin-only: /prompts/{id}/deploy, /prompts/{id}/rollback
# Write: POST /eval/runs, DELETE /calls/{id}
# Read: everything else (GET endpoints)
```

**4d. Rate limiting**
```python
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)

@app.get("/calls")
@limiter.limit(settings.RATE_LIMIT_API)
async def list_calls(...):
    ...
```

**Tests**: `test_api_calls.py`, `test_api_auth.py`, `test_api_prompts.py`, `test_api_diagnostics.py`

**Done when**: All API endpoints return correct responses. Auth tests confirm scope restrictions. Audit log has entries for all mutating operations.

---

### Phase 5 — Eval Suite (1 session)

**Goal**: `POST /eval/runs` triggers async eval, results queryable, markdown report generated.

**5a. Scenarios** — implement all 15 from section 14.1  
**5b. Runner** — async executor using `asyncio.gather()` for parallel scenario runs  
**5c. Scorer** — implement field-level scoring from section 14.2  
**5d. Reporter** — generate markdown report with per-scenario breakdown and delta vs baseline  
**5e. Background task** — run eval in FastAPI `BackgroundTasks`, update `EvalRun.status` in DB  

**Done when**: `POST /eval/runs` with `"all"` scenarios returns run_id, status progresses to "complete", `/report` endpoint returns meaningful markdown.

---

### Phase 6 — Observability (1 session)

**Goal**: Prometheus scrapes metrics, Grafana dashboards show real data, Langfuse traces visible.

**6a. Prometheus config** (`prometheus/prometheus.yml`):
```yaml
global:
  scrape_interval: 15s

scrape_configs:
  - job_name: vaani_backend
    static_configs:
      - targets: ['backend:8000']
    metrics_path: /metrics
```

**6b. Grafana dashboards** — create all 3 JSON dashboard files (section 13.2)  
Use Prometheus queries:
- STT P95: `histogram_quantile(0.95, rate(vaani_stt_latency_ms_bucket[5m]))`
- Active calls: `vaani_active_calls`
- Fallback rate: `rate(vaani_fallback_triggered_total[1h]) / rate(vaani_calls_total[1h])`

**6c. Langfuse** — ensure `@observe` decorator is on all LLM calls, verify traces appear in Langfuse cloud dashboard  

**6d. Grafana provisioning** — configure datasource and dashboard auto-provisioning so dashboards appear on first startup without manual setup

**Done when**: Navigate to `localhost:3001`, all 3 dashboards visible with real data from test calls.

---

### Phase 7 — Frontend (3-4 sessions)

**Goal**: Production-grade ops dashboard matching the aesthetic specification. All components functional.

**7a. Foundation**
- `lib/types.ts`: TypeScript types matching all API response shapes
- `lib/api.ts`: Typed API client using `fetch` with JWT token handling and SWR integration
- `store/callStore.ts`: Zustand store for active calls map
- `store/uiStore.ts`: UI state (selected call, sidebar state)
- `app/layout.tsx`: Sidebar + TopBar, dark theme, IBM Plex fonts from Google Fonts

**7b. Hooks**
- `useCallWebSocket.ts`: manages `/ws/live` connection, dispatches to Zustand store
- `useWaveform.ts`: Web Audio API wrapper, returns canvas draw function
- `useAudioPlayer.ts`: audio playback control for replay
- `useMetrics.ts`: polls `/diagnostics` every 10s with SWR

**7c. Components** (build in this order, each testable standalone)
1. `FNOLRecord.tsx` — pure display, no WebSocket needed
2. `CompletenessBar.tsx` — animated progress bar
3. `PipelineStages.tsx` — takes `TurnMetrics` prop, renders bars
4. `WaveformVisualizer.tsx` — canvas-based, takes MediaStream or AudioBuffer
5. `CallCard.tsx` — single call card for live dashboard
6. `LiveCallPanel.tsx` — grid of CallCards, uses useCallWebSocket
7. `ConversationReplay.tsx` — uses useAudioPlayer + transcript display
8. `PromptEditor.tsx` — Monaco editor + version list
9. `VersionDiff.tsx` — unified diff display
10. `RegressionRunner.tsx` — trigger + results table
11. `ScenarioResultCard.tsx` — expandable result row

**7d. Pages** — assemble components
- `app/page.tsx`: `<LiveCallPanel>` as main content, system health summary in header
- `app/calls/page.tsx`: `<CallHistoryTable>` with filters
- `app/calls/[id]/page.tsx`: `<ConversationReplay>` + `<FNOLRecord>` side by side
- `app/metrics/page.tsx`: Grafana embed + custom `<PipelineStages>` with historical data
- `app/prompts/page.tsx`: `<PromptEditor>` full page
- `app/eval/page.tsx`: `<RegressionRunner>` full page

**Design implementation checklist**:
- [ ] IBM Plex fonts loaded from Google Fonts in `layout.tsx`
- [ ] All CSS color tokens defined in `globals.css`
- [ ] No purple gradients, no Inter font, no generic AI aesthetic
- [ ] Amber used for amber/warning states, teal for healthy/active
- [ ] Monospace font for all latency values, call IDs, policy numbers
- [ ] Framer Motion used for card entrance animations (staggered), not decoratively
- [ ] All interactive states (hover, active, disabled) defined
- [ ] Mobile-responsive sidebar (collapses to icon bar on small screens)

**Done when**: Full flow: open browser → see live call dashboard → trigger a test call via web client → watch transcript appear in real-time → replay it → view extracted FNOL record → run eval → see accuracy report.

---

## 19. Resume Bullets

Use these exactly — they are engineered to hit JD keywords for each role.

### FDSE

```
• Built Vaani, an end-to-end multilingual FNOL voice agent for Indian insurance clients,
  deployable across phone (Twilio), web (WebSocket), and WhatsApp channels with 
  Hindi/Hinglish/English support and structured claim extraction via FSM-driven conversation flow

• Instrumented full pipeline with Prometheus metrics, Langfuse LLM tracing, and Grafana 
  dashboards; built per-call artifact storage, conversation replay, and a 15-scenario 
  prompt regression suite enabling prompt version → eval → deploy → rollback cycle
```

### Backend — Inference Pipelines

```
• Designed STT→LLM→TTS inference pipeline with per-stage Prometheus histograms (P50/P95/P99),
  circuit breaker with cooldown/recovery across Groq and Gemini providers, and parallel batch 
  TTS queue reducing synthesis latency from Σ(sentences) to max(sentences) via asyncio.gather()

• Exposed /diagnostics API with live provider health status and /metrics Prometheus endpoint;
  pipeline achieves <1000ms P95 total latency on web channel with automatic fallback routing
```

### Backend — General

```
• Built production FastAPI backend: 25+ REST endpoints (call management, prompt versioning, 
  eval runner, diagnostics), JWT auth with scope-restricted tokens, slowapi rate limiting,
  append-only audit log, async SQLite via SQLAlchemy 2.0, and 60+ pytest tests (90%+ coverage)

• Implemented multi-channel call orchestration across Twilio voice, WebSocket browser client,
  and WhatsApp; FNOL structured extraction with Pydantic validation, completeness scoring, 
  and Alembic-managed schema migrations
```

### Frontend

```
• Built ops dashboard in Next.js 15 + TypeScript: real-time call monitoring via WebSocket
  broadcast, Web Audio API waveform visualizer, live pipeline latency bars (STT/LLM/TTS) 
  with P50/P95 color coding, and synchronized conversation replay with per-turn metrics

• Implemented prompt version management UI (Monaco editor, unified diff, deploy/rollback),
  regression test runner with per-scenario accuracy breakdown, and FNOL record viewer with
  per-field confidence indicators and extraction completeness tracking
```

---

*End of specification. Total estimated build time with Claude Code: 8-12 sessions.*
