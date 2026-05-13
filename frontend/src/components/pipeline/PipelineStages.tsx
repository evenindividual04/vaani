"use client";

import { formatMs, latencyColor } from "@/lib/utils";

interface Stage {
  label: string;
  ms: number;
  provider: string;
  isFallback?: boolean;
}

interface PipelineStagesProps {
  stt_ms: number;
  llm_ms: number;
  llm_ttft_ms?: number;
  tts_ms: number;
  total_ms: number;
  stt_provider?: string;
  llm_provider?: string;
  tts_provider?: string;
  fallback_triggered?: boolean;
  compact?: boolean;
}

export function PipelineStages({
  stt_ms,
  llm_ms,
  llm_ttft_ms,
  tts_ms,
  total_ms,
  stt_provider = "sarvam",
  llm_provider = "groq",
  tts_provider = "sarvam",
  fallback_triggered = false,
  compact = false,
}: PipelineStagesProps) {
  const stages: Stage[] = [
    { label: "STT", ms: stt_ms, provider: stt_provider },
    { label: "LLM", ms: llm_ms, provider: llm_provider, isFallback: fallback_triggered },
    { label: "TTS", ms: tts_ms, provider: tts_provider },
  ].filter((s) => s.ms > 0);

  const maxMs = Math.max(...stages.map((s) => s.ms), 1);

  if (compact) {
    return (
      <div className="flex items-center gap-3 flex-wrap">
        {stages.map((s) => {
          const c = latencyColor(s.ms);
          return (
            <div key={s.label} className="flex items-center gap-1.5">
              <span className="text-[9px] font-mono" style={{ color: "#4A5568" }}>{s.label}</span>
              <span className="text-xs font-mono font-medium" style={{ color: c }}>
                {formatMs(s.ms)}
              </span>
            </div>
          );
        })}
        <span className="text-[10px]" style={{ color: "#2D3748" }}>▶</span>
        <span className="text-xs font-mono font-bold" style={{ color: latencyColor(total_ms) }}>
          {formatMs(total_ms)}
        </span>
        {fallback_triggered && (
          <span
            className="text-[9px] font-mono px-1.5 py-0.5 rounded"
            style={{ background: "rgba(245,166,35,0.1)", color: "#F5A623", border: "1px solid rgba(245,166,35,0.2)" }}
          >
            FALLBACK
          </span>
        )}
      </div>
    );
  }

  return (
    <div className="space-y-3">
      {stages.map((s, idx) => {
        const color = latencyColor(s.ms);
        const widthPct = (s.ms / maxMs) * 100;
        return (
          <div
            key={s.label}
            className="space-y-1.5 animate-fade-in-up"
            style={{ animationDelay: `${idx * 0.07}s`, opacity: 0 }}
          >
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <span
                  className="text-[9px] font-mono font-bold w-7"
                  style={{ color: "#4A5568" }}
                >
                  {s.label}
                </span>
                <span
                  className="text-[9px] font-mono"
                  style={{ color: "#2D3748" }}
                >
                  {s.provider}
                </span>
                {s.isFallback && (
                  <span
                    className="text-[8px] font-mono px-1 py-0.5 rounded"
                    style={{
                      background: "rgba(245,166,35,0.1)",
                      color: "#F5A623",
                      border: "1px solid rgba(245,166,35,0.2)",
                    }}
                  >
                    FALLBACK
                  </span>
                )}
              </div>
              <div className="flex items-center gap-1.5">
                <span className="text-xs font-mono font-semibold" style={{ color }}>
                  {formatMs(s.ms)}
                </span>
                {s.label === "LLM" && llm_ttft_ms && (
                  <span className="text-[9px] font-mono" style={{ color: "#2D3748" }}>
                    ttft:{formatMs(llm_ttft_ms)}
                  </span>
                )}
              </div>
            </div>

            {/* Animated bar */}
            <div
              className="h-1.5 rounded-full overflow-hidden"
              style={{ background: "rgba(255,255,255,0.05)" }}
            >
              <div
                className="h-full rounded-full"
                style={{
                  width: `${widthPct}%`,
                  background: `linear-gradient(90deg, ${color}80, ${color})`,
                  boxShadow: `0 0 6px ${color}60`,
                  transition: "width 0.6s cubic-bezier(0.4,0,0.2,1)",
                }}
              />
            </div>
          </div>
        );
      })}

      {/* Total */}
      <div
        className="flex items-center justify-between pt-2"
        style={{ borderTop: "1px solid rgba(255,255,255,0.05)" }}
      >
        <span className="text-[9px] font-mono tracking-wider" style={{ color: "#4A5568" }}>
          TOTAL
        </span>
        <span
          className="text-base font-mono font-bold"
          style={{
            color: latencyColor(total_ms),
            textShadow: `0 0 12px ${latencyColor(total_ms)}60`,
          }}
        >
          {formatMs(total_ms)}
        </span>
      </div>
    </div>
  );
}
