"use client";

import { useEffect, useState } from "react";
import { useCallStore } from "@/store/callStore";
import { channelIcon, formatRelative, fsmStateLabel, completenessColor } from "@/lib/utils";

const FSM_STATES = [
  { key: "GREETING", label: "Greeting" },
  { key: "POLICY_VERIFY", label: "Policy" },
  { key: "INCIDENT_CAPTURE", label: "Incident" },
  { key: "DETAILS_CAPTURE", label: "Details" },
  { key: "CONTACT_VERIFY", label: "Contact" },
  { key: "SUMMARY", label: "Summary" },
];

function ElapsedTimer({ startedAt }: { startedAt: string }) {
  const [elapsed, setElapsed] = useState(0);
  useEffect(() => {
    const start = new Date(startedAt).getTime();
    const tick = () => setElapsed(Math.floor((Date.now() - start) / 1000));
    tick();
    const id = setInterval(tick, 1000);
    return () => clearInterval(id);
  }, [startedAt]);
  const m = Math.floor(elapsed / 60);
  const s = elapsed % 60;
  return (
    <span className="font-mono text-xs text-[#71717A]">
      {m > 0 ? `${m}m ` : ""}{s}s
    </span>
  );
}

function ChannelSVG({ channel }: { channel: string }) {
  if (channel === "phone") return (
    <svg width="12" height="12" viewBox="0 0 24 24" fill="currentColor">
      <path d="M20.01 15.38c-1.23 0-2.42-.2-3.53-.56a.977.977 0 0 0-1.01.24l-1.57 1.97c-2.83-1.35-5.48-3.9-6.89-6.83l1.95-1.66c.27-.28.35-.67.24-1.02-.37-1.11-.56-2.3-.56-3.53 0-.54-.45-.99-.99-.99H4.19C3.65 3 3 3.24 3 3.99 3 13.28 10.73 21 20.01 21c.71 0 .99-.63.99-1.18v-3.45c0-.54-.45-.99-.99-.99z"/>
    </svg>
  );
  if (channel === "web") return (
    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <circle cx="12" cy="12" r="10"/>
      <line x1="2" y1="12" x2="22" y2="12"/>
      <path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"/>
    </svg>
  );
  return (
    <svg width="12" height="12" viewBox="0 0 24 24" fill="currentColor">
      <path d="M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.298-.347.446-.52.149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207-.242-.579-.487-.5-.669-.51-.173-.008-.371-.01-.57-.01-.198 0-.52.074-.792.372-.272.297-1.04 1.016-1.04 2.479 0 1.462 1.065 2.875 1.213 3.074.149.198 2.096 3.2 5.077 4.487.709.306 1.262.489 1.694.625.712.227 1.36.195 1.871.118.571-.085 1.758-.719 2.006-1.413.248-.694.248-1.289.173-1.413-.074-.124-.272-.198-.57-.347m-5.421 7.403h-.004a9.87 9.87 0 0 1-5.031-1.378l-.361-.214-3.741.982.998-3.648-.235-.374a9.86 9.86 0 0 1-1.51-5.26c.001-5.45 4.436-9.884 9.888-9.884 2.64 0 5.122 1.03 6.988 2.898a9.825 9.825 0 0 1 2.893 6.994c-.003 5.45-4.437 9.884-9.885 9.884m8.413-18.297A11.815 11.815 0 0 0 12.05 0C5.495 0 .16 5.335.157 11.892c0 2.096.547 4.142 1.588 5.945L.057 24l6.305-1.654a11.882 11.882 0 0 0 5.683 1.448h.005c6.554 0 11.89-5.335 11.893-11.893a11.821 11.821 0 0 0-3.48-8.413Z"/>
    </svg>
  );
}

interface CallCardProps {
  callId: string;
  isSelected?: boolean;
}

export function CallCard({ callId, isSelected }: CallCardProps) {
  const call = useCallStore((s) => s.liveCalls[callId]);
  const selectCall = useCallStore((s) => s.selectCall);
  if (!call) return null;

  const pct = Math.round(call.completeness_score * 100);
  const color = completenessColor(call.completeness_score);
  const stateIdx = FSM_STATES.findIndex((s) => s.key === call.fsm_state);

  // SVG ring
  const R = 18;
  const circumference = 2 * Math.PI * R;
  const dash = (pct / 100) * circumference;

  return (
    <div
      onClick={() => selectCall(callId)}
      className="cursor-pointer rounded-lg p-3 transition-all duration-150 animate-fade-in border shadow-sm"
      style={{
        background: isSelected ? "#161616" : "#111111",
        borderColor: isSelected ? "#52525B" : "#2A2A2A",
      }}
    >
      {/* Header row */}
      <div className="flex items-center gap-2 mb-2">
        <span className="flex items-center justify-center w-6 h-6 rounded bg-[#1C1C1C] text-[#A1A1AA] border border-[#2A2A2A]">
          <ChannelSVG channel={call.channel} />
        </span>

        <div className="flex items-center gap-1.5 flex-1 min-w-0">
          <div className="w-1.5 h-1.5 rounded-full flex-shrink-0 animate-pulse-dot bg-[#34D399]" />
          <span className="text-[10px] font-mono text-[#FAFAFA] font-medium">LIVE</span>
        </div>

        {/* Completeness ring */}
        <svg width="44" height="44" className="flex-shrink-0">
          <circle
            cx="22" cy="22" r={R}
            fill="none"
            stroke="#2A2A2A"
            strokeWidth="3"
          />
          <circle
            cx="22" cy="22" r={R}
            fill="none"
            stroke={color}
            strokeWidth="3"
            strokeLinecap="round"
            strokeDasharray={`${dash} ${circumference}`}
            transform="rotate(-90 22 22)"
            style={{ transition: "stroke-dasharray 0.5s ease" }}
          />
          <text
            x="22" y="26"
            textAnchor="middle"
            fontSize="9"
            fontFamily="JetBrains Mono, monospace"
            fill={color}
          >
            {pct}%
          </text>
        </svg>
      </div>

      {/* Call ID + time */}
      <div className="flex items-center justify-between mb-2">
        <span className="text-[10px] font-mono text-[#71717A]">
          {callId.slice(0, 8)}…
        </span>
        <ElapsedTimer startedAt={call.started_at} />
      </div>

      {/* Language + State */}
      <div className="flex items-center gap-1.5">
        <span className="text-[9px] font-mono px-1.5 py-0.5 rounded bg-[#1C1C1C] text-[#A1A1AA] border border-[#2A2A2A]">
          {call.language}
        </span>
        <span className="text-[9px] font-mono px-1.5 py-0.5 rounded bg-[#262626] text-[#FAFAFA] border border-[#3E3E3E]">
          {fsmStateLabel(call.fsm_state)}
        </span>
      </div>

      {/* Mini FSM progress */}
      <div className="flex items-center gap-0.5 mt-2">
        {FSM_STATES.map((state, i) => (
          <div
            key={state.key}
            className="flex-1 h-0.5 rounded-full transition-all duration-500"
            style={{
              background: i < stateIdx ? "#A1A1AA" : i === stateIdx ? "#FAFAFA" : "#2A2A2A",
            }}
          />
        ))}
      </div>
    </div>
  );
}
