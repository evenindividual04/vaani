"use client";

import { useRef, useEffect } from "react";
import { FNOLRecordCard } from "@/components/fnol/FNOLRecord";
import { PipelineStages } from "@/components/pipeline/PipelineStages";
import { useCallStore } from "@/store/callStore";
import { fsmStateLabel } from "@/lib/utils";
import type { TurnMetrics } from "@/lib/types";

interface LiveCallPanelProps {
  callId: string;
}

const FSM_STEPS = [
  { key: "GREETING",         label: "Greeting" },
  { key: "POLICY_VERIFY",    label: "Policy" },
  { key: "INCIDENT_CAPTURE", label: "Incident" },
  { key: "DETAILS_CAPTURE",  label: "Details" },
  { key: "CONTACT_VERIFY",   label: "Contact" },
  { key: "SUMMARY",          label: "Summary" },
];

function ChannelBadge({ channel }: { channel: string }) {
  const icons: Record<string, string> = { phone: "📞", web: "🌐", whatsapp: "💬" };
  const colors: Record<string, string> = {
    phone:    "rgba(76,158,255,0.15)",
    web:      "rgba(0,212,200,0.12)",
    whatsapp: "rgba(0,230,118,0.12)",
  };
  const textColors: Record<string, string> = {
    phone: "#4C9EFF",
    web:   "#00D4C8",
    whatsapp: "#00E676",
  };
  return (
    <div
      className="flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs font-mono"
      style={{ background: colors[channel] ?? "rgba(255,255,255,0.06)", color: textColors[channel] ?? "#8B9BB4" }}
    >
      <span className="text-sm leading-none">{icons[channel] ?? "?"}</span>
      <span className="uppercase tracking-wider text-[10px]">{channel}</span>
    </div>
  );
}

export function LiveCallPanel({ callId }: LiveCallPanelProps) {
  const call = useCallStore((s) => s.liveCalls[callId]);
  const transcriptEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    transcriptEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [call?.turns]);

  if (!call) return null;

  const currentStateIdx = FSM_STEPS.findIndex((s) => s.key === call.fsm_state);
  const lastMetrics: TurnMetrics | null = call.metrics[call.metrics.length - 1] ?? null;

  return (
    <div className="flex flex-col h-full rounded-lg overflow-hidden bg-[#0A0A0A] border border-[#2A2A2A] shadow-sm">
      {/* ── Header ───────────────────────────────────────────────────────── */}
      <div className="flex items-center gap-3 px-5 py-3.5 flex-shrink-0 bg-[#111111] border-b border-[#2A2A2A]">
        {/* Live pulse */}
        <div className="relative flex-shrink-0">
          <div className="w-2 h-2 rounded-full bg-[#34D399]" />
          <div className="absolute inset-0 rounded-full animate-ping-ring bg-[#34D399]" />
        </div>

        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <span className="text-xs font-mono font-medium text-[#FAFAFA]">
              LIVE
            </span>
            <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-[#1C1C1C] text-[#71717A]">
              {callId.slice(0, 8)}…
            </span>
          </div>
          <div className="text-[11px] mt-0.5 text-[#52525B] font-mono uppercase">
            {call.language}
          </div>
        </div>

        <ChannelBadge channel={call.channel} />

        <div
          className="badge badge-amber"
          style={{ fontSize: 10 }}
        >
          {fsmStateLabel(call.fsm_state)}
        </div>
      </div>

      {/* ── FSM Progress ─────────────────────────────────────────────────── */}
      <div className="px-5 py-3 flex-shrink-0 border-b border-[#2A2A2A] bg-[#0A0A0A]">
        <div className="flex items-center gap-0">
          {FSM_STEPS.map((step, i) => {
            const isDone   = i < currentStateIdx;
            const isActive = i === currentStateIdx;
            return (
              <div key={step.key} className="flex items-center flex-1">
                <div className="flex flex-col items-center gap-1.5" style={{ minWidth: 40 }}>
                  <div
                    className={`w-2 h-2 rounded-full transition-all duration-300 ${isActive ? "animate-pulse-dot" : ""}`}
                    style={{
                      background: isDone ? "#A1A1AA" : isActive ? "#FAFAFA" : "#2A2A2A",
                    }}
                  />
                  <span
                    className="text-[9px] font-mono leading-none hidden sm:block"
                    style={{ color: isDone ? "#A1A1AA" : isActive ? "#FAFAFA" : "#52525B" }}
                  >
                    {step.label}
                  </span>
                </div>
                {i < FSM_STEPS.length - 1 && (
                  <div
                    className="flex-1 h-[1px] mx-2 transition-all duration-300"
                    style={{
                      background: i < currentStateIdx ? "#52525B" : "#2A2A2A",
                    }}
                  />
                )}
              </div>
            );
          })}
        </div>
      </div>

      {/* ── Body ─────────────────────────────────────────────────────────── */}
      <div className="flex flex-1 min-h-0">

        {/* Transcript */}
        <div className="flex-1 overflow-y-auto px-5 py-4 space-y-3">
          {call.turns.length === 0 && (
            <div
              className="flex flex-col items-center justify-center h-full gap-3 text-center"
              style={{ color: "#2D3748" }}
            >
              <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>
              </svg>
              <p className="text-xs font-mono">Waiting for conversation…</p>
            </div>
          )}
          {call.turns.map((turn, i) => (
            <div
              key={i}
              className={`flex gap-2 animate-fade-in-up ${turn.speaker === "agent" ? "flex-row-reverse" : ""}`}
            >
              {/* Speaker label */}
              <div className="flex flex-col items-center gap-1 mt-1 flex-shrink-0">
                <div
                  className="w-5 h-5 rounded flex items-center justify-center text-[10px] font-medium font-mono"
                  style={{
                    background: turn.speaker === "agent" ? "#161616" : "#262626",
                    color: turn.speaker === "agent" ? "#FAFAFA" : "#A1A1AA",
                    border: "1px solid #2A2A2A"
                  }}
                >
                  {turn.speaker === "agent" ? "A" : "U"}
                </div>
              </div>

              {/* Bubble */}
              <div
                className="max-w-[78%] px-3.5 py-2.5 text-[13px] leading-relaxed shadow-sm"
                style={
                  turn.speaker === "agent"
                    ? {
                        background: "#161616",
                        border: "1px solid #2A2A2A",
                        borderRadius: "6px",
                        color: "#E4E4E7",
                      }
                    : {
                        background: "#262626",
                        border: "1px solid #3E3E3E",
                        borderRadius: "6px",
                        color: "#A1A1AA",
                      }
                }
              >
                {turn.text}
              </div>
            </div>
          ))}
          <div ref={transcriptEndRef} />
        </div>

        {/* Right panel */}
        <div className="w-[260px] shrink-0 overflow-y-auto flex flex-col gap-4 p-4 border-l border-[#2A2A2A] bg-[#0A0A0A]">
          <FNOLRecordCard
            fnol={call.fnol}
            completenessScore={call.completeness_score}
            missingFields={call.missing_fields}
          />

          {lastMetrics && (
            <div>
              <div
                className="text-[9px] font-mono tracking-[0.15em] mb-3 uppercase"
                style={{ color: "#2D3748" }}
              >
                Last Turn Pipeline
              </div>
              <PipelineStages
                stt_ms={lastMetrics.stt_ms}
                llm_ms={lastMetrics.llm_ms}
                llm_ttft_ms={lastMetrics.llm_ttft_ms}
                tts_ms={lastMetrics.tts_ms}
                total_ms={lastMetrics.total_ms}
                stt_provider={lastMetrics.stt_provider}
                llm_provider={lastMetrics.llm_provider}
                tts_provider={lastMetrics.tts_provider}
                fallback_triggered={lastMetrics.fallback_triggered}
              />
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
