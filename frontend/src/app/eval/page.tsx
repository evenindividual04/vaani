"use client";

import { useState } from "react";
import useSWR from "swr";
import { swrFetcher, createEvalRun } from "@/lib/api";
import { RegressionRunner, ScenarioResultCard } from "@/components/eval/RegressionRunner";
import type { EvalRun, ScenarioResult } from "@/lib/types";

export default function EvalPage() {
  const { data: runsData, isLoading, mutate } = useSWR("/eval/runs", swrFetcher, {
    refreshInterval: 5000,
  });
  const { data: promptsData } = useSWR("/prompts", swrFetcher);

  const [selectedRunId, setSelectedRunId] = useState<string | null>(null);
  const [versionId, setVersionId] = useState("v1");
  const [triggering, setTriggering] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const runs: EvalRun[] = (runsData as any) ?? [];
  const versions = (promptsData as any)?.versions ?? [];

  const selectedRun = runs.find((r) => r.run_id === selectedRunId) ?? runs[0];
  const scenarioResults: Record<string, ScenarioResult> = selectedRun?.scenario_results ?? {};

  const handleTrigger = async () => {
    setTriggering(true);
    setError(null);
    try {
      await createEvalRun({ prompt_version_id: versionId, scenario_ids: "all" });
      mutate();
    } catch (e: any) {
      setError(e.message);
    } finally {
      setTriggering(false);
    }
  };

  return (
    <div className="flex flex-col h-screen p-6 gap-6 overflow-y-auto" style={{ background: "#080B0F" }}>
      {/* Header */}
      <div className="flex items-start justify-between flex-shrink-0">
        <div>
          <h1
            className="font-bold text-xl tracking-wide"
            style={{ color: "#F0F4F8", fontFamily: "Inter, sans-serif" }}
          >
            Eval Suite
          </h1>
          <p className="text-xs font-mono mt-0.5" style={{ color: "#4A5568" }}>
            15 scenarios · H1-H5 Hindi · E1-E5 English · X1-X5 Edge cases
          </p>
        </div>

        {/* Trigger panel */}
        <div
          className="flex items-center gap-3 p-2 rounded-xl"
          style={{ background: "rgba(12,16,23,0.7)", border: "1px solid rgba(255,255,255,0.07)" }}
        >
          <select
            value={versionId}
            onChange={(e) => setVersionId(e.target.value)}
            className="input-dark bg-transparent border-0 focus:ring-0"
            style={{ width: 120 }}
          >
            {versions.length > 0
              ? versions.map((v: any) => (
                  <option key={v.version_id} value={v.version_id}>{v.version_id}</option>
                ))
              : <option value="v1">v1</option>}
          </select>
          <button
            onClick={handleTrigger}
            disabled={triggering}
            className="btn-amber font-bold shadow-glow-amber"
            style={{ padding: "8px 16px" }}
          >
            {triggering ? (
              <span className="flex items-center gap-2">
                <span className="w-1.5 h-1.5 rounded-full bg-white animate-pulse" />
                QUEUING
              </span>
            ) : (
              "▶ RUN EVAL"
            )}
          </button>
        </div>
      </div>

      {error && (
        <div
          className="px-4 py-3 rounded-lg text-xs font-mono"
          style={{ background: "rgba(255,69,69,0.1)", color: "#FF4545", border: "1px solid rgba(255,69,69,0.2)" }}
        >
          Error: {error}
        </div>
      )}

      {/* Run selector tabs */}
      {runs.length > 1 && (
        <div className="flex items-center gap-2 flex-wrap">
          <span className="text-[10px] font-mono tracking-wider mr-2" style={{ color: "#4A5568" }}>
            HISTORY
          </span>
          {runs.slice(0, 8).map((r) => {
            const isSelected = selectedRun?.run_id === r.run_id;
            const passPct = Math.round((r.overall_accuracy ?? 0) * 100);
            return (
              <button
                key={r.run_id}
                onClick={() => setSelectedRunId(r.run_id)}
                className="flex items-center gap-2 px-3 py-1.5 rounded-lg text-[10px] font-mono transition-all duration-200"
                style={{
                  background: isSelected ? "rgba(0,212,200,0.1)" : "rgba(255,255,255,0.03)",
                  color: isSelected ? "#00D4C8" : "#8B9BB4",
                  border: `1px solid ${isSelected ? "rgba(0,212,200,0.3)" : "rgba(255,255,255,0.06)"}`,
                }}
              >
                <span>{r.run_id.slice(0, 8)}</span>
                {r.status === "complete" && (
                  <span
                    className="px-1.5 py-0.5 rounded"
                    style={{
                      background: passPct >= 80 ? "rgba(0,230,118,0.15)" : "rgba(245,166,35,0.15)",
                      color: passPct >= 80 ? "#00E676" : "#F5A623",
                    }}
                  >
                    {passPct}%
                  </span>
                )}
                {r.status === "running" && (
                  <span className="w-1.5 h-1.5 rounded-full animate-pulse-dot" style={{ background: "#F5A623" }} />
                )}
              </button>
            );
          })}
        </div>
      )}

      {isLoading ? (
        <div className="flex items-center justify-center h-48 rounded-xl" style={{ border: "1px solid rgba(255,255,255,0.05)" }}>
          <div className="w-2 h-2 rounded-full bg-[#00D4C8] animate-ping-ring" />
        </div>
      ) : (
        <div className="flex flex-col lg:flex-row gap-6 min-h-0">
          <div className="w-full lg:w-1/3 flex-shrink-0">
            <RegressionRunner
              runs={runs}
              onTrigger={async () => handleTrigger()}
              loading={triggering}
            />
          </div>

          <div className="w-full lg:w-2/3 flex-1 overflow-y-auto">
            {Object.keys(scenarioResults).length > 0 ? (
              <div className="space-y-4">
                <div
                  className="text-[10px] font-mono tracking-[0.15em] uppercase sticky top-0 py-2 z-10"
                  style={{ color: "#4A5568", background: "#080B0F", borderBottom: "1px solid rgba(255,255,255,0.05)" }}
                >
                  Scenario Results — {selectedRun?.prompt_version_id}
                </div>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  {Object.entries(scenarioResults).map(([id, result], idx) => (
                    <div key={id} className="animate-fade-in-up" style={{ animationDelay: `${idx * 0.05}s`, opacity: 0, animationFillMode: "forwards" }}>
                      <ScenarioResultCard scenarioId={id} result={result} />
                    </div>
                  ))}
                </div>
              </div>
            ) : selectedRun?.status === "running" ? (
              <div className="flex flex-col items-center justify-center h-full gap-4 text-center">
                <div className="relative">
                  <div className="w-8 h-8 rounded-full border-2 border-[rgba(245,166,35,0.2)] border-t-[rgba(245,166,35,1)] animate-spin-slow" />
                  <div className="absolute inset-0 flex items-center justify-center">
                    <div className="w-2 h-2 rounded-full bg-[#F5A623] animate-pulse-dot" />
                  </div>
                </div>
                <div>
                  <div className="text-sm font-medium" style={{ color: "#F5A623" }}>Evaluating Scenarios</div>
                  <div className="text-[10px] font-mono mt-1" style={{ color: "#8B9BB4" }}>This usually takes 1-2 minutes</div>
                </div>
              </div>
            ) : (
              <div className="flex items-center justify-center h-full rounded-xl" style={{ border: "1px dashed rgba(255,255,255,0.1)" }}>
                <span className="text-xs font-mono" style={{ color: "#4A5568" }}>Select a completed run to view scenario details</span>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
