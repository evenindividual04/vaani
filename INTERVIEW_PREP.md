# Vaani FNOL Agent — Sarvam AI FDSE Interview Prep Guide

---

## 1. SYSTEM ARCHITECTURE

### End-to-End Call Flow

Three inbound channels converge on the same core pipeline:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  CHANNEL ENTRY                                                              │
│                                                                             │
│  Twilio Phone  ──→  POST /voice/incoming  (TwiML XML response)             │
│                     Twilio dials back on  WS /voice/stream                 │
│                     20ms μ-law chunks arrive as "media" events             │
│                                                                             │
│  Browser       ──→  WS /ws/call  (JWT-authenticated)                      │
│                     PCM chunks arrive as audio_chunk JSON messages         │
│                                                                             │
│  WhatsApp      ──→  POST /webhook/whatsapp  (Twilio form POST)            │
│                     Plain text "Body" — no audio at all                    │
└────────────────────────┬────────────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  AUDIO INGESTION (voice channels only)                                      │
│                                                                             │
│  Twilio:   base64 decode → audioop.ulaw2lin → audioop.ratecv(8k→16k)     │
│  Browser:  raw PCM 16k arrives directly                                    │
│                                                                             │
│  AudioBuffer accumulates 20ms chunks                                       │
│  Flush trigger: MAX_MS=10000ms OR (should_flush_on_silence AND !VAD)      │
│  SileroVAD checks confidence > VAD_THRESHOLD (default 0.5)                │
│  On flush: build_wav_bytes() wraps PCM in WAV container                    │
└────────────────────────┬────────────────────────────────────────────────────┘
                         │ WAV bytes
                         ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  PipelineOrchestrator.run_turn()                                            │
│                                                                             │
│  1. STT: SarvamSTT.transcribe()                                            │
│     - Wraps WAV in io.BytesIO, calls saarika:v2.5 synchronously           │
│     - Returns STTResult(transcript, language_code, latency_ms)             │
│     - Records STT_LATENCY histogram                                        │
│                                                                             │
│  2. LLM: LLMRouter.complete()                                              │
│     - _build_messages() assembles [system, ...history, user_turn]         │
│     - GroqLLM: streaming (llama-3.3-70b-versatile), TTFT captured         │
│     - Falls back to GeminiLLM if circuit breaker not available             │
│     - Records LLM_LATENCY + LLM_TTFT histograms                           │
│                                                                             │
│  3. TTS: SarvamTTS.synthesize_parallel()                                   │
│     - split_into_sentences() splits on [।.!?] (Devanagari-aware)         │
│     - asyncio.gather fires all sentences simultaneously (bulbul:v2)        │
│     - Returns ordered audio_chunks; failed sentences → silence             │
│     - Records TTS_LATENCY histogram                                        │
└────────────────────────┬────────────────────────────────────────────────────┘
                         │ PipelineTurnResult
                         ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  CONVERSATION MANAGEMENT (per handler)                                      │
│                                                                             │
│  ConversationFSM.add_turn("user", transcript)                              │
│  ConversationFSM.add_turn("agent", response_text)                          │
│  LanguageTracker.update() — locks language after LANGUAGE_DETECTION_TURNS  │
│  FNOLExtractor.extract(fsm.history) — separate LLM JSON extraction        │
│  ConversationFSM.advance(fnol_data) — state transition check              │
│                                                                             │
│  DB write: CallStore.add_turn(), upsert_fnol(), record_turn_metrics()     │
│  live_manager.broadcast() → all /ws/live subscribers                       │
└────────────────────────┬────────────────────────────────────────────────────┘
                         │ audio_chunks
                         ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  AUDIO OUTPUT                                                               │
│                                                                             │
│  Twilio:   strip_wav_header → ratecv(16k→8k) → audioop.lin2ulaw          │
│            base64-encode → send_json(event:"media")                        │
│                                                                             │
│  Browser:  base64-encode WAV → send_json(type:"agent_audio")              │
│                                                                             │
│  WhatsApp: Twilio REST API client.messages.create(body=text)              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Component Connections

| Component | File | Connects To |
|---|---|---|
| `PipelineOrchestrator` | `pipeline/orchestrator.py` | `SarvamSTT`, `LLMRouter`, `SarvamTTS` |
| `LLMRouter` | `pipeline/llm.py` | `GroqLLM` (primary), `GeminiLLM` (fallback), each wraps `CircuitBreaker` |
| `ConversationFSM` | `domain/fsm.py` | Stateful per-call, driven by channel handlers |
| `FNOLExtractor` | `domain/extractor.py` | Calls `LLMRouter.complete()` with a separate extraction prompt |
| `AudioBuffer` | `pipeline/audio.py` | Receives raw chunks from handlers, flushes WAV to orchestrator |
| `SileroVAD` | `pipeline/vad.py` | Consulted by browser WebSocket handler before flushing |
| `live_manager` | `channels/websocket_handler.py` | Singleton `LiveMonitorManager`; all voice turns broadcast to `/ws/live` |
| `PromptLoader` | `domain/prompts/loader.py` | Filesystem cache; `settings.ACTIVE_PROMPT_VERSION` controls which version |
| `CircuitBreaker` | `pipeline/circuit_breaker.py` | One instance per provider: `sarvam_stt`, `sarvam_tts`, `groq`, `gemini` |

### Async / Concurrent Execution Patterns

- **`asyncio.gather`** in `tts.py:92` — fires all TTS sentence coroutines concurrently
- **`asyncio.gather`** in `eval/runner.py:150` — runs all 15 eval scenarios concurrently
- **Background `asyncio.sleep(30)` heartbeat** in `websocket_handler.py:317` — keeps live monitor connections alive through proxies
- **`async with AsyncSessionFactory()`** — each request opens/closes its own DB session; no connection held across turns
- **`httpx.AsyncClient`** — FNOL webhook POSTed asynchronously after completeness ≥ 0.9 (`websocket_handler.py:265`)

---

## 2. THE 7-STATE FSM

### State Names (exact enum values from `domain/fsm.py:13`)

```python
class FsmState(str, Enum):
    GREETING         = "GREETING"
    POLICY_VERIFY    = "POLICY_VERIFY"
    INCIDENT_CAPTURE = "INCIDENT_CAPTURE"
    DETAILS_CAPTURE  = "DETAILS_CAPTURE"
    CONTACT_VERIFY   = "CONTACT_VERIFY"
    SUMMARY          = "SUMMARY"
    COMPLETE         = "COMPLETE"
    ERROR            = "ERROR"
```

> There are 8 values in the enum (7 conversational + ERROR). The class docstring says "7 states" referring to the conversational flow states; ERROR is a terminal escape hatch only reachable from GREETING.

### Valid Transitions with Trigger Conditions

```
GREETING ──────────────────────────────────────────────────────────────────
  exit_condition:  any turn where speaker == "user" exists in history
  max_reprompts:   2
  on success  → POLICY_VERIFY       (trigger: "exit_condition_met")
  on max      → ERROR               (trigger: "max_reprompts_exceeded")

POLICY_VERIFY ─────────────────────────────────────────────────────────────
  exit_condition:  fnol_record.get("policy_number") is truthy
  max_reprompts:   3
  on success  → INCIDENT_CAPTURE    (trigger: "exit_condition_met")
  on max      → INCIDENT_CAPTURE    (trigger: "max_reprompts_exceeded")  ← fallback == next

INCIDENT_CAPTURE ──────────────────────────────────────────────────────────
  exit_condition:  incident_type AND incident_date both present in fnol_record
  max_reprompts:   3
  on success  → DETAILS_CAPTURE
  on max      → DETAILS_CAPTURE

DETAILS_CAPTURE ───────────────────────────────────────────────────────────
  exit_condition:  completeness_score >= 0.8
  max_reprompts:   5
  on success  → CONTACT_VERIFY
  on max      → CONTACT_VERIFY

CONTACT_VERIFY ─────────────────────────────────────────────────────────────
  exit_condition:  callback_number present in fnol_record
  max_reprompts:   2
  on success  → SUMMARY
  on max      → SUMMARY

SUMMARY ────────────────────────────────────────────────────────────────────
  exit_condition:  reprompt_count >= 1  (always advances after one turn here)
  max_reprompts:   2
  on success  → COMPLETE
  on max      → COMPLETE

COMPLETE / ERROR ───────────────────────────────────────────────────────────
  advance() returns None immediately — terminal states, no further transitions
```

Key design choice: for POLICY_VERIFY through SUMMARY the **fallback == next** — the conversation always moves forward even if the required field was not captured. Only GREETING can hard-stop into ERROR.

### What Happens on Invalid / Unexpected Input

There is **no explicit guard** for invalid transitions. `advance()` (`fsm.py:95`) follows this logic:

1. If `state in (COMPLETE, ERROR)` → return `None` immediately
2. Check `_check_exit_condition(fnol_record)`
3. If exit met → `_transition_to(config["next"], "exit_condition_met")`
4. If `reprompt_count >= max_reprompts` → `_transition_to(config["fallback"], "max_reprompts_exceeded")`
5. Else → `reprompt_count += 1`, return `None` (stay in state, reprompt)

No exception is raised for unexpected input. `reprompt_count` resets to 0 on every successful transition (`_transition_to:145`).

### Why FSM Was Chosen Over Alternatives

**Problem FSM solves:** Without state tracking, an LLM can skip required fields, loop on one topic, or summarise prematurely. The FSM enforces a *guaranteed* sequential data-gathering contract regardless of which LLM or provider is running.

**Concrete benefits in this code:**
- System prompt switches per state via `get_prompt(fsm.current_prompt_key, ...)` — the LLM is told to do exactly one task per turn
- `max_reprompts` gives deterministic call length bounds, critical for voice UX
- FSM transitions are observable events broadcast to `/ws/live` in real time
- Unit tests can verify exit conditions against a plain Python dict — no LLM needed in tests

**Alternative rejected:** Single prompt with full task list. Requires the LLM to self-track completeness, decide when to advance, and avoid loops — things LLMs do inconsistently across providers and temperature settings. Moving that control flow into Python makes it testable and provider-independent.

---

## 3. LLM INTEGRATION

### Conversation Prompt Structure

Built by `_build_messages()` in `pipeline/orchestrator.py:36`:

```python
[
  {"role": "system",    "content": <state-specific prompt from PromptLoader>},
  {"role": "user",      "content": <turn 1 user text>},
  {"role": "assistant", "content": <turn 1 agent text>},
  {"role": "user",      "content": <turn 2 user text>},
  {"role": "assistant", "content": <turn 2 agent text>},
  ...
  {"role": "user",      "content": <current STT transcript>},
]
```

The system prompt is loaded per FSM state. In `INCIDENT_CAPTURE`, the prompt instructs the LLM to focus only on incident type and date. The full conversation history spans state boundaries — only the system prompt changes as the FSM advances.

### Extraction Prompt Structure

`FNOLExtractor.extract()` (`domain/extractor.py:158`) constructs a **completely separate** LLM call:

```python
[
  {"role": "system", "content": EXTRACTOR_SYSTEM_PROMPT},
  {"role": "user",   "content": "Extract FNOL data from this conversation:\n\n{transcript}"}
]
```

`EXTRACTOR_SYSTEM_PROMPT` (`extractor.py:13`) specifies:
- 11 fields to extract: `policy_number`, `incident_type`, `incident_date`, `incident_location`, `injuries_reported`, `injury_description`, `vehicle_damage`, `damage_description`, `third_party_involved`, `callback_number`, `preferred_language`
- Per-field confidence scores 0.0–1.0 with defined bands (0.9–1.0 = explicit, 0.6–0.8 = inferred, 0.3–0.5 = guessed)
- Hindi/Hinglish handling instructions ("15 March ko" = 2024-03-15)
- Strict output rule: "Return ONLY valid JSON. No preamble, no explanation."

### How JSON-Constrained Extraction Works

**Technique:** Plain-text instruction constraint — not Groq's JSON mode or function calling. The system prompt ends with a precise JSON schema. This works well with Llama 3.3 70B but is not guaranteed.

**Parse flow** (`extractor.py:96–105`):

```python
def _parse_json(text: str) -> dict | None:
    cleaned = text.strip()
    if cleaned.startswith("```"):          # strip markdown code fences
        lines = cleaned.split("\n")
        cleaned = "\n".join(lines[1:-1] if lines[-1] == "```" else lines[1:])
    return json.loads(cleaned)             # returns None on JSONDecodeError
```

**On parse failure:**
1. First attempt fails → retry with `"RESPOND ONLY WITH JSON. NO EXPLANATIONS."` appended (`extractor.py:179`)
2. Second attempt also fails → return `dict(EMPTY_FNOL)` — all fields `None`, `completeness_score: 0.0`

### How Claim Record Validation Works

`_validate_and_clean()` (`extractor.py:108`) runs after every successful parse:

- `incident_type` must be in `{"accident","theft","fire","flood","natural_disaster","medical","other"}` — else coerced to `"other"`
- `preferred_language` must be `"hi-IN"` or `"en-IN"` — else defaults to `"hi-IN"`
- `compute_completeness()` (`domain/validator.py:26`) calculates the score:

```python
REQUIRED_FIELDS = ["policy_number","incident_type","incident_date","incident_location","callback_number"]
OPTIONAL_FIELDS = ["injuries_reported","vehicle_damage","third_party_involved","injury_description"]

REQUIRED_WEIGHT = 0.15   # 5 × 0.15 = 0.75 total max
OPTIONAL_WEIGHT = 0.05   # 4 × 0.05 = 0.25 total max
CONFIDENCE_THRESHOLD = 0.5

# A field counts only if: value is not None AND confidence > 0.5
```

Score drives the `DETAILS_CAPTURE` exit condition (`completeness_score >= 0.8`) and the FNOL webhook trigger (`completeness_score >= 0.9`).

---

## 4. CIRCUIT BREAKER

### Exact Implementation (`pipeline/circuit_breaker.py`)

Three states: `HEALTHY`, `COOLING_DOWN`, `DISABLED`

**Parameters (from `config.py`, set via `.env`):**

```python
CB_ERROR_THRESHOLD:  int = 3    # consecutive failures to enter COOLING_DOWN
CB_COOLDOWN_SECONDS: int = 60   # how long COOLING_DOWN lasts
CB_DISABLE_THRESHOLD: int = 3   # number of cooldown cycles before DISABLED
```

**State machine in full:**

```
HEALTHY
  record_failure():
    consecutive_errors++
    if consecutive_errors >= 3:
      cooldown_cycles++
      if cooldown_cycles >= 3: state → DISABLED
      else: state → COOLING_DOWN, cooling_until = now + 60s

COOLING_DOWN
  is_available():
    if now > cooling_until:
      state → HEALTHY, consecutive_errors = 0
      return True
    return False
  record_success():
    state → HEALTHY, cooldown_cycles = 0, cooling_until = None

DISABLED
  is_available(): always False (no self-recovery without process restart)
```

**Notable:** There is no half-open probe state. Recovery from `COOLING_DOWN` is purely time-based — after 60s, `is_available()` spontaneously returns True and moves back to HEALTHY. The first call after cooldown is a live probe, not a controlled single test.

### Groq → Gemini Fallback Trigger (`llm.py:187–209`)

```python
async def complete(self, messages, call_id, purpose) -> LLMResult:
    override = get_llm_provider_override()     # "auto" / "groq" / "gemini"

    if override == "groq":   return await self.primary.complete(...)
    if override == "gemini": return await self.fallback.complete(...)

    # auto mode — two independent fallback triggers:
    if self.primary.circuit_breaker.is_available():
        try:
            return await self.primary.complete(...)    # GroqLLM
        except Exception:
            pass   # falls through to fallback

    FALLBACKS_TRIGGERED.labels(...).inc()
    return await self.fallback.complete(...)            # GeminiLLM
```

**Two independent triggers for fallback:**
1. `circuit_breaker.is_available()` returns False (CB in COOLING_DOWN or DISABLED)
2. Groq raises any exception on the current call — even if CB is still HEALTHY

Each provider (`groq`, `gemini`, `sarvam_stt`, `sarvam_tts`) has its own `CircuitBreaker` instance, tracking failures independently.

---

## 5. AUDIO PIPELINE

### µ-law ↔ PCM Conversion (`pipeline/audio.py`)

Twilio uses µ-law (G.711) at 8 kHz because PSTN telephony was designed around it — µ-law compresses 13-bit PCM into 8 bits, reducing bandwidth while maintaining voice quality in the 300–3400 Hz speech band.

**Inbound (Twilio → Sarvam STT):**

```python
# convert_twilio_chunk() — audio.py:16
mulaw_bytes = base64.b64decode(b64_payload)
pcm_8k = audioop.ulaw2lin(mulaw_bytes, 2)                          # μ-law → 16-bit PCM
pcm_16k, state = audioop.ratecv(pcm_8k, 2, 1, 8000, 16000, state) # 8k → 16k upsample
```

Sarvam's Saarika expects 16 kHz — hence the upsample. The resampler `state` is stored in `AudioBuffer._upsample_state` and passed across chunks to maintain filter continuity across 20ms boundaries.

**Outbound (Sarvam TTS → Twilio):**

```python
# send_audio_to_twilio() — audio.py:55
pcm_16k = strip_wav_header(wav_bytes)
pcm_8k, _ = audioop.ratecv(pcm_16k, 2, 1, 16000, 8000, None)     # 16k → 8k downsample
mulaw_bytes = audioop.lin2ulaw(pcm_8k, 2)                          # PCM → μ-law
audio_b64 = base64.b64encode(mulaw_bytes).decode("utf-8")
await ws.send_json({"event": "media", "streamSid": stream_sid, "media": {"payload": audio_b64}})
```

### VAD-Gated Buffering

**`AudioBuffer`** thresholds (`audio.py:73`):

| Constant | Value | Meaning |
|---|---|---|
| `CHUNK_MS` | 20 | Each incoming Twilio chunk = 20ms of audio |
| `FLUSH_MS` | 300 | Minimum buffer size to trigger VAD-gated silence flush |
| `MAX_MS` | 10000 | Hard cap — flush regardless after 10 seconds |

**VAD gate condition** in browser handler (`websocket_handler.py:144`):

```python
if vad and audio_buffer.should_flush_on_silence():   # buffer >= 300ms
    if not vad.is_speech(pcm):                        # VAD says this chunk is silence
        flushed = audio_buffer.flush()
```

**`SileroVAD.is_speech()`** (`vad.py:39`):

```python
audio_tensor = torch.frombuffer(pcm, dtype=torch.int16).float() / 32768.0
confidence = _model(audio_tensor, sample_rate).item()
return confidence > settings.VAD_THRESHOLD   # default 0.5
```

Graceful degradation: if Silero fails to load, `_model` is `None` and `is_speech()` returns `True` — audio always passes through, just no VAD gating. On VAD inference error, also returns `True`.

### Parallel Batch TTS via `asyncio.gather`

**Without parallelism:** Synthesising 3 sentences serially = latency₁ + latency₂ + latency₃

**With `asyncio.gather`** (`tts.py:82–93`):

```python
async def synthesize_one(text: str, index: int) -> tuple[int, bytes]:
    resp = await self.async_client.text_to_speech.convert(...)
    audio = base64.b64decode(resp.audios[0])
    return index, audio

tasks = [synthesize_one(s, i) for i, s in enumerate(sentences)]
results = await asyncio.gather(*tasks, return_exceptions=True)
```

All N API calls fire simultaneously. Wall-clock latency = **max(sentence_latencies)**, not their sum.

The `(index, audio)` tuple preserves ordering after gather. Failed sentences (returned as `Exception` by `return_exceptions=True`) are replaced with `generate_silence_wav(500)` — 500ms of silence.

**Why this works:** Each Sarvam TTS call is stateless per sentence — no dependency between requests. asyncio handles I/O concurrency on a single thread without GIL contention.

### Prometheus Histograms — Stages and Bucket Boundaries

```python
# pipeline/metrics.py

STT_LATENCY  = Histogram("vaani_stt_latency_ms",
    labels=["provider", "language", "channel"],
    buckets=[50, 100, 200, 300, 500, 750, 1000, 1500, 2000, 5000])

LLM_LATENCY  = Histogram("vaani_llm_latency_ms",
    labels=["provider", "model"],
    buckets=[100, 200, 500, 750, 1000, 1500, 2000, 3000, 5000, 10000])

LLM_TTFT     = Histogram("vaani_llm_ttft_ms",       # time-to-first-token
    labels=["provider", "model"],
    buckets=[50, 100, 150, 200, 300, 500, 750, 1000, 2000])

TTS_LATENCY  = Histogram("vaani_tts_latency_ms",    # parallel batch wall-clock
    labels=["provider", "language"],
    buckets=[50, 100, 200, 300, 500, 750, 1000, 1500, 2000])

PIPELINE_LATENCY = Histogram("vaani_pipeline_total_latency_ms",
    labels=["channel"],
    buckets=[200, 500, 750, 1000, 1500, 2000, 3000, 5000])

FNOL_COMPLETENESS = Histogram("vaani_fnol_completeness_score",
    buckets=[0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0])
```

Counters: `CALLS_TOTAL` (channel/language/outcome), `PROVIDER_ERRORS` (stage/provider/error_type), `FALLBACKS_TRIGGERED` (stage/from/to), `CIRCUIT_BREAKER_OPENS` (provider)

Gauges: `ACTIVE_CALLS` (channel), `PROVIDER_HEALTH` (stage/provider — 1.0=healthy, 0.5=cooling_down, 0.0=disabled)

All per-turn metrics are recorded in one call to `record_pipeline_turn()` at the end of `PipelineOrchestrator.run_turn()`.

---

## 6. OPS DASHBOARD

### WebSocket Real-Time Architecture

Two WebSocket endpoints serve different purposes:

**`/ws/call`** (`websocket_handler.py:94`) — per-call bidirectional channel for the caller/agent:
- Inbound: `audio_chunk`, `text_input`, `end_call`
- Outbound: `agent_audio`, `agent_text`, `call_ready`, `error`

**`/ws/live`** (`websocket_handler.py:307`) — read-only fan-out for the ops dashboard:
- `LiveMonitorManager` holds `connections: list[WebSocket]` of all connected dashboard clients
- Every voice turn triggers these broadcasts in `_process_voice_turn()`:

```python
await live_manager.broadcast({"type": "transcript_turn", ...})    # speaker/text/language/fsm_state
await live_manager.broadcast({"type": "pipeline_metrics", ...})   # stt_ms/llm_ms/tts_ms/providers
await live_manager.broadcast({"type": "fnol_update", ...})        # fields/completeness/missing_fields
if transition:
    await live_manager.broadcast({"type": "fsm_transition", ...}) # from_state/to_state/trigger
# at call boundaries:
await live_manager.broadcast({"type": "call_started", ...})
await live_manager.broadcast({"type": "call_ended", ...})
```

Dead connections are silently pruned in `broadcast()` — any `send_json` exception adds that socket to a `dead` list and removes it after the loop.

**Heartbeat:** `/ws/live` handler sleeps 30s and sends `{"type": "ping"}` to keep connections alive through proxies (`websocket_handler.py:317`).

### Prompt Version Management (`api/prompts.py`)

**Storage:** `PromptVersion` table in SQLite. Columns: `version_id (PK)`, `description`, `templates (JSON dict)`, `created_at`, `is_active`, `eval_score`.

**Deploy flow** — requires `admin` JWT scope:

```python
# POST /prompts/{version_id}/deploy
await db.execute(update(PromptVersion).values(is_active=False))  # deactivate all atomically
pv.is_active = True
await db.commit()
# audit log: action="prompt_deployed", actor=user["sub"]
```

**Rollback** — identical to deploy, additionally logs `{"rolled_back_from": current_id}` in audit_log detail.

**Diff endpoint** — `GET /prompts/diff/{version_a}/{version_b}`:

```python
for key in all_keys:
    unified = "\n".join(difflib.unified_diff(
        a_text.splitlines(), b_text.splitlines(),
        fromfile=f"{version_a}/{key}", tofile=f"{version_b}/{key}",
    ))
    diffs[key] = {"a": a_text, "b": b_text, "unified_diff": unified}
```

Uses Python's `difflib.unified_diff` — standard unified diff format per template key.

**Filesystem fallback** (`domain/prompts/loader.py`): `PromptLoader.get()` tries in order:
1. `templates/{version}/{key}_{lang}.txt`
2. `templates/{version}/{key}.txt`
3. `templates/v1/{key}_{lang}.txt`
4. `templates/v1/{key}.txt`

Results cached in `_cache: dict[str, str]` keyed by `"{version}:{key}:{language}"`.

### The 15-Scenario Regression Suite (`eval/scenarios.py`)

Structured as `SCENARIOS: list[dict]` with fields: `id`, `name`, `language`, `transcript` (list of speaker/text dicts), `expected`, `acceptable_alternatives` (optional), `expected_partial` (optional).

| ID | Category | Key Challenge |
|---|---|---|
| H1 | Hindi | Clean complete FNOL — all fields present |
| H2 | Hindi | Hinglish numbers/dates ("P-two-four-five-six-seven", "Three April") |
| H3 | Hindi | Confused caller, hesitation, eventual policy number |
| H4 | Hindi | Multi-vehicle accident, injuries present |
| H5 | Hindi | Distressed caller, incomplete info |
| E1 | English | Clean complete FNOL |
| E2 | English | Ambiguous date format (15/3) |
| E3 | English | Third party + legal complication |
| E4 | English | Non-vehicle claim (home theft) |
| E5 | English | Caller self-corrects policy number and date mid-call |
| X1 | Edge | Language switch Hindi→English mid-call |
| X2 | Edge | Wrong policy number corrected |
| X3 | Edge | Vague location requiring agent follow-up |
| X4 | Edge | Caller aborts — `expected_partial=True` |
| X5 | Edge | STT errors simulated (garbled speech: "nine eight seven six") |

**Scoring** (`eval/runner.py:33`):
- Exact match (case-insensitive) = 1.0
- Acceptable alternative match = 1.0
- Partial string containment = 0.8
- Miss = 0.0

Scenario passes if `overall_accuracy >= 0.8`. All 15 run concurrently via `asyncio.gather(*tasks)`.

---

## 7. DESIGN DECISIONS

### Decision 1: FSM vs LLM-Native Conversation Management

**Chose:** Explicit 7-state FSM (`domain/fsm.py`)

**Alternatives considered:** Single prompt with full task list; multi-agent with planner LLM; ReAct-style tool calls

**Why:** A phone call for insurance claim capture has a deterministic sequence with clear gate conditions. There is no branching that requires LLM reasoning — you always need policy number, incident details, contact info, in that order. The FSM makes loop exit conditions testable in Python without any LLM inference. The system prompt also switches per state, making each LLM call a focused single-task prompt.

**Tradeoff:** Rigidity. If a caller volunteers their callback number at turn 1, `CONTACT_VERIFY` still activates its dedicated prompt (though the exit condition may pass immediately if the FNOL record already has the field). A smarter router could detect already-present fields and skip states dynamically.

---

### Decision 2: `asyncio.gather` for TTS Batching

**Chose:** Fire all sentences simultaneously; reconstruct order by index

**Alternative:** Serial synthesis; streaming TTS with sentence-by-sentence playback as LLM generates

**Why:** For a 3-sentence response (typical in this domain), parallel reduces TTS wall-clock latency from ~600ms to ~200ms (assuming 200ms per sentence). Implementation is simple — each `synthesize_one` is pure async I/O, asyncio handles concurrency without threads.

**Tradeoff:** All N TTS calls hit Sarvam simultaneously — bursty traffic under high call volume. Also, the caller hears nothing until all chunks arrive: if sentence 1 takes 800ms and 2–3 finish in 200ms, playback still waits 800ms. Streaming TTS (play sentence 1 while 2 synthesises) would reduce perceived latency further but requires a more complex async pipeline with queues.

---

### Decision 3: Circuit Breaker — 3 States, Time-Based Recovery, No Half-Open

**Chose:** HEALTHY → COOLING_DOWN → DISABLED with 60s time-based recovery

**Alternative:** Classic 4-state (closed/open/half-open with single probe); exponential backoff; Hystrix-style

**Why:** Simplicity and predictability. Time-based recovery means operators know exactly when to expect recovery. The half-open pattern adds a race condition (what if the probe itself is slow or hits partial outage?).

**Tradeoff:** The DISABLED state has no self-recovery. 3 cooldown cycles = 9 consecutive failures over ~3 minutes permanently disables the provider until process restart. There is no `POST /admin/reset-circuit-breaker` endpoint. In production, a 10-minute Groq outage would permanently disable the primary LLM.

---

### Decision 4: Prometheus Instrumentation Granularity

**Chose:** Per-stage histograms (STT, LLM total, LLM TTFT, TTS, total pipeline) with provider+language labels

**Alternative:** Single end-to-end latency only; application-level log parsing

**Why:** When latency spikes, you need to know which stage is responsible. `vaani_stt_latency_ms` vs `vaani_llm_latency_ms` tells you immediately whether the bottleneck is at Sarvam or Groq. The language label on STT matters because Hindi and English models may perform differently. LLM_TTFT is tracked separately — in a streaming TTS architecture, TTFT (not full LLM latency) determines when audio can start playing.

**Tradeoff:** Label cardinality. `STT_LATENCY` has 3 label dimensions: 2 providers × 2 languages × 3 channels = 12 time series per histogram bucket boundary. Manageable now, but adding more label dimensions could stress Prometheus memory.

---

## 8. FAILURE MODES

### ASR Transcription Errors

**What can go wrong:** Sarvam Saarika returns garbled text, empty string, wrong language code, or times out.

**How the code handles it:**
- Empty transcript → `transcript = ""` flows into LLM which generates a reprompt ("I didn't catch that")
- Wrong language code → `LanguageTracker` uses `infer_language_from_text()` (Devanagari character ratio) as fallback if STT returns an unrecognised code (`language.py:27`)
- API exception → `circuit_breaker.record_failure()` increments; if CB opens, next call immediately raises `RuntimeError("sarvam_stt circuit breaker is open")`; the handler catches this in its outer `try/except` (`twilio_handler.py:159`) and continues without processing that audio chunk

**What would happen if unhandled:** Every failed turn propagates an exception to the channel handler, closing the WebSocket and dropping the call with no FNOL data saved.

---

### LLM JSON Parse Failures

**What can go wrong:** Groq returns markdown-wrapped JSON, partial JSON, or plain text explanatory prose.

**How the code handles it:**
- `_parse_json()` strips markdown code fences, then calls `json.loads()`; returns `None` on `JSONDecodeError`
- First attempt fails → retry with `"RESPOND ONLY WITH JSON. NO EXPLANATIONS."` appended (`extractor.py:179`)
- Second attempt also fails → return `dict(EMPTY_FNOL)` — all fields `None`, `completeness_score: 0.0`

**Consequence:** FSM exit conditions never fire (no truthy `policy_number`), so the call hits `max_reprompts` on each state and advances via fallback. Call completes but FNOL record is empty. Webhook only fires at completeness ≥ 0.9, so no corrupt data escapes downstream.

---

### TTS Service Downtime

**What can go wrong:** Sarvam Bulbul returns 5xx, times out, or base64 decode fails.

**How the code handles it** (`tts.py:93–108`):
- `asyncio.gather(*tasks, return_exceptions=True)` — exceptions returned as values, not raised
- Each exception: `circuit_breaker.record_failure()`, replace that chunk with `generate_silence_wav(500)`
- If ALL sentences fail: `update_provider_health("sarvam","tts", cb_state)` reflects the degradation
- Browser clients still receive `{"type": "agent_text"}` with the response text
- Call continues — caller hears 500ms silence per failed sentence instead of synthesised speech

**What would happen if unhandled:** A single TTS exception would propagate out of `synthesize_parallel`, crash `run_turn`, and close the WebSocket mid-call.

---

### WebSocket Disconnection Mid-Call

**What can go wrong:** Caller's browser closes, network drops, or Twilio stream terminates unexpectedly.

**How the code handles it:**
- `WebSocketDisconnect` is caught explicitly in both handlers
- `finally` block always runs: `ACTIVE_CALLS.dec()`, `CALLS_TOTAL.inc(outcome="abandoned")`, `store.finalize_call(call_id, "abandoned")`, `live_manager.broadcast({"type":"call_ended",...})`
- `fnol_data` up to that point is persisted via `store.upsert_fnol(call_id, fnol_data)`

**What would happen if unhandled:** Active call gauge would never decrement; the call record would remain unfinished in the DB; each unfinished record occupies storage and skews metrics.

---

### FSM Receiving Unexpected Input

**What can go wrong:** Unknown `msg_type` from browser, malformed JSON, or very long audio chunks.

**How the code handles it:**
- Unknown `msg_type` → `elif` chain doesn't match → loop continues to `await ws.receive_json()`. No error sent, no state change.
- `AudioBuffer.MAX_MS = 10000` caps buffer size — no single chunk ever exceeds 10 seconds
- `ws.receive_json()` failure (malformed JSON) → raises, caught by outer `except Exception`, sends `{"type":"error","code":"PIPELINE_ERROR"}` and exits loop cleanly
- `advance()` called on terminal state → immediately returns `None`, no side effects

---

## 9. WHAT I'D DO DIFFERENTLY

### 1. STT Client Is Synchronous Inside an Async Event Loop

**The problem:** `SarvamSTT.transcribe()` (`stt.py:51`) calls `self.client.speech_to_text.transcribe(...)` using the synchronous `SarvamAI` client, not `AsyncSarvamAI`. Running a blocking HTTP call inside `async def` blocks the entire asyncio event loop for the duration of the STT request (~200–500ms). During that time, no other coroutine — including other concurrent calls — can make progress.

The TTS code already does this correctly (`tts.py:83`): `await self.async_client.text_to_speech.convert(...)`.

**Production fix:** Replace `self.client` with `self.async_client` in `transcribe()` and `await` the call. This is a one-line change but has significant impact under any concurrent load.

---

### 2. `PromptLoader` Cache Never Invalidates After Deploy

**The problem:** `_loader` is a module-level singleton (`domain/prompts/loader.py:65`) with an in-memory `_cache` dict. After `POST /prompts/{id}/deploy` changes the active version in the database, the `_cache` in each running process still holds the old templates. The `invalidate_cache()` method (`loader.py:61`) exists but is never called from the deploy endpoint. In multi-process deployments, the cache diverges across workers indefinitely.

`settings.ACTIVE_PROMPT_VERSION` is also read at startup from `.env` and never updated at runtime — so even if the cache were cleared, the version string used as a cache key is stale.

**Production fix:** Call `_loader.invalidate_cache()` inside the deploy endpoint handler, and re-read the active version from the database per request rather than from `settings`.

---

### 3. Circuit Breaker DISABLED State Has No Self-Recovery

**The problem:** After 3 cooldown cycles (9 consecutive failures over ~3 minutes), `state = DISABLED` and `is_available()` returns `False` forever. There is no timer, no probe, no admin reset API. Process restart is the only recovery. A 10-minute Groq outage permanently disables the primary LLM for the process lifetime.

**Production fix:** Add a half-open probe. After a configurable duration in DISABLED (e.g., 10 minutes), allow a single test call. If it succeeds, return to HEALTHY. Alternatively expose `POST /admin/circuit-breaker/{provider}/reset` behind admin scope for manual recovery without restart.

---

### 4. In-Process Session Dicts Block Horizontal Scaling

**The problem:** `_active_calls: dict[str, dict]` (`twilio_handler.py:29`) and `_sessions: dict[str, dict]` (`whatsapp_handler.py:19`) are process-local. With multiple gunicorn workers or Kubernetes pods, a Twilio `POST /voice/incoming` could land on worker A while the subsequent `WS /voice/stream` lands on worker B, finding no matching session. WhatsApp sessions have the same problem.

**Production fix:** Store active session state in Redis with a TTL. FSM state, `fnol_data`, and buffer metadata would be serialised per turn. Raw PCM bytes in `AudioBuffer` are harder — requires sticky WebSocket routing (all WebSocket frames for a call hit the same pod) or a dedicated streaming server.

---

### 5. No Real-Time Streaming TTS — Caller Waits for Full LLM Response

**The problem:** `GroqLLM.complete()` uses streaming (`stream=True`) to measure TTFT, then collects all chunks into `text = "".join(chunks)` and returns the full string. `PipelineOrchestrator` only calls TTS after the full LLM response is available. Total caller silence = STT (~250ms) + LLM full response (~800ms) + TTS wall-clock (~200ms) = **~1,250ms**. The measured TTFT (~100–200ms) is logged and Prometheused but never acted on.

**Production fix:** As the LLM streams, detect sentence boundaries (punctuation). Fire TTS for sentence 1 immediately upon detecting the first sentence-ending token. Stream sentence 1 audio to the caller while the LLM is still generating sentence 2. This requires restructuring `run_turn` into a streaming pipeline using `asyncio.Queue` between LLM output and TTS input, and a separate send task consuming audio as it arrives.

---

## 10. LIKELY INTERVIEW QUESTIONS WITH ANSWERS

### Q1: Walk me through exactly what happens between when a caller speaks and when they hear a response.

1. Twilio captures audio and sends 20ms µ-law chunks over the Media Streams WebSocket to `/voice/stream`
2. `twilio_handler.py` decodes each base64 payload → `audioop.ulaw2lin` (µ-law to 16-bit PCM) → `audioop.ratecv` (8kHz to 16kHz upsample), stored in `AudioBuffer`
3. `AudioBuffer` flushes at `MAX_MS=10000ms` (time-based); browser channel also VAD-gates at `FLUSH_MS=300ms`
4. `PipelineOrchestrator.run_turn(audio_wav=...)` is called
5. `SarvamSTT.transcribe()` sends the WAV to `saarika:v2.5`, gets back a transcript
6. `_build_messages()` assembles `[system_prompt, ...conversation_history, user_transcript]`
7. `GroqLLM.complete()` opens a streaming completion to `llama-3.3-70b-versatile`, collecting chunks, measuring TTFT
8. `split_into_sentences()` splits the response on `[।.!?]+`
9. `asyncio.gather` fires one `async_client.text_to_speech.convert()` per sentence simultaneously
10. Audio chunks arrive back ordered by index; failed ones replaced with silence
11. Each WAV chunk: strip header → ratecv(16k→8k) → `audioop.lin2ulaw` → base64 → `send_json(event:"media")` back to Twilio
12. Twilio plays µ-law audio to the caller

In parallel: `FNOLExtractor.extract()` runs a separate LLM call, `ConversationFSM.advance()` checks exit conditions, `live_manager.broadcast()` pushes transcript/metrics/FSM state to the dashboard.

---

### Q2: Why did you use a separate LLM call for FNOL extraction rather than having the conversation LLM return structured JSON directly?

The conversation LLM's output must be fluent speech that Sarvam TTS can synthesise. If it returned JSON, the TTS pipeline breaks — you can't speak `{"policy_number": "SBI-2024-789456"}` naturally.

Extraction is a different task: reading a completed transcript and pulling out structured fields. Separating them gives each LLM call a single, focused responsibility. The extractor uses a dedicated `EXTRACTOR_SYSTEM_PROMPT` with field definitions, confidence scoring, and Hindi/Hinglish handling — none of which belongs in a real-time conversation prompt.

The extraction call also runs after the turn completes, so in principle it does not add to caller-facing latency. (Though in the current implementation it IS awaited before audio is sent — see Q15.)

---

### Q3: Your circuit breaker doesn't have a half-open state. Why not, and what's the risk?

I chose time-based recovery (60s in COOLING_DOWN → spontaneous return to HEALTHY) for simplicity. The reasoning: a 60-second window is long enough for transient API issues to resolve, and the first real call after cooldown acts as a natural probe.

The risk: if the provider is still unstable after 60s, the probe fails, `record_failure()` increments again, and the CB enters another cooldown cycle. After 3 such cycles it hits DISABLED with no self-recovery path short of a process restart.

In production I'd add half-open: after cooldown, allow exactly one probe. If it succeeds, reset to HEALTHY cleanly. If it fails, reset the cooldown timer and stay open. This prevents the cascade of failed-probe → new-cooldown-cycle → DISABLED.

---

### Q4: Why not use Groq's JSON mode instead of plain-text instruction for FNOL extraction?

Groq's JSON mode (`response_format={"type": "json_object"}`) guarantees valid JSON output, which would eliminate the two-attempt parse retry entirely.

I didn't use it because: (1) JSON mode only guarantees *valid JSON*, not that the schema matches — field names and types could still be wrong; (2) `LLMRouter` also routes to Gemini, which has a different JSON mode API — unifying both would require provider-specific logic in the extraction call; (3) the current approach — parse → validate → clean — handles schema mismatches anyway.

For production, I'd use Groq JSON mode for the Groq path and Gemini's `response_mime_type="application/json"` for fallback. Or use function calling with a typed Pydantic schema, which gives field-level type guarantees at the API layer.

---

### Q5: The FSM has 5 states where `fallback == next`. Why advance even if the required field wasn't collected?

Blocking on a missing field creates a worse experience than advancing with partial data. If a caller can't recall their policy number after 3 prompts, a 4th prompt won't help — the call becomes frustrating and the caller hangs up with zero data.

By advancing with `fallback == next`, we continue collecting whatever the caller *can* provide (incident details, callback number). After the call, a partial record with a callback number lets a human agent follow up for the missing fields.

The exception is GREETING with `fallback = ERROR` — if a caller says nothing after 2 prompts, there's no conversation to continue and the call should terminate cleanly.

---

### Q6: How does `LanguageTracker` handle a call that starts in Hindi and switches to English mid-call (scenario X1)?

`LanguageTracker.update()` (`language.py:51`) takes the STT-detected language code and the transcript text. On each call:
1. If STT returns `"hi-IN"` or `"en-IN"`, use that
2. Otherwise run `infer_language_from_text()` — counts Devanagari characters; if >10% of alphabetic characters are Devanagari, classify as `"hi-IN"`
3. After `LANGUAGE_DETECTION_TURNS=1` successful detection, set `_locked = True` and return the locked language forever

For scenario X1, the first user turn (`"Mera policy number hai..."`) is detected as `"hi-IN"` by STT or the heuristic, and the language locks to `"hi-IN"` after turn 1. When the caller switches to English in turn 2, the language stays `"hi-IN"` — the system prompt and TTS speaker remain Hindi.

This is a known limitation. A production fix would detect language drift over a rolling window and allow re-locking, rather than locking on the first turn.

---

### Q7: Your system makes two LLM calls per turn. Under load, what's the total LLM API budget?

Per turn:
- **Conversation call:** ~200–512 tokens input + ~100 tokens output ≈ 600 tokens
- **Extraction call:** Grows with transcript length — ~800 tokens on turn 1, ~1500 tokens by turn 8 (extractor system prompt is ~400 tokens; transcript grows ~100 tokens per turn)

For a typical 8-turn call: ~4,800 tokens conversation + ~9,200 tokens extraction ≈ **14,000 tokens per call**.

At Groq pricing (~$0.59/M input tokens for Llama 3.3 70B), that's < $0.01 per call. The more important concern is latency: extraction IS awaited before audio is sent (`websocket_handler.py:223` before line 244), so it adds to caller-perceived turn latency. It should be a background task.

---

### Q8: The `live_manager.broadcast()` calls happen sequentially per turn. What happens under 50 concurrent calls?

`live_manager.broadcast()` iterates `self.connections` and calls `await ws.send_json(message)` for each dashboard client. With 50 active calls each finishing a turn simultaneously, you'd have 50 concurrent `_process_voice_turn` coroutines each calling `broadcast()` multiple times. Since asyncio is single-threaded, these interleave on the event loop rather than truly paralleling.

With 10 dashboard clients connected and 5 broadcasts per turn, that's 500 `send_json` calls per turn cycle across 50 concurrent calls — measurable event loop pressure.

Production fix: fire broadcasts as `asyncio.create_task(live_manager.broadcast(...))` so they don't block the call handler's main path. The caller should not have to wait for dashboard clients to receive metrics.

---

### Q9: Why does `SileroVAD` only gate the browser channel and not the Twilio channel?

`SileroVAD` is instantiated only in the browser WebSocket handler (`websocket_handler.py:75`). The Twilio handler (`twilio_handler.py:130–132`) uses `AudioBuffer.add_twilio_chunk()` and checks only `if flushed:` — there is no VAD call.

For the Twilio channel, flushing is purely time-based (`MAX_MS=10000`). This means a phone caller speaks for up to 10 seconds before the pipeline runs — very poor UX. The browser channel benefits from VAD-gated 300ms flush windows.

This appears to be an implementation gap. The Twilio handler should also instantiate `SileroVAD` and apply the same gating. The likely reason it was omitted: loading Silero requires torch and has startup overhead/memory cost. The design should pre-load the model at startup via the lifespan event, shared across both handlers.

---

### Q10: How would you add streaming TTS to reduce caller-perceived latency?

Current flow: full LLM response → sentence split → parallel TTS → all chunks → send. Total silence ≈ 1,250ms.

To stream:
1. Modify `GroqLLM.complete()` to be an async generator that yields tokens (it already iterates chunks via `stream=True`)
2. Detect sentence boundaries as tokens arrive (punctuation: `।`, `.`, `!`, `?`)
3. When a complete sentence is detected, immediately fire `asyncio.create_task(synthesize_one(sentence))` for that sentence
4. Stream audio chunks to the caller as each TTS task completes via `asyncio.Queue` consumed by a send coroutine
5. Continue LLM generation concurrently

```
STT    [====]
LLM         [===sent1===|==sent2==|=sent3=]
TTS               [=s1=]    [=s2=]    [=s3=]
Audio         sent↑     sent↑    sent↑
```

The caller hears sentence 1 approximately at TTFT + TTS_sentence_1 ≈ 200ms + 150ms = 350ms instead of 1,250ms.

---

### Q11: Why not store FSM state in the database rather than in-process?

In-process is faster (no serialisation overhead, no DB round-trip) and simpler. Each WebSocket connection has exactly one handler coroutine that owns the FSM, so there's no concurrency concern within a single call.

The cost is horizontal scalability: if the WebSocket drops and reconnects to a different process, the FSM state is lost. But for a voice call — a continuous WebSocket session — the FSM lives exactly as long as the connection. If the connection drops, the call is abandoned regardless. In-process storage is the right trade-off here.

It would become a problem for resumable calls (caller hangs up and dials back to continue). That would require persisting FSM state — current state, reprompt_count, history — to the database per turn, and routing callbacks to the same session by phone number.

---

### Q12: The `DETAILS_CAPTURE` state has `max_reprompts=5` while `CONTACT_VERIFY` has `max_reprompts=2`. Why the difference?

`DETAILS_CAPTURE` exits at `completeness_score >= 0.8`, which requires multiple fields: incident location, injury details, damage description, third-party info. A caller providing all of these in one turn is unlikely — it naturally takes several exchanges. Five reprompts allows 5 additional turns for the LLM to elicit remaining fields.

`CONTACT_VERIFY` just needs a callback number — a single piece of information. If the caller hasn't provided it after 2 prompts, they probably won't. More prompts make the call feel repetitive.

`GREETING` uses `max_reprompts=2` with `fallback=ERROR` — if a caller says nothing after two greetings, it's likely a wrong number or abandoned call.

---

### Q13: Why not use Sarvam's own LLM instead of Groq for the conversation turns?

This is the first thing I'd evaluate for production. The codebase uses Groq (Llama 3.3 70B) + Gemini as general-purpose LLMs. Sarvam has their own models optimised for Indian languages.

For a Hindi-primary FNOL agent, a Sarvam LLM would likely handle code-switching, Hinglish, and Indian proper nouns better than a Western-trained general-purpose model. It would also eliminate the third-party LLM dependency, reducing latency (same infrastructure as STT/TTS) and operational complexity.

The probable reason it wasn't done here: the `sarvamai` SDK wraps their STT/TTS APIs cleanly, but the LLM API availability/stability at implementation time was unclear. In production for Sarvam, using their full stack is the obvious path — and one of the things I'd want to discuss in this interview.

---

### Q14: How does the eval runner handle a field that's correct but in a different format (e.g., "March 15" vs "2024-03-15")?

`score_scenario()` (`eval/runner.py:33`) checks in order:
1. Exact match (case-insensitive) — "March 15" ≠ "2024-03-15", fails
2. Acceptable alternatives — the scenario defines `"acceptable_alternatives": {"incident_date": ["March 15","15 March","15-03-2024"]}`. If extracted value matches any (case-insensitive), score = 1.0
3. Partial containment — if expected is a substring of extracted (or vice versa), score = 0.8
4. Miss — 0.0

The `acceptable_alternatives` dict explicitly handles date format variability, policy number formats, and location spelling variations. Each scenario defines its own acceptable alternatives for ambiguous fields.

---

### Q15: You said extraction runs after the turn completes — but does it actually block audio delivery to the caller?

Yes, and this is a bug. Looking at `_process_voice_turn` (`websocket_handler.py:199`):

```python
# line 223:
fnol_data.update(await extractor.extract(fsm.history, call_id))

# ...DB writes...

# line 244 (audio sent AFTER extraction):
for chunk in result.audio_chunks:
    await ws.send_json({"type": "agent_audio", ...})
```

`extractor.extract()` is awaited on line 223, before the audio chunks are sent on line 244. This means the extraction LLM call (~400–800ms) blocks audio delivery to the browser caller.

The fix: send audio chunks first, then run extraction as a background task:

```python
# Send audio immediately
for chunk in result.audio_chunks:
    await ws.send_json({"type": "agent_audio", ...})

# Run extraction in background
asyncio.create_task(extractor.extract(fsm.history, call_id))
```

The FNOL update and FSM advance can be deferred to complete after the caller already hears the response. For the Twilio handler, this is not an issue since extraction runs after `send_audio_to_twilio` (`twilio_handler.py:154` sends audio, `150` runs `extractor.extract` in the same sequential block — same problem exists there too).
