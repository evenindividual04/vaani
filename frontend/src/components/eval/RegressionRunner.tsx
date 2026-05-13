"use client";

import type { EvalRun, ScenarioResult } from "@/lib/types";
import { formatDate } from "@/lib/utils";

// ── Scenario Result Card ──────────────────────────────────────────────────────

interface ScenarioResultCardProps {
  scenarioId: string;
  result: ScenarioResult;
}

export function ScenarioResultCard({ scenarioId, result }: ScenarioResultCardProps) {
  const passPct = Math.round(result.overall_accuracy * 100);
  const passColor = result.passed ? "#00E676" : "#FF4545";

  return (
    <div
      className="rounded-xl overflow-hidden animate-fade-in-up"
      style={{
        background: "rgba(12,16,23,0.7)",
        border: `1px solid ${result.passed ? "rgba(0,230,118,0.15)" : "rgba(255,69,69,0.15)"}`,
      }}
    >
      {/* Header */}
      <div
        className="px-4 py-3 flex items-center justify-between"
        style={{
          background: result.passed ? "rgba(0,230,118,0.05)" : "rgba(255,69,69,0.05)",
          borderBottom: `1px solid ${result.passed ? "rgba(0,230,118,0.1)" : "rgba(255,69,69,0.1)"}`,
        }}
      >
        <div className="flex items-center gap-3">
          <div
            className="w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold flex-shrink-0"
            style={{
              background: `${passColor}18`,
              color: passColor,
              border: `1px solid ${passColor}30`,
            }}
          >
            {result.passed ? "✓" : "✗"}
          </div>
          <div>
            <span className="text-xs font-mono font-bold" style={{ color: passColor }}>
              {scenarioId}
            </span>
            <span className="text-xs ml-2" style={{ color: "#8B9BB4" }}>
              {result.name}
            </span>
          </div>
        </div>

        <div className="flex items-center gap-3">
          <div className="text-right">
            <div className="text-sm font-mono font-bold" style={{ color: passColor }}>
              {passPct}%
            </div>
            <div className="text-[9px] font-mono" style={{ color: "#4A5568" }}>accuracy</div>
          </div>
          <div
            className="text-[10px] font-mono px-2.5 py-1 rounded-lg"
            style={{
              background: `${passColor}12`,
              color: passColor,
              border: `1px solid ${passColor}25`,
            }}
          >
            {result.passed ? "PASS" : "FAIL"}
          </div>
        </div>
      </div>

      {/* Field grid */}
      <div className="p-4 grid grid-cols-2 gap-x-6 gap-y-2">
        {result.field_details.map((detail) => {
          const fieldColor = detail.score >= 0.8 ? "#00E676" : "#FF4545";
          return (
            <div key={detail.field} className="flex items-center gap-2 min-w-0">
              <div
                className="w-1 h-4 rounded-full flex-shrink-0"
                style={{ background: fieldColor, boxShadow: `0 0 4px ${fieldColor}60` }}
              />
              <span className="text-[10px] font-mono w-28 flex-shrink-0" style={{ color: "#4A5568" }}>
                {detail.field}
              </span>
              <span
                className="text-[10px] font-mono truncate flex-1"
                style={{ color: detail.extracted != null ? "#8B9BB4" : "#2D3748" }}
                title={String(detail.extracted)}
              >
                {detail.extracted != null && detail.extracted !== undefined
                  ? String(detail.extracted).slice(0, 28)
                  : "—"}
              </span>
              <span
                className="text-[9px] font-mono flex-shrink-0"
                style={{ color: fieldColor }}
              >
                {Math.round(detail.score * 100)}%
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ── Regression Runner ─────────────────────────────────────────────────────────

interface RegressionRunnerProps {
  runs: EvalRun[];
  onTrigger: (versionId: string) => Promise<void>;
  loading?: boolean;
}

function StatusBadge({ status }: { status: string }) {
  const cfg: Record<string, { color: string; bg: string }> = {
    complete: { color: "#00E676", bg: "rgba(0,230,118,0.08)"  },
    running:  { color: "#F5A623", bg: "rgba(245,166,35,0.08)" },
    failed:   { color: "#FF4545", bg: "rgba(255,69,69,0.08)"  },
    queued:   { color: "#8B9BB4", bg: "rgba(255,255,255,0.05)"},
  };
  const { color, bg } = cfg[status] ?? cfg.queued;
  return (
    <div
      className="flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-[10px] font-mono"
      style={{ background: bg, color, border: `1px solid ${color}25` }}
    >
      {status === "running" && (
        <div className="w-1.5 h-1.5 rounded-full animate-pulse-dot" style={{ background: color }} />
      )}
      {status.toUpperCase()}
    </div>
  );
}

export function RegressionRunner({ runs, onTrigger, loading = false }: RegressionRunnerProps) {
  const latest = runs[0];

  return (
    <div className="space-y-4">
      {/* Latest run hero */}
      {latest && (
        <div
          className="rounded-xl p-5"
          style={{ background: "rgba(12,16,23,0.7)", border: "1px solid rgba(255,255,255,0.07)" }}
        >
          <div className="flex items-start justify-between mb-4">
            <div>
              <div className="text-[10px] font-mono uppercase tracking-wider mb-1" style={{ color: "#4A5568" }}>
                Latest Run
              </div>
              <div className="text-sm font-mono" style={{ color: "#8B9BB4" }}>
                {latest.run_id.slice(0, 8)}…
              </div>
              <div className="text-[10px] font-mono mt-0.5" style={{ color: "#4A5568" }}>
                {formatDate(latest.started_at)} · {latest.prompt_version_id}
              </div>
            </div>
            <StatusBadge status={latest.status} />
          </div>

          {/* Accuracy bar */}
          {latest.overall_accuracy != null && (
            <div>
              <div className="flex items-center justify-between mb-2">
                <span className="text-[10px] font-mono uppercase tracking-wider" style={{ color: "#4A5568" }}>
                  Overall Accuracy
                </span>
                <span
                  className="text-xl font-mono font-bold"
                  style={{
                    color: latest.overall_accuracy >= 0.8 ? "#00E676" : "#F5A623",
                    textShadow: `0 0 16px ${latest.overall_accuracy >= 0.8 ? "#00E67660" : "#F5A62360"}`,
                  }}
                >
                  {Math.round((latest.overall_accuracy ?? 0) * 100)}%
                </span>
              </div>
              <div className="h-2 rounded-full overflow-hidden" style={{ background: "rgba(255,255,255,0.05)" }}>
                <div
                  className="h-full rounded-full transition-all duration-1000"
                  style={{
                    width: `${Math.round((latest.overall_accuracy ?? 0) * 100)}%`,
                    background: latest.overall_accuracy >= 0.8
                      ? "linear-gradient(90deg, #00E67680, #00E676)"
                      : "linear-gradient(90deg, #F5A62380, #F5A623)",
                    boxShadow: `0 0 8px ${latest.overall_accuracy >= 0.8 ? "#00E67640" : "#F5A62340"}`,
                  }}
                />
              </div>

              {/* Summary stats */}
              {latest.summary && (
                <div className="grid grid-cols-3 gap-3 mt-4">
                  {[
                    { label: "Total", value: latest.summary.total_scenarios, color: "#8B9BB4" },
                    { label: "Pass",  value: latest.summary.passed,          color: "#00E676" },
                    { label: "Fail",  value: latest.summary.failed,           color: "#FF4545" },
                  ].map(({ label, value, color }) => (
                    <div
                      key={label}
                      className="rounded-lg px-3 py-2 text-center"
                      style={{ background: "rgba(255,255,255,0.03)", border: "1px solid rgba(255,255,255,0.06)" }}
                    >
                      <div className="text-lg font-mono font-bold" style={{ color }}>{value}</div>
                      <div className="text-[9px] font-mono uppercase" style={{ color: "#4A5568" }}>{label}</div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {/* Run history table */}
      {runs.length > 0 && (
        <div
          className="rounded-xl overflow-hidden"
          style={{ background: "rgba(12,16,23,0.7)", border: "1px solid rgba(255,255,255,0.07)" }}
        >
          <div
            className="px-4 py-3 text-[10px] font-mono uppercase tracking-wider"
            style={{ color: "#4A5568", borderBottom: "1px solid rgba(255,255,255,0.05)" }}
          >
            Run History
          </div>
          <table className="w-full border-collapse">
            <thead>
              <tr>
                {["Run ID", "Version", "Status", "Accuracy", "Date"].map((h) => (
                  <th
                    key={h}
                    className="text-left px-4 py-2.5 text-[9px] font-mono uppercase tracking-[0.1em]"
                    style={{ color: "#2D3748", borderBottom: "1px solid rgba(255,255,255,0.04)" }}
                  >
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {runs.map((run) => {
                const accColor = (run.overall_accuracy ?? 0) >= 0.8 ? "#00E676" : "#F5A623";
                return (
                  <tr
                    key={run.run_id}
                    className="transition-colors duration-150"
                    style={{ borderBottom: "1px solid rgba(255,255,255,0.03)" }}
                    onMouseEnter={(e) => (e.currentTarget as HTMLElement).style.background = "rgba(23,31,42,0.6)"}
                    onMouseLeave={(e) => (e.currentTarget as HTMLElement).style.background = "transparent"}
                  >
                    <td className="px-4 py-3 font-mono text-xs" style={{ color: "#8B9BB4" }}>
                      {run.run_id.slice(0, 8)}…
                    </td>
                    <td className="px-4 py-3">
                      <span
                        className="text-[10px] font-mono px-2 py-0.5 rounded"
                        style={{ background: "rgba(245,166,35,0.08)", color: "#F5A623" }}
                      >
                        {run.prompt_version_id}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      <StatusBadge status={run.status} />
                    </td>
                    <td className="px-4 py-3 font-mono text-xs font-bold" style={{ color: accColor }}>
                      {run.overall_accuracy != null
                        ? `${Math.round((run.overall_accuracy ?? 0) * 100)}%`
                        : "—"}
                    </td>
                    <td className="px-4 py-3 text-[10px] font-mono" style={{ color: "#4A5568" }}>
                      {formatDate(run.started_at)}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
