"use client";

import { useState } from "react";
import useSWR from "swr";
import { swrFetcher, deployPrompt, rollbackPrompt } from "@/lib/api";
import { PromptEditor, VersionDiff } from "@/components/prompts/PromptEditor";
import { formatDate } from "@/lib/utils";
import type { PromptVersion } from "@/lib/types";

type Tab = "view" | "diff";

export default function PromptsPage() {
  const { data, isLoading, mutate } = useSWR("/prompts", swrFetcher);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [compareId, setCompareId] = useState<string | null>(null);
  const [tab, setTab] = useState<Tab>("view");
  const [actionLoading, setActionLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const versions: PromptVersion[] = (data as any)?.versions ?? [];
  const activeVersion: string | null = (data as any)?.active_version ?? null;
  const selectedVersion = versions.find((v) => v.version_id === selectedId) ?? versions[0] ?? null;

  const { data: promptDetail } = useSWR(
    selectedVersion ? `/prompts/${selectedVersion.version_id}` : null,
    swrFetcher
  );
  const templates = (promptDetail as any)?.templates ?? {};

  const handleDeploy = async () => {
    if (!selectedVersion) return;
    setActionLoading(true);
    setError(null);
    try {
      await deployPrompt(selectedVersion.version_id);
      mutate();
    } catch (e: any) {
      setError(e.message);
    } finally {
      setActionLoading(false);
    }
  };

  const handleRollback = async () => {
    if (!selectedVersion) return;
    setActionLoading(true);
    setError(null);
    try {
      await rollbackPrompt(selectedVersion.version_id);
      mutate();
    } catch (e: any) {
      setError(e.message);
    } finally {
      setActionLoading(false);
    }
  };

  const compareVersion = versions.find((v) => v.version_id === compareId);

  return (
    <div className="flex h-screen p-6 gap-6" style={{ background: "#080B0F" }}>
      {/* Version sidebar */}
      <div className="w-64 shrink-0 flex flex-col gap-3">
        <div className="text-[10px] font-mono uppercase tracking-[0.15em]" style={{ color: "#4A5568" }}>
          Prompt History
        </div>

        <div className="flex-1 overflow-y-auto space-y-2 pr-1">
          {isLoading ? (
            <div className="text-xs font-mono" style={{ color: "#4A5568" }}>Loading…</div>
          ) : (
            versions.map((v) => {
              const isSelected = v.version_id === selectedVersion?.version_id;
              const isLive = v.version_id === activeVersion;
              const scoreColor = (v.eval_score ?? 0) >= 0.8 ? "#00E676" : "#F5A623";

              return (
                <button
                  key={v.version_id}
                  onClick={() => setSelectedId(v.version_id)}
                  className="w-full text-left p-3 rounded-xl transition-all duration-200 group"
                  style={{
                    background: isSelected ? "rgba(0,212,200,0.08)" : "rgba(12,16,23,0.7)",
                    border: `1px solid ${isSelected ? "rgba(0,212,200,0.3)" : "rgba(255,255,255,0.06)"}`,
                  }}
                >
                  <div className="flex items-start justify-between mb-2">
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-mono font-bold" style={{ color: isSelected ? "#00D4C8" : "#C8D4E0" }}>
                        {v.version_id}
                      </span>
                      {isLive && (
                        <span className="text-[9px] font-mono px-1.5 py-0.5 rounded" style={{ background: "rgba(0,212,200,0.15)", color: "#00D4C8" }}>
                          LIVE
                        </span>
                      )}
                    </div>
                    {v.eval_score != null && (
                      <div className="text-[10px] font-mono" style={{ color: scoreColor }}>
                        {Math.round(v.eval_score * 100)}% acc
                      </div>
                    )}
                  </div>
                  <div className="text-[11px] leading-snug line-clamp-2 mb-2" style={{ color: isSelected ? "#8B9BB4" : "#4A5568" }}>
                    {v.description}
                  </div>
                  <div className="text-[9px] font-mono" style={{ color: "#4A5568" }}>
                    {formatDate(v.created_at)}
                  </div>
                </button>
              );
            })
          )}
        </div>
      </div>

      {/* Main content */}
      <div className="flex-1 flex flex-col min-w-0 bg-[#080B0F]">
        {selectedVersion && (
          <>
            {/* Header */}
            <div className="flex items-start justify-between mb-6 flex-shrink-0">
              <div>
                <h1 className="font-bold text-xl tracking-wide flex items-center gap-3" style={{ color: "#F0F4F8", fontFamily: "Inter, sans-serif" }}>
                  {selectedVersion.version_id}
                  {selectedVersion.version_id === activeVersion && (
                    <span className="text-[10px] font-mono px-2 py-1 rounded-lg" style={{ background: "rgba(0,212,200,0.1)", color: "#00D4C8", border: "1px solid rgba(0,212,200,0.2)" }}>
                      CURRENTLY DEPLOYED
                    </span>
                  )}
                </h1>
                <p className="text-sm mt-1 max-w-2xl" style={{ color: "#8B9BB4" }}>
                  {selectedVersion.description}
                </p>
              </div>

              <div className="flex items-center gap-3">
                {selectedVersion.version_id !== activeVersion ? (
                  <button
                    onClick={handleDeploy}
                    disabled={actionLoading}
                    className="btn-teal font-bold shadow-glow-teal"
                    style={{ padding: "8px 20px" }}
                  >
                    DEPLOY PROMPT
                  </button>
                ) : (
                  <button
                    onClick={handleRollback}
                    disabled={actionLoading}
                    className="btn-amber font-bold shadow-glow-amber"
                    style={{ padding: "8px 20px" }}
                  >
                    ROLLBACK TO PREVIOUS
                  </button>
                )}
              </div>
            </div>

            {error && (
              <div className="px-4 py-3 rounded-lg text-xs font-mono mb-4 flex-shrink-0" style={{ background: "rgba(255,69,69,0.1)", color: "#FF4545", border: "1px solid rgba(255,69,69,0.2)" }}>
                Error: {error}
              </div>
            )}

            {/* Tabs */}
            <div className="flex items-center gap-4 mb-4 flex-shrink-0" style={{ borderBottom: "1px solid rgba(255,255,255,0.05)" }}>
              {(["view", "diff"] as Tab[]).map((t) => (
                <button
                  key={t}
                  onClick={() => setTab(t)}
                  className="px-2 py-3 text-[11px] font-mono uppercase tracking-widest transition-colors relative"
                  style={{ color: tab === t ? "#00D4C8" : "#4A5568" }}
                >
                  {t === "view" ? "View Templates" : "Compare Changes"}
                  {tab === t && (
                    <div className="absolute bottom-0 left-0 right-0 h-0.5" style={{ background: "#00D4C8", boxShadow: "0 0 8px rgba(0,212,200,0.6)" }} />
                  )}
                </button>
              ))}
            </div>

            <div className="flex-1 min-h-0 relative">
              {tab === "view" && (
                <PromptEditor
                  templates={templates}
                  onChange={() => {}}
                  readOnly
                />
              )}
              {tab === "diff" && (
                <div className="absolute inset-0 flex flex-col gap-4">
                  <div className="flex items-center gap-3 flex-shrink-0">
                    <span className="text-xs font-mono" style={{ color: "#4A5568" }}>Compare with:</span>
                    <select
                      value={compareId ?? ""}
                      onChange={(e) => setCompareId(e.target.value || null)}
                      className="input-dark w-48"
                    >
                      <option value="">Select version…</option>
                      {versions
                        .filter((v) => v.version_id !== selectedVersion.version_id)
                        .map((v) => (
                          <option key={v.version_id} value={v.version_id}>{v.version_id}</option>
                        ))}
                    </select>
                  </div>
                  <div className="flex-1 min-h-0">
                    {compareVersion ? (
                      <VersionDiff versionA={selectedVersion} versionB={compareVersion} />
                    ) : (
                      <div className="flex items-center justify-center h-full rounded-xl" style={{ border: "1px dashed rgba(255,255,255,0.1)" }}>
                        <span className="text-xs font-mono" style={{ color: "#4A5568" }}>Select a version to compare</span>
                      </div>
                    )}
                  </div>
                </div>
              )}
            </div>
          </>
        )}
      </div>
    </div>
  );
}
