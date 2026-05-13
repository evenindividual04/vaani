# Vaani — Full Build Plan

## Context

Build Vaani from scratch: a production-grade multilingual FNOL (First Notice of Loss) voice agent for insurance. The repo currently contains only `VAANI_COMPLETE_SPEC.md`. Goal is to implement all 8 phases of the spec end-to-end, resulting in a deployable system with FastAPI backend, Next.js 15 frontend, Prometheus/Grafana observability, and a 15-scenario eval suite.

The spec is highly detailed and prescriptive. The plan is to follow it phase-by-phase, verifying each phase before starting the next.

---

## Phase 0 — Scaffolding

**Goal:** `make dev` runs; health check returns 200; Next.js accessible on :3000; Grafana on :3001.

### Files to create

**Root:**
- `docker-compose.yml` — backend + frontend + prometheus + grafana services
- `docker-compose.dev.yml` — volume mounts for hot reload
- `.env.example` — all vars from spec §5
- `Makefile` — dev, prod, test, migrate, lint, seed-prompts, clean targets

**Backend:**
- `backend/requirements.txt` — all packages from spec §3
- `backend/pyproject.toml` — ruff + mypy config
- `backend/app/__init__.py`
- `backend/app/main.py` — FastAPI app, lifespan (init_db + seed), CORS, /metrics mount, /health endpoint
- `backend/app/config.py` — pydantic-settings Settings class, all env vars from §5
- `backend/app/storage/__init__.py`
- `backend/app/storage/database.py` — async SQLite engine, session factory, `get_db` dependency
- `backend/app/storage/models.py` — all 7 SQLAlchemy models from §10 (CallRecord, ConversationTurn, FNOLRecord, TurnMetrics, PromptVersion, EvalRun, AuditLog, AudioArtifact)
- `backend/migrations/env.py` + first migration via `alembic init` + `alembic revision --autogenerate`
- `backend/prometheus/prometheus.yml`
- `backend/grafana/provisioning/datasources/prometheus.yml`
- `backend/grafana/provisioning/dashboards/dashboards.yml`
- `backend/Dockerfile` — multi-stage dev/production

**Frontend:**
- `frontend/package.json` — all packages from spec §3
- `frontend/tsconfig.json`
- `frontend/tailwind.config.ts`
- `frontend/src/styles/globals.css` — all CSS color tokens from §15.1
- `frontend/src/app/layout.tsx` — IBM Plex fonts, Sidebar + TopBar shells
- `frontend/src/app/page.tsx` — placeholder
- `frontend/Dockerfile` — multi-stage dev/production

**Verify:** `make dev` → `curl localhost:8000/health` → `{"status": "ok"}`, browser opens :3000, Grafana at :3001.

---

## Phase 1 — Inference Pipeline

**Goal:** `PipelineOrchestrator.run_turn()` works end-to-end with real APIs, emits Prometheus metrics, handles provider failure.

### Build order

**1a. Circuit Breaker** — `backend/app/pipeline/circuit_breaker.py`
- Implement `CircuitBreaker` dataclass exactly per §12.1
- States: HEALTHY → COOLING_DOWN → DISABLED
- Tests: `backend/tests/test_circuit_breaker.py` — all state transitions, cooldown expiry, disable threshold (100% coverage target)

**1b. Metrics** — `backend/app/pipeline/metrics.py`
- All Prometheus metrics from §12.3: histograms (STT/LLM/TTS/pipeline latency, FNOL completeness), counters (calls, errors, fallbacks, CB opens), gauges (active calls, provider health)
- `record_pipeline_turn()` helper

**1c. STT** — `backend/app/pipeline/stt.py`
- `SarvamSTT` class wrapping `sarvamai` SDK, circuit breaker, timing, Prometheus emit
- Returns `STTResult(transcript, language_code, latency_ms)`
- Tests: `test_pipeline_stt.py` — success, timeout, audio format error, CB trigger

**1d. LLM** — `backend/app/pipeline/llm.py`
- `GroqLLM` (primary) + `GeminiLLM` (fallback) + `LLMRouter`
- Track TTFT (time to first token)
- Langfuse `@observe` decorator on all completions
- Returns `LLMResult(text, latency_ms, ttft_ms, fallback_used)`
- Tests: `test_pipeline_llm.py` — success, fallback triggered, CB open, TTFT tracking

**1e. TTS** — `backend/app/pipeline/tts.py`
- `SarvamTTS` with `synthesize_parallel()` using `asyncio.gather()` per §12.2
- `split_into_sentences()` with Hindi danda `।` support
- `generate_silence_wav()` for failed sentence substitution
- Tests: `test_pipeline_tts.py` — parallel batch success, partial failure, sentence splitting

**1f. VAD** — `backend/app/pipeline/vad.py`
- `SileroVAD` wrapper loading `snakers4/silero-vad` via torch.hub
- `is_speech(pcm_bytes, sample_rate) -> bool` using `VAD_THRESHOLD` setting

**1g. Audio utils** — `backend/app/pipeline/audio.py`
- `AudioBuffer` class (20ms chunks, 300ms flush, 10s max) per §9
- `convert_twilio_chunk()` — μ-law → PCM 16-bit 8kHz
- `upsample_to_16k()` — 8kHz → 16kHz via audioop.ratecv
- `build_wav_bytes()` — wrap PCM in WAV container
- `send_audio_to_twilio()` — WAV → μ-law → base64 → WebSocket JSON

**1h. Orchestrator** — `backend/app/pipeline/orchestrator.py`
- `PipelineOrchestrator.run_turn(audio_wav, text_input, history, call_id, language, prompt_version) -> PipelineTurnResult`
- Chains STT → LLM → TTS, records all metrics
- Tests: `test_pipeline_orchestrator.py` — full pipeline mocked, partial (text input skips STT), error propagation

**Verify:** `pytest tests/test_pipeline* -v` all pass (mocked). Manual integration test with real audio file produces transcript + response + audio.

---

## Phase 2 — Domain Logic

**Goal:** Full conversation flow GREETING → COMPLETE works in isolation without HTTP layer.

**2a. Language detection** — `backend/app/domain/language.py`
- Primary: use Sarvam STT `language_code` field
- Fallback: Devanagari character ratio heuristic per §11.3
- Lock language after `LANGUAGE_DETECTION_TURNS` turns

**2b. Prompt loader** — `backend/app/domain/prompts/loader.py`
- `PromptLoader.get(key, version, language) -> str`
- Maps to `templates/{version}/{key}_{lang_suffix}.txt`
- Falls back to v1 filesystem if DB version not found

**2c. Prompt templates** — `backend/app/domain/prompts/templates/v1/`
- 11 files: `greeting_hi.txt`, `greeting_en.txt`, `policy_verify_hi.txt`, `policy_verify_en.txt`, `incident_capture_hi.txt`, `incident_capture_en.txt`, `details_capture_hi.txt` (with `{{missing_fields}}`), `details_capture_en.txt`, `summary_hi.txt`, `summary_en.txt`, `extractor_system.txt`
- Each prompt: professional, empathetic, ≤2 sentences, in the correct language

**2d. Conversation FSM** — `backend/app/domain/fsm.py`
- All 7 states from §11.1: GREETING, POLICY_VERIFY, INCIDENT_CAPTURE, DETAILS_CAPTURE, CONTACT_VERIFY, SUMMARY, COMPLETE
- `ConversationFSM.advance(fnol_record) -> FsmTransition | None`
- Tracks reprompt count, emits structlog on transitions
- Tests: `test_domain_fsm.py` — all transitions, max reprompts, fallback states

**2e. FNOL Extractor** — `backend/app/domain/extractor.py`
- Uses `extractor_system.txt` prompt + formatted transcript
- JSON-constrained output → Pydantic `FNOLRecord`
- Retry once on JSON parse failure with "RESPOND ONLY WITH JSON" suffix
- Tests: `test_domain_extractor.py` — all 5 scenario types, partial extraction, JSON failure + retry

**2f. Completeness Validator** — `backend/app/domain/validator.py`
- Required fields × 0.15 + optional fields × 0.05 per §2e
- `compute_completeness(record) -> float`
- Tests: `test_domain_validator.py` — all completeness thresholds, confidence gating

**Verify:** Script that feeds scenario H1 transcript through FSM + extractor produces correct FNOLRecord.

---

## Phase 3 — Channel Handlers

**Goal:** Browser can complete full FNOL call; Twilio handler connects.

**3a. WebSocket browser channel** — `backend/app/channels/websocket_handler.py`
- `/ws/call?token=<jwt>` — JWT validation, audio buffer, VAD-triggered turn processing
- Sends `call_ready`, `agent_audio`, `agent_text`, `vad_state`, `error` messages
- Broadcasts to live monitor after each turn

**3b. Live monitor WebSocket** — same file
- `LiveMonitorManager` with broadcast to all connected dashboards
- `/ws/live?token=<jwt>` — all message types from §7: call_started, transcript_turn, pipeline_metrics, fnol_update, fsm_transition, call_ended, provider_health_change

**3c. Twilio voice handler** — `backend/app/channels/twilio_handler.py`
- `/voice/incoming` — validate Twilio signature, return TwiML for Media Streams
- `/voice/stream` WebSocket — handle connected/start/media/stop/mark events per §9
- Audio conversion pipeline: μ-law → PCM → buffer → STT
- Response audio: WAV → μ-law → send back per §9

**3d. WhatsApp handler** — `backend/app/channels/whatsapp_handler.py`
- `/webhook/whatsapp` — text-only pipeline, session management by phone number
- Responds via Twilio SDK

**Verify:** Full end-to-end: browser WebSocket → GREETING → COMPLETE, DB has call record + transcript + FNOL.

---

## Phase 4 — API Layer + Storage

**Goal:** All 25+ REST endpoints work, auth enforces scopes, audit log populated.

**4a. Storage layer**
- `backend/app/storage/call_store.py` — `CallStore`: async CRUD for all call-related tables
- `backend/app/storage/audit_log.py` — `AuditLog`: append-only insert only

**4b. API routes** matching spec §6:
- `backend/app/api/auth.py` — `/auth/login`, `/auth/refresh`, `/auth/revoke`; JWT scopes: read/write/admin
- `backend/app/api/calls.py` — GET /calls (paginated, filtered), GET /calls/{id}, GET /calls/{id}/audio, GET /calls/{id}/replay, DELETE /calls/{id}
- `backend/app/api/prompts.py` — CRUD + deploy + rollback + diff
- `backend/app/api/diagnostics.py` — `/diagnostics` aggregating circuit breaker state + recent metrics
- `backend/app/api/eval.py` — POST /eval/runs (BackgroundTask), GET /eval/runs, GET /eval/runs/{id}, GET /eval/runs/{id}/report
- `backend/app/api/router.py` — wire all routers into main app

**4c. Rate limiting** — slowapi on all endpoints per §5 env vars

**4d. Tests:** `test_api_calls.py`, `test_api_auth.py`, `test_api_prompts.py`, `test_api_diagnostics.py` — scope restrictions, pagination, soft delete, audit entries

**Verify:** All endpoints return correct responses. `pytest tests/test_api* -v` passes. Auth scope tests confirm 403 on wrong scope.

---

## Phase 5 — Eval Suite

**Goal:** `POST /eval/runs` triggers async eval, results queryable.

- `backend/app/eval/scenarios.py` — all 15 scenarios from §14.1 (H1-H5, E1-E5, X1-X5)
- `backend/app/eval/runner.py` — `asyncio.gather()` parallel execution, `score_scenario()` per §14.2
- `backend/app/eval/reporter.py` — markdown report with per-scenario breakdown and baseline delta
- Wire into `api/eval.py` BackgroundTasks, update `EvalRun.status` in DB
- Tests: `test_eval_runner.py` — scenario execution, field-level scoring, baseline comparison

**Verify:** `POST /eval/runs {"scenario_ids": "all"}` → `run_id`, status progresses to "complete", markdown report returned.

---

## Phase 6 — Observability

**Goal:** Grafana shows real data from test calls.

- `backend/prometheus/prometheus.yml` — scrape backend:8000/metrics every 15s
- `backend/grafana/dashboards/pipeline_health.json` — STT/LLM/TTS P50/P95/P99, CB events, fallback rate
- `backend/grafana/dashboards/call_analytics.json` — active calls, calls/hour, outcome/channel/language pies, P95 latency trend
- `backend/grafana/dashboards/fnol_accuracy.json` — completeness distribution, per-field rates, eval scores
- `backend/grafana/provisioning/` — auto-provision datasource and all 3 dashboards
- Verify Langfuse `@observe` traces visible in cloud dashboard

**Verify:** :3001 shows all 3 dashboards with real data after running test calls.

---

## Phase 7 — Frontend

**Goal:** Production-grade ops dashboard matching spec §15 aesthetic (dark/amber/teal, IBM Plex fonts).

**7a. Foundation**
- `frontend/src/lib/types.ts` — all TypeScript types matching API shapes
- `frontend/src/lib/api.ts` — typed fetch client, JWT handling, SWR integration
- `frontend/src/lib/utils.ts` — formatting helpers
- `frontend/src/store/callStore.ts` — Zustand store: active calls map, dispatch WS events
- `frontend/src/store/uiStore.ts` — selected call, sidebar open state
- `frontend/src/app/layout.tsx` — IBM Plex Sans/Mono from Google Fonts, Sidebar, TopBar

**7b. Hooks**
- `useCallWebSocket.ts` — `/ws/live` connection, dispatch to Zustand
- `useWaveform.ts` — Web Audio API AnalyserNode, canvas draw function, 60fps RAF
- `useAudioPlayer.ts` — playback control for replay, speed controls
- `useMetrics.ts` — SWR poll `/diagnostics` every 10s

**7c. Components** (in build order)
1. `FNOLRecord.tsx` — 2-col grid, confidence dots, completeness bar, "FNOL COMPLETE" badge
2. `CompletenessBar.tsx` — animated progress bar, color-coded by score
3. `PipelineStages.tsx` — STT/LLM/TTS bars, P50/P95 color coding, fallback badge, sparkline on click
4. `WaveformVisualizer.tsx` — canvas, 64 frequency buckets, VAD state colors, 0.85x decay
5. `CallCard.tsx` — channel/language badges, duration counter, FSM badge, FNOL bar, latency mini-bars
6. `LiveCallPanel.tsx` — WebSocket grid of CallCards, empty state, slide-in animation
7. `ConversationReplay.tsx` — AudioPlayer + timeline scrubber + transcript + FNOL panel + FSM indicator
8. `PromptEditor.tsx` — Monaco editor, version list with ACTIVE badge, diff toggle, deploy/rollback actions
9. `VersionDiff.tsx` — unified diff with line-level highlights
10. `RegressionRunner.tsx` — trigger form, progress, results table with per-field dots and delta
11. `ScenarioResultCard.tsx` — expandable row with field/expected/extracted breakdown

**7d. Pages**
- `app/page.tsx` — `<LiveCallPanel>` + system health header
- `app/calls/page.tsx` — `<CallHistoryTable>` with channel/language/outcome/date filters
- `app/calls/[id]/page.tsx` — `<ConversationReplay>` + `<FNOLRecord>` side-by-side
- `app/metrics/page.tsx` — Grafana iframe + `<PipelineStages>` with historical data
- `app/prompts/page.tsx` — `<PromptEditor>` full page
- `app/eval/page.tsx` — `<RegressionRunner>` full page

**Verify:** Browser test — open :3000, trigger web call, watch transcript appear live, replay it, view FNOL, run eval, see accuracy report.

---

## Implementation Order Within Each Phase

Follow spec §18 rule: **never start the next phase until current phase has passing tests**.

Each phase ends with its own verification step as described above.

## Key Spec References

| Concern | Spec Section |
|---------|-------------|
| API contracts | §6 |
| WebSocket protocol | §7 |
| Sarvam API usage | §8 |
| Twilio audio conversion | §9 |
| DB schema | §10 |
| FSM states/transitions | §11.1 |
| FNOL extractor prompt | §11.2 |
| Circuit breaker | §12.1 |
| Parallel TTS | §12.2 |
| Prometheus metrics | §12.3 |
| Grafana dashboards | §13.2 |
| Eval scenarios | §14.1 |
| Eval scoring | §14.2 |
| Frontend aesthetic | §15.1 |
| Component specs | §15.2 |
| Test fixtures/strategy | §16 |
| Docker config | §17 |
