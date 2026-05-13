"use client";

import type { CallRecord } from "@/lib/types";
import { formatDate, formatDuration, outcomeColor, completenessColor } from "@/lib/utils";

interface CallHistoryTableProps {
  calls: CallRecord[];
  total: number;
  page: number;
  pageSize?: number;
  onPageChange: (page: number) => void;
  onRowClick: (callId: string) => void;
}

const CHANNEL_ICONS: Record<string, string> = {
  phone: "📞",
  web: "🌐",
  whatsapp: "💬",
};

function OutcomeBadge({ outcome }: { outcome: string }) {
  const color = outcomeColor(outcome);
  return (
    <div className="flex items-center gap-1.5">
      <div
        className="w-1.5 h-1.5 rounded-full flex-shrink-0"
        style={{ background: color }}
      />
      <span
        className="text-xs font-mono"
        style={{ color }}
      >
        {outcome}
      </span>
    </div>
  );
}

function CompletenessRing({ score }: { score: number }) {
  const pct = Math.round(score * 100);
  const color = completenessColor(score);
  const R = 10;
  const circumference = 2 * Math.PI * R;
  const dash = (pct / 100) * circumference;

  return (
    <div className="flex items-center gap-2">
      <svg width="28" height="28">
        <circle cx="14" cy="14" r={R} fill="none" stroke="#2A2A2A" strokeWidth="2.5"/>
        <circle
          cx="14" cy="14" r={R}
          fill="none"
          stroke={color}
          strokeWidth="2.5"
          strokeLinecap="round"
          strokeDasharray={`${dash} ${circumference}`}
          transform="rotate(-90 14 14)"
        />
      </svg>
      <span className="text-[11px] font-mono" style={{ color }}>{pct}%</span>
    </div>
  );
}

function SkeletonRow() {
  return (
    <tr>
      {[...Array(7)].map((_, i) => (
        <td key={i} className="px-4 py-4">
          <div
            className="h-3 rounded"
            style={{
              width: `${50 + Math.random() * 40}%`,
              background: "linear-gradient(90deg, #161616 25%, #1C1C1C 50%, #161616 75%)",
              backgroundSize: "400% 100%",
              animation: "shimmer 1.6s ease-in-out infinite",
            }}
          />
        </td>
      ))}
    </tr>
  );
}

export function CallHistoryTable({
  calls,
  total,
  page,
  pageSize = 20,
  onPageChange,
  onRowClick,
}: CallHistoryTableProps) {
  const totalPages = Math.ceil(total / pageSize);

  return (
    <div className="flex flex-col h-full">
      <div className="overflow-auto flex-1">
        <table className="w-full border-collapse" style={{ minWidth: 720 }}>
          <thead>
            <tr className="bg-[#111111]">
              {["Channel", "Language", "Started", "Duration", "Outcome", "Completeness", "Version"].map((h) => (
                <th
                  key={h}
                  className="text-left px-4 py-3 text-[10px] font-mono font-medium uppercase tracking-wider whitespace-nowrap text-[#71717A] border-b border-[#2A2A2A] sticky top-0 z-10 bg-[#111111]"
                >
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {calls.map((call, idx) => (
              <tr
                key={call.call_id}
                onClick={() => onRowClick(call.call_id)}
                className="cursor-pointer transition-colors duration-150 animate-fade-in hover:bg-[#161616]"
                style={{
                  borderBottom: "1px solid #2A2A2A",
                  animationDelay: `${idx * 0.03}s`,
                  opacity: 0,
                  animationFillMode: "forwards"
                }}
              >
                {/* Channel */}
                <td className="px-4 py-3">
                  <div className="flex items-center gap-2">
                    <span className="text-base leading-none">
                      {CHANNEL_ICONS[call.channel] ?? "?"}
                    </span>
                    <span className="text-xs capitalize text-[#A1A1AA]">
                      {call.channel}
                    </span>
                  </div>
                </td>

                {/* Language */}
                <td className="px-4 py-3">
                  <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-[#1C1C1C] text-[#A1A1AA] border border-[#2A2A2A]">
                    {call.language}
                  </span>
                </td>

                {/* Started */}
                <td className="px-4 py-3">
                  <span className="text-xs font-mono text-[#A1A1AA]">
                    {formatDate(call.started_at)}
                  </span>
                </td>

                {/* Duration */}
                <td className="px-4 py-3">
                  <span className="text-xs font-mono text-[#A1A1AA]">
                    {formatDuration(call.duration_seconds)}
                  </span>
                </td>

                {/* Outcome */}
                <td className="px-4 py-3">
                  <OutcomeBadge outcome={call.outcome} />
                </td>

                {/* Completeness */}
                <td className="px-4 py-3">
                  {call.fnol_record ? (
                    <CompletenessRing score={call.fnol_record.completeness_score ?? 0} />
                  ) : (
                    <span className="text-xs text-[#52525B]">—</span>
                  )}
                </td>

                {/* Version */}
                <td className="px-4 py-3">
                  <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-[#1C1C1C] text-[#FBBF24] border border-[#2A2A2A]">
                    {call.prompt_version}
                  </span>
                </td>
              </tr>
            ))}

            {calls.length === 0 && (
              <tr>
                <td
                  colSpan={7}
                  className="text-center py-20 text-sm font-mono text-[#52525B]"
                >
                  No calls found
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-between px-4 py-3 border-t border-[#2A2A2A]">
          <span className="text-xs font-mono text-[#71717A]">
            {(page - 1) * pageSize + 1}–{Math.min(page * pageSize, total)} of {total.toLocaleString()}
          </span>
          <div className="flex items-center gap-2">
            <button
              onClick={() => onPageChange(page - 1)}
              disabled={page <= 1}
              className="btn-ghost disabled:opacity-30 disabled:cursor-not-allowed"
            >
              ← Prev
            </button>
            <span className="text-xs font-mono text-[#71717A]">
              {page} / {totalPages}
            </span>
            <button
              onClick={() => onPageChange(page + 1)}
              disabled={page >= totalPages}
              className="btn-ghost disabled:opacity-30 disabled:cursor-not-allowed"
            >
              Next →
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
