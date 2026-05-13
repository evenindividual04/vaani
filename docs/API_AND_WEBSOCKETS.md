# API & WebSockets Protocol

The Vaani platform relies on a hybrid communication model: REST for historical data/configuration, and WebSockets for low-latency, real-time observability.

## 📡 WebSocket Protocol

The WebSocket endpoint is located at `ws://<backend_url>/ws`.
It is primarily used by the frontend dashboard to monitor live calls. The backend broadcasts state updates as they happen.

### Message Format
All WebSocket messages are JSON objects containing a `type` and a `payload`.

#### 1. `call_started`
Fired when a new caller connects to the system.
```json
{
  "type": "call_started",
  "payload": {
    "call_id": "call_abc123",
    "channel": "phone",
    "language": "en",
    "started_at": "2026-05-13T10:00:00Z"
  }
}
```

#### 2. `turn_complete`
Fired after a full conversation turn (User speaks -> System processes -> Agent replies).
```json
{
  "type": "turn_complete",
  "payload": {
    "call_id": "call_abc123",
    "fsm_state": "POLICY_VERIFY",
    "extracted_data": {
      "policy_number": "POL-99812",
      "completeness_score": 0.35
    },
    "metrics": {
      "stt_ms": 120,
      "llm_ms": 450,
      "tts_ms": 200,
      "total_ms": 770
    },
    "new_turns": [
      { "speaker": "user", "text": "My policy number is POL-99812." },
      { "speaker": "agent", "text": "Thank you. I have verified your policy. What kind of incident are you reporting?" }
    ]
  }
}
```

#### 3. `call_ended`
Fired when the call terminates.
```json
{
  "type": "call_ended",
  "payload": {
    "call_id": "call_abc123",
    "outcome": "completed"
  }
}
```

---

## 🔌 REST API

The FastAPI REST API provides configuration, history, and metrics. Base URL: `/api/v1`

### `GET /calls`
Retrieve historical call records with pagination.
- **Query Params**: `page` (int), `limit` (int)
- **Response**: Array of `CallRecord` objects.

### `GET /diagnostics/metrics`
Retrieve system-wide metrics for the dashboard KPI cards.
- **Response**:
```json
{
  "calls_last_24h": 142,
  "completion_rate": 0.88,
  "avg_latency_ms": 850,
  "active_calls": 2
}
```

### `POST /eval/run`
Trigger a batch evaluation of the current LLM prompt using simulated transcripts.
- **Body**: `{ "prompt_version": "v1.2" }`
- **Response**: Detailed test results, passes, fails, and regression metrics.
