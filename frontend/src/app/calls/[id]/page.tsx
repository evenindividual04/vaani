"use client";

import { use } from "react";
import useSWR from "swr";
import { swrFetcher } from "@/lib/api";
import { ConversationReplay } from "@/components/replay/ConversationReplay";
import { channelIcon, formatDate, formatDuration, outcomeColor } from "@/lib/utils";
import Link from "next/link";

interface Props {
  params: Promise<{ id: string }>;
}

export default function CallDetailPage({ params }: Props) {
  const { id } = use(params);

  const { data: call, isLoading: callLoading } = useSWR(`/calls/${id}`, swrFetcher);
  const { data: replay, isLoading: replayLoading } = useSWR(`/calls/${id}/replay`, swrFetcher);

  if (callLoading || replayLoading) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="text-[#606060] font-mono text-sm">Loading call…</div>
      </div>
    );
  }

  if (!call) {
    return (
      <div className="p-6">
        <p className="text-[#EF4444] font-mono text-sm">Call not found.</p>
        <Link href="/calls" className="text-xs text-[#14B8A6] font-mono mt-2 inline-block">
          ← Back to calls
        </Link>
      </div>
    );
  }

  const callData = call as any;
  const replayData = replay as any;

  return (
    <div className="flex flex-col h-full p-6 gap-4">
      {/* Header */}
      <div className="flex items-center gap-4">
        <Link
          href="/calls"
          className="text-xs font-mono text-[#606060] hover:text-[#A0A0A0] transition-colors"
        >
          ← Calls
        </Link>
        <div className="flex items-center gap-3 flex-1">
          <span className="text-xl">{channelIcon(callData.channel)}</span>
          <div>
            <div className="flex items-center gap-3">
              <h1 className="font-condensed font-bold text-xl text-[#F5F5F5] uppercase tracking-wide">
                Call {id.slice(0, 8)}…
              </h1>
              <span
                className="text-xs font-mono px-2 py-0.5 rounded border uppercase"
                style={{
                  color: outcomeColor(callData.outcome),
                  borderColor: outcomeColor(callData.outcome) + "40",
                  backgroundColor: outcomeColor(callData.outcome) + "10",
                }}
              >
                {callData.outcome}
              </span>
            </div>
            <p className="text-xs text-[#606060] font-mono mt-0.5">
              {formatDate(callData.started_at)} · {callData.language} · {formatDuration(callData.duration_seconds)} · {callData.prompt_version}
            </p>
          </div>
        </div>
        {callData.audio_available && (
          <a
            href={`${process.env.NEXT_PUBLIC_API_URL}/calls/${id}/audio`}
            className="text-xs px-3 py-2 bg-[#141414] border border-[#2A2A2A] rounded hover:border-[#3A3A3A] font-mono transition-colors"
            download
          >
            ↓ Audio
          </a>
        )}
      </div>

      {/* Replay */}
      <div className="flex-1 min-h-0 overflow-hidden">
        {replayData ? (
          <ConversationReplay
            transcript={replayData.transcript ?? []}
            perTurnMetrics={replayData.per_turn_metrics ?? []}
            finalFnol={replayData.final_fnol ?? null}
            durationSeconds={callData.duration_seconds}
          />
        ) : (
          <div className="flex items-center justify-center h-full border border-[#2A2A2A] rounded text-[#606060] text-sm font-mono">
            No replay data available
          </div>
        )}
      </div>
    </div>
  );
}
