"""Prometheus metrics for Vaani pipeline — per §12.3."""
from prometheus_client import Counter, Gauge, Histogram

# ── Latency histograms (buckets in milliseconds) ────────────────────────────

STT_LATENCY = Histogram(
    "vaani_stt_latency_ms",
    "STT stage latency in milliseconds",
    ["provider", "language", "channel"],
    buckets=[50, 100, 200, 300, 500, 750, 1000, 1500, 2000, 5000],
)

LLM_LATENCY = Histogram(
    "vaani_llm_latency_ms",
    "LLM stage total latency in milliseconds",
    ["provider", "model"],
    buckets=[100, 200, 500, 750, 1000, 1500, 2000, 3000, 5000, 10000],
)

LLM_TTFT = Histogram(
    "vaani_llm_ttft_ms",
    "LLM time-to-first-token in milliseconds",
    ["provider", "model"],
    buckets=[50, 100, 150, 200, 300, 500, 750, 1000, 2000],
)

TTS_LATENCY = Histogram(
    "vaani_tts_latency_ms",
    "TTS stage latency in milliseconds (parallel batch)",
    ["provider", "language"],
    buckets=[50, 100, 200, 300, 500, 750, 1000, 1500, 2000],
)

PIPELINE_LATENCY = Histogram(
    "vaani_pipeline_total_latency_ms",
    "Total pipeline latency per turn",
    ["channel"],
    buckets=[200, 500, 750, 1000, 1500, 2000, 3000, 5000],
)

FNOL_COMPLETENESS = Histogram(
    "vaani_fnol_completeness_score",
    "FNOL extraction completeness score distribution",
    buckets=[0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0],
)

# ── Counters ────────────────────────────────────────────────────────────────

CALLS_TOTAL = Counter(
    "vaani_calls_total",
    "Total calls by outcome",
    ["channel", "language", "outcome"],
)

PROVIDER_ERRORS = Counter(
    "vaani_provider_errors_total",
    "Provider errors by type",
    ["stage", "provider", "error_type"],
)

FALLBACKS_TRIGGERED = Counter(
    "vaani_fallback_triggered_total",
    "Number of times fallback provider was used",
    ["stage", "from_provider", "to_provider"],
)

CIRCUIT_BREAKER_OPENS = Counter(
    "vaani_circuit_breaker_opens_total",
    "Number of times a circuit breaker opened",
    ["provider"],
)

# ── Gauges ──────────────────────────────────────────────────────────────────

ACTIVE_CALLS = Gauge(
    "vaani_active_calls",
    "Currently active calls",
    ["channel"],
)

PROVIDER_HEALTH = Gauge(
    "vaani_provider_health",
    "Provider health status: 1=healthy, 0.5=cooling_down, 0=disabled",
    ["stage", "provider"],
)


def record_pipeline_turn(
    channel: str,
    language: str,
    stt_ms: float,
    llm_ms: float,
    llm_ttft_ms: float,
    tts_ms: float,
    total_ms: float,
    stt_provider: str = "sarvam",
    llm_provider: str = "groq",
    llm_model: str = "llama-3.3-70b-versatile",
    tts_provider: str = "sarvam",
    fallback_triggered: bool = False,
) -> None:
    """Record all per-turn Prometheus metrics in one call."""
    STT_LATENCY.labels(provider=stt_provider, language=language, channel=channel).observe(stt_ms)
    LLM_LATENCY.labels(provider=llm_provider, model=llm_model).observe(llm_ms)
    LLM_TTFT.labels(provider=llm_provider, model=llm_model).observe(llm_ttft_ms)
    TTS_LATENCY.labels(provider=tts_provider, language=language).observe(tts_ms)
    PIPELINE_LATENCY.labels(channel=channel).observe(total_ms)
    if fallback_triggered:
        FALLBACKS_TRIGGERED.labels(stage="llm", from_provider="groq", to_provider="gemini").inc()


def update_provider_health(provider: str, stage: str, state: str) -> None:
    """Update the health gauge for a provider."""
    value_map = {"healthy": 1.0, "cooling_down": 0.5, "disabled": 0.0}
    PROVIDER_HEALTH.labels(stage=stage, provider=provider).set(value_map.get(state, 0.0))
