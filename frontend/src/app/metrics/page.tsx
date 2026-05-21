"use client";

import useSWR from "swr";
import { swrFetcher } from "@/lib/api";
import { formatDuration } from "@/lib/utils";
import type { DiagnosticsData } from "@/lib/types";
import { Activity, Clock, CheckCircle, AlertTriangle } from "lucide-react";
import { KPICard } from "@/components/metrics/KPICard";
import { LatencyChart } from "@/components/metrics/LatencyChart";
import { ProviderHealthCard } from "@/components/metrics/ProviderHealthCard";

function RefreshIndicator({ refreshesIn }: { refreshesIn: number }) {
  return (
    <div className="flex items-center gap-2">
      <div
        className="w-1.5 h-1.5 rounded-full animate-pulse-dot"
        style={{ background: "#00D4C8" }}
      />
      <span className="text-[10px] font-mono" style={{ color: "#4A5568" }}>
        Auto-refresh 10s
      </span>
    </div>
  );
}

// Radial arc for percentage KPIs
function RadialScore({ value, max = 100, color }: { value: number; max?: number; color: string }) {
  const pct = Math.min(value / max, 1);
  const R = 36;
  const circumference = 2 * Math.PI * R;
  const dash = pct * circumference;

  return (
    <svg width="100" height="100">
      <circle cx="50" cy="50" r={R} fill="none" stroke="rgba(255,255,255,0.06)" strokeWidth="6" />
      <circle
        cx="50" cy="50" r={R}
        fill="none"
        stroke={color}
        strokeWidth="6"
        strokeLinecap="round"
        strokeDasharray={`${dash} ${circumference}`}
        transform="rotate(-90 50 50)"
        style={{ filter: `drop-shadow(0 0 6px ${color}80)`, transition: "stroke-dasharray 0.8s ease" }}
      />
      <text x="50" y="54" textAnchor="middle" fontSize="14" fontFamily="JetBrains Mono" fontWeight="700" fill={color}>
        {Math.round(value)}%
      </text>
    </svg>
  );
}

export default function MetricsPage() {
  const { data, isLoading } = useSWR("/diagnostics", swrFetcher, { refreshInterval: 10000 });
  const typedData = data as DiagnosticsData | undefined;
  const pipelineProviders = typedData?.pipeline
    ? {
        [`STT · ${typedData.pipeline.stt.provider}`]: {
          status: typedData.pipeline.stt.status,
          consecutive_errors: typedData.pipeline.stt.consecutive_errors ?? 0,
        },
        [`LLM · ${typedData.pipeline.llm.provider}`]: {
          status: typedData.pipeline.llm.status,
          consecutive_errors: typedData.pipeline.llm.consecutive_errors ?? 0,
        },
        [`TTS · ${typedData.pipeline.tts.provider}`]: {
          status: typedData.pipeline.tts.status,
          consecutive_errors: typedData.pipeline.tts.consecutive_errors ?? 0,
        },
      }
    : typedData?.providers ?? {};

  const completionPct  = Math.round((typedData?.fnol_completion_rate_1h ?? 0) * 100);
  const fallbackPct    = Math.round((typedData?.fallback_rate_1h ?? 0) * 100);
  const completionOK   = completionPct >= 80;
  const fallbackBad    = fallbackPct >= 10;

  return (
    <div
      className="flex flex-col gap-6 p-6 overflow-y-auto"
      style={{ background: "#080B0F", minHeight: "100vh" }}
    >
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1
            className="font-bold text-xl tracking-wide"
            style={{ color: "#F0F4F8", fontFamily: "Inter, sans-serif" }}
          >
            Metrics
          </h1>
          <p className="text-xs font-mono mt-0.5" style={{ color: "#4A5568" }}>
            System diagnostics — auto-refreshes every 10s
          </p>
        </div>
        <RefreshIndicator refreshesIn={10} />
      </div>

      {isLoading ? (
        /* Skeleton cards */
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          {[...Array(4)].map((_, i) => (
            <div
              key={i}
              className="rounded-xl p-5 h-32"
              style={{
                background: "linear-gradient(90deg, rgba(255,255,255,0.04) 25%, rgba(255,255,255,0.07) 50%, rgba(255,255,255,0.04) 75%)",
                backgroundSize: "400% 100%",
                animation: "shimmer 1.6s ease-in-out infinite",
                animationDelay: `${i * 0.1}s`,
                border: "1px solid rgba(255,255,255,0.06)",
              }}
            />
          ))}
        </div>
      ) : !data ? (
        <div
          className="rounded-xl p-10 text-center"
          style={{ background: "rgba(12,16,23,0.7)", border: "1px solid rgba(255,255,255,0.07)" }}
        >
          <div className="text-2xl mb-3">⚠️</div>
          <p className="text-sm font-mono" style={{ color: "#FF4545" }}>
            Unable to reach backend
          </p>
          <p className="text-xs font-mono mt-1" style={{ color: "#2D3748" }}>
            Is the Vaani backend running?
          </p>
        </div>
      ) : (
        <>
          {/* ── KPI Row ─────────────────────────────────────────────────── */}
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
            <KPICard
              label="Active Calls"
              value={typedData?.active_calls ?? 0}
              color="#00D4C8"
              icon={<Activity size={14} />}
            />
            <KPICard
              label="Calls Last 1h"
              value={typedData?.calls_last_1h ?? 0}
              color="#4C9EFF"
              icon={<Clock size={14} />}
            />
            <KPICard
              label="FNOL Completion"
              value={`${completionPct}%`}
              color={completionOK ? "#00E676" : "#F5A623"}
              icon={<CheckCircle size={14} />}
            />
            <KPICard
              label="Fallback Rate"
              value={`${fallbackPct}%`}
              color={fallbackBad ? "#FF4545" : "#00E676"}
              icon={<AlertTriangle size={14} />}
            />
          </div>

          {/* ── Charts Row ───────────────────────────────────────────────── */}
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
            {/* Latency chart takes 2/3 */}
            <div className="lg:col-span-2">
              <LatencyChart />
            </div>

            {/* Radial scores */}
            <div
              className="rounded-xl p-5 flex flex-col gap-4"
              style={{ background: "rgba(12,16,23,0.7)", border: "1px solid rgba(255,255,255,0.07)" }}
            >
              <div className="text-sm font-medium" style={{ color: "#C8D4E0" }}>
                Quality Scores
              </div>

              <div className="flex justify-around items-center flex-1">
                <div className="flex flex-col items-center gap-2">
                  <RadialScore value={completionPct} color={completionOK ? "#00E676" : "#F5A623"} />
                  <span className="text-[9px] font-mono uppercase tracking-wider" style={{ color: "#4A5568" }}>
                    Completion
                  </span>
                </div>
                <div className="flex flex-col items-center gap-2">
                  <RadialScore value={100 - fallbackPct} color={!fallbackBad ? "#00E676" : "#FF4545"} />
                  <span className="text-[9px] font-mono uppercase tracking-wider" style={{ color: "#4A5568" }}>
                    Reliability
                  </span>
                </div>
              </div>

              {/* Aggregate stats */}
              <div className="space-y-2 pt-2" style={{ borderTop: "1px solid rgba(255,255,255,0.05)" }}>
                {[
                  { label: "Calls Last 24h",    value: String(typedData?.calls_last_24h ?? 0) },
                  { label: "Avg Call Duration", value: formatDuration(typedData?.avg_call_duration_1h ?? 0) },
                  { label: "Last Updated",      value: typedData ? new Date(typedData.timestamp).toLocaleTimeString() : "—" },
                ].map(({ label, value }) => (
                  <div key={label} className="flex items-center justify-between">
                    <span className="text-[10px] font-mono" style={{ color: "#4A5568" }}>{label}</span>
                    <span className="text-[11px] font-mono" style={{ color: "#8B9BB4" }}>{value}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>

          {/* ── Provider Health + Grafana ─────────────────────────────────── */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            <ProviderHealthCard providers={pipelineProviders} />

            {/* Grafana links */}
            <div
              className="rounded-xl p-5"
              style={{ background: "rgba(12,16,23,0.7)", border: "1px solid rgba(255,255,255,0.07)" }}
            >
              <div className="text-sm font-medium mb-1" style={{ color: "#C8D4E0" }}>
                Grafana Dashboards
              </div>
              <div className="text-[10px] font-mono mb-4" style={{ color: "#4A5568" }}>
                External observability links
              </div>

              <div className="space-y-2.5">
                {[
                  { label: "Pipeline Health", uid: "vaani-pipeline", icon: "📊", desc: "STT / LLM / TTS latency" },
                  { label: "Call Analytics",  uid: "vaani-calls",    icon: "📞", desc: "Volume, outcomes, languages" },
                  { label: "FNOL Accuracy",   uid: "vaani-fnol",     icon: "📋", desc: "Extraction field scores" },
                ].map(({ label, uid, icon, desc }) => (
                  <a
                    key={uid}
                    href={`http://localhost:3001/d/${uid}`}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="flex items-center gap-3 px-4 py-3 rounded-lg transition-all duration-200 group"
                    style={{
                      background: "rgba(255,255,255,0.03)",
                      border: "1px solid rgba(255,255,255,0.06)",
                    }}
                    onMouseEnter={(e) => {
                      (e.currentTarget as HTMLElement).style.borderColor = "rgba(245,166,35,0.3)";
                      (e.currentTarget as HTMLElement).style.background  = "rgba(245,166,35,0.05)";
                    }}
                    onMouseLeave={(e) => {
                      (e.currentTarget as HTMLElement).style.borderColor = "rgba(255,255,255,0.06)";
                      (e.currentTarget as HTMLElement).style.background  = "rgba(255,255,255,0.03)";
                    }}
                  >
                    <span className="text-xl">{icon}</span>
                    <div className="flex-1 min-w-0">
                      <div className="text-xs font-medium" style={{ color: "#C8D4E0" }}>{label}</div>
                      <div className="text-[10px] font-mono mt-0.5" style={{ color: "#4A5568" }}>{desc}</div>
                    </div>
                    <span className="text-xs" style={{ color: "#4A5568" }}>↗</span>
                  </a>
                ))}
              </div>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
