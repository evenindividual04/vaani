"use client";

import type { ConversationTurn, TurnMetrics } from "@/lib/types";
import { FNOLRecordCard } from "@/components/fnol/FNOLRecord";
import { PipelineStages } from "@/components/pipeline/PipelineStages";
import { fsmStateLabel, formatDuration } from "@/lib/utils";
import type { FNOLRecord } from "@/lib/types";

interface ConversationReplayProps {
  transcript: ConversationTurn[];
  perTurnMetrics: TurnMetrics[];
  finalFnol: FNOLRecord | null;
  durationSeconds?: number | null;
}

const FSM_STATE_COLORS: Record<string, string> = {
  GREETING: "#606060",
  POLICY_VERIFY: "#3B82F6",
  INCIDENT_CAPTURE: "#F59E0B",
  DETAILS_CAPTURE: "#F59E0B",
  CONTACT_VERIFY: "#14B8A6",
  SUMMARY: "#22C55E",
  COMPLETE: "#22C55E",
  ERROR: "#EF4444",
};

export function ConversationReplay({
  transcript,
  perTurnMetrics,
  finalFnol,
  durationSeconds,
}: ConversationReplayProps) {
  const metricsMap = Object.fromEntries(perTurnMetrics.map((m) => [m.turn_index, m]));
  const totalTurns = transcript.filter((t) => t.speaker === "user").length;

  return (
    <div className="flex gap-6 h-full">
      {/* Transcript + Timeline */}
      <div className="flex-1 overflow-y-auto space-y-0">
        {transcript.map((turn, i) => {
          const userTurnIdx = transcript.slice(0, i).filter((t) => t.speaker === "user").length;
          const metrics = turn.speaker === "user" ? metricsMap[userTurnIdx] : null;
          const stateColor = FSM_STATE_COLORS[turn.fsm_state] ?? "#606060";

          return (
            <div key={i} className="flex gap-3 group">
              {/* State indicator */}
              <div className="flex flex-col items-center">
                <div
                  className="w-2 h-2 rounded-full mt-4 shrink-0"
                  style={{ backgroundColor: stateColor }}
                />
                {i < transcript.length - 1 && (
                  <div className="w-px flex-1 bg-[#1A1A1A] min-h-4" />
                )}
              </div>

              <div className="flex-1 pb-3">
                <div className="flex items-center gap-2 mb-1">
                  <span className="text-[10px] font-mono text-[#606060] uppercase">
                    {turn.speaker === "user" ? "Caller" : "Agent"}
                  </span>
                  <span
                    className="text-[9px] font-mono px-1 rounded"
                    style={{ color: stateColor, backgroundColor: stateColor + "15" }}
                  >
                    {fsmStateLabel(turn.fsm_state)}
                  </span>
                </div>
                <div
                  className={`inline-block max-w-xl px-3 py-2 rounded text-sm leading-relaxed ${
                    turn.speaker === "user"
                      ? "bg-[#1A1A1A] text-[#F5F5F5]"
                      : "bg-[#0A4A44]/50 text-[#E0FFF9] border border-[#14B8A6]/10"
                  }`}
                >
                  {turn.text}
                </div>

                {/* Per-turn metrics (after user turn) */}
                {metrics && (
                  <div className="mt-2 opacity-0 group-hover:opacity-100 transition-opacity">
                    <PipelineStages
                      stt_ms={metrics.stt_ms}
                      llm_ms={metrics.llm_ms}
                      llm_ttft_ms={metrics.llm_ttft_ms}
                      tts_ms={metrics.tts_ms}
                      total_ms={metrics.total_ms}
                      stt_provider={metrics.stt_provider}
                      llm_provider={metrics.llm_provider}
                      tts_provider={metrics.tts_provider}
                      fallback_triggered={metrics.fallback_triggered}
                      compact
                    />
                  </div>
                )}
              </div>
            </div>
          );
        })}
      </div>

      {/* FNOL sidebar */}
      <div className="w-72 shrink-0 space-y-4">
        <div className="text-xs text-[#606060] uppercase tracking-widest font-mono">
          Final FNOL Record
        </div>
        {finalFnol ? (
          <FNOLRecordCard fnol={finalFnol} completenessScore={finalFnol.completeness_score} />
        ) : (
          <div className="flex items-center justify-center h-32 border border-[#2A2A2A] rounded text-[#444444] text-sm">
            No FNOL extracted
          </div>
        )}
        <div className="text-xs text-[#606060] font-mono space-y-1">
          <div className="flex justify-between">
            <span>Duration</span>
            <span className="text-[#A0A0A0]">{formatDuration(durationSeconds ?? null)}</span>
          </div>
          <div className="flex justify-between">
            <span>Turns</span>
            <span className="text-[#A0A0A0]">{totalTurns}</span>
          </div>
        </div>
      </div>
    </div>
  );
}
