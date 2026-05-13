"use client";

import { useCallStore } from "@/store/callStore";
import { useCallWebSocket } from "@/hooks/useCallWebSocket";
import { LiveCallPanel } from "@/components/calls/LiveCallPanel";
import { CallCard } from "@/components/calls/CallCard";

function EmptyState({ isConnected }: { isConnected: boolean }) {
  return (
    <div className="flex-1 flex flex-col items-center justify-center gap-6">
      {/* Concentric rings */}
      <div className="relative flex items-center justify-center" style={{ width: 120, height: 120 }}>
        <div
          className="absolute rounded-full"
          style={{
            width: 120, height: 120,
            border: "1px solid rgba(0,212,200,0.08)",
            animation: "ping-ring 3s cubic-bezier(0,0,0.2,1) infinite",
          }}
        />
        <div
          className="absolute rounded-full"
          style={{
            width: 90, height: 90,
            border: "1px solid rgba(0,212,200,0.12)",
            animation: "ping-ring 3s cubic-bezier(0,0,0.2,1) infinite 0.5s",
          }}
        />
        <div
          className="absolute rounded-full"
          style={{
            width: 60, height: 60,
            border: "1px solid rgba(0,212,200,0.18)",
            animation: "ping-ring 3s cubic-bezier(0,0,0.2,1) infinite 1s",
          }}
        />
        {/* Center mic icon */}
        <div
          className="relative z-10 w-12 h-12 rounded-full flex items-center justify-center"
          style={{
            background: "rgba(0,212,200,0.1)",
            border: "1px solid rgba(0,212,200,0.25)",
            boxShadow: "0 0 20px rgba(0,212,200,0.15)",
          }}
        >
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#00D4C8" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <rect x="9" y="3" width="6" height="11" rx="3"/>
            <path d="M5 11c0 3.866 3.134 7 7 7s7-3.134 7-7"/>
            <line x1="12" y1="18" x2="12" y2="22"/>
            <line x1="8" y1="22" x2="16" y2="22"/>
          </svg>
        </div>
      </div>

      <div className="text-center space-y-1.5">
        <p
          className="text-sm font-medium"
          style={{ color: "#8B9BB4" }}
        >
          No active calls
        </p>
        <p
          className="text-xs font-mono"
          style={{ color: "#2D3748" }}
        >
          {isConnected
            ? "Monitoring — waiting for incoming calls"
            : "Connect to the backend to start monitoring"}
        </p>
      </div>

      {/* Status pill */}
      <div
        className="flex items-center gap-2 px-4 py-2 rounded-full"
        style={{
          background: isConnected ? "rgba(0,230,118,0.06)" : "rgba(255,69,69,0.06)",
          border: `1px solid ${isConnected ? "rgba(0,230,118,0.2)" : "rgba(255,69,69,0.2)"}`,
        }}
      >
        <div
          className="w-1.5 h-1.5 rounded-full"
          style={{ background: isConnected ? "#00E676" : "#FF4545" }}
        />
        <span
          className="text-[10px] font-mono"
          style={{ color: isConnected ? "#00E676" : "#FF4545" }}
        >
          {isConnected ? "WebSocket connected" : "WebSocket disconnected"}
        </span>
      </div>
    </div>
  );
}

export default function HomePage() {
  const { isConnected } = useCallWebSocket();
  const liveCalls = useCallStore((s) => s.liveCalls);
  const selectedCallId = useCallStore((s) => s.selectedCallId);
  const selectCall = useCallStore((s) => s.selectCall);
  const callIds = Object.keys(liveCalls);
  const activeCallId = selectedCallId ?? callIds[0];

  return (
    <div className="flex flex-col h-screen p-6 gap-5" style={{ background: "#080B0F" }}>
      {/* Header */}
      <div className="flex items-center justify-between flex-shrink-0">
        <div>
          <h1
            className="font-bold text-xl tracking-wide"
            style={{ color: "#F0F4F8", fontFamily: "Inter, sans-serif" }}
          >
            Live Calls
          </h1>
          <p className="text-xs font-mono mt-0.5" style={{ color: "#4A5568" }}>
            Real-time FNOL voice agent monitoring
          </p>
        </div>

        {/* Stats row */}
        <div className="flex items-center gap-4">
          <div
            className="flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs font-mono"
            style={{
              background: "rgba(0,212,200,0.06)",
              border: "1px solid rgba(0,212,200,0.15)",
              color: "#00D4C8",
            }}
          >
            <span className="font-bold text-sm">{callIds.length}</span>
            <span style={{ color: "#4A5568" }}>active call{callIds.length !== 1 ? "s" : ""}</span>
          </div>

          <div
            className="flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs font-mono"
            style={{
              background: isConnected ? "rgba(0,230,118,0.06)" : "rgba(255,69,69,0.06)",
              border: `1px solid ${isConnected ? "rgba(0,230,118,0.15)" : "rgba(255,69,69,0.15)"}`,
            }}
          >
            <div className="relative">
              <div
                className="w-1.5 h-1.5 rounded-full"
                style={{ background: isConnected ? "#00E676" : "#FF4545" }}
              />
              {isConnected && (
                <div
                  className="absolute inset-0 rounded-full animate-ping-ring"
                  style={{ background: "#00E676" }}
                />
              )}
            </div>
            <span style={{ color: isConnected ? "#00E676" : "#FF4545" }}>
              {isConnected ? "LIVE" : "OFFLINE"}
            </span>
          </div>
        </div>
      </div>

      {/* Content */}
      {callIds.length === 0 ? (
        <EmptyState isConnected={isConnected} />
      ) : (
        <div className="flex flex-1 min-h-0 gap-4">
          {/* Call list sidebar (only if multiple calls) */}
          {callIds.length > 1 && (
            <div className="w-52 shrink-0 space-y-2 overflow-y-auto">
              {callIds.map((id) => (
                <CallCard key={id} callId={id} isSelected={id === activeCallId} />
              ))}
            </div>
          )}

          {/* Main panel */}
          <div className="flex-1 min-h-0">
            <LiveCallPanel callId={activeCallId} />
          </div>
        </div>
      )}
    </div>
  );
}
