"use client";

import { useState } from "react";
import useSWR from "swr";
import { swrFetcher } from "@/lib/api";
import { CallHistoryTable } from "@/components/calls/CallHistoryTable";
import { useRouter } from "next/navigation";
import type { CallRecord } from "@/lib/types";

const FILTER_OPTIONS = {
  Channel: { key: "channel", options: ["", "web", "phone", "whatsapp"] },
  Outcome:  { key: "outcome",  options: ["", "complete", "abandoned", "error", "active"] },
  Language: { key: "language", options: ["", "hi-IN", "en-IN"] },
};

type Filters = { channel: string; outcome: string; language: string };

function FilterPill({
  label,
  options,
  value,
  onChange,
}: {
  label: string;
  options: string[];
  value: string;
  onChange: (v: string) => void;
}) {
  return (
    <div className="flex items-center gap-0 rounded-lg overflow-hidden" style={{ border: "1px solid rgba(255,255,255,0.07)" }}>
      <span
        className="px-3 py-1.5 text-[10px] font-mono uppercase tracking-wider"
        style={{ background: "rgba(255,255,255,0.04)", color: "#4A5568", borderRight: "1px solid rgba(255,255,255,0.07)" }}
      >
        {label}
      </span>
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="input-dark border-0 rounded-none focus:ring-0 pr-2 text-[11px]"
        style={{ background: "transparent", paddingLeft: 8 }}
      >
        {options.map((o) => (
          <option key={o} value={o}>{o || "All"}</option>
        ))}
      </select>
    </div>
  );
}

export default function CallsPage() {
  const router = useRouter();
  const [page, setPage] = useState(1);
  const [filters, setFilters] = useState<Filters>({ channel: "", outcome: "", language: "" });

  const params: Record<string, string | number> = { page, page_size: 20 };
  if (filters.channel)  params.channel  = filters.channel;
  if (filters.outcome)  params.outcome  = filters.outcome;
  if (filters.language) params.language = filters.language;

  const qs = new URLSearchParams(
    Object.entries(params).map(([k, v]) => [k, String(v)])
  ).toString();

  const { data, isLoading, mutate } = useSWR(`/calls?${qs}`, swrFetcher, { refreshInterval: 15000 });

  const calls: CallRecord[] = (data as any)?.items ?? [];
  const total: number = (data as any)?.total ?? 0;

  const setFilter = (key: keyof Filters) => (v: string) => {
    setFilters((f) => ({ ...f, [key]: v }));
    setPage(1);
  };

  const activeFilterCount = Object.values(filters).filter(Boolean).length;

  return (
    <div className="flex flex-col h-screen p-6 gap-5" style={{ background: "#080B0F" }}>
      {/* Header */}
      <div className="flex items-center justify-between flex-shrink-0">
        <div>
          <h1
            className="font-bold text-xl tracking-wide"
            style={{ color: "#F0F4F8", fontFamily: "Inter, sans-serif" }}
          >
            Call History
          </h1>
          <p className="text-xs font-mono mt-0.5" style={{ color: "#4A5568" }}>
            {isLoading ? "Loading…" : `${total.toLocaleString()} total records`}
          </p>
        </div>

        <div className="flex items-center gap-2">
          {activeFilterCount > 0 && (
            <button
              onClick={() => { setFilters({ channel: "", outcome: "", language: "" }); setPage(1); }}
              className="btn-ghost text-[11px]"
            >
              Clear filters ({activeFilterCount})
            </button>
          )}
          <button onClick={() => mutate()} className="btn-ghost">
            <span style={{ color: "#00D4C8" }}>↻</span> Refresh
          </button>
        </div>
      </div>

      {/* Filters */}
      <div className="flex items-center gap-3 flex-wrap flex-shrink-0">
        {Object.entries(FILTER_OPTIONS).map(([label, { key, options }]) => (
          <FilterPill
            key={key}
            label={label}
            options={options}
            value={filters[key as keyof Filters]}
            onChange={setFilter(key as keyof Filters)}
          />
        ))}
      </div>

      {/* Table */}
      <div
        className="flex-1 min-h-0 rounded-xl overflow-hidden"
        style={{
          background: "rgba(10,14,22,0.7)",
          border: "1px solid rgba(255,255,255,0.06)",
        }}
      >
        {isLoading ? (
          <div className="overflow-auto h-full">
            <table className="w-full border-collapse" style={{ minWidth: 720 }}>
              <thead>
                <tr style={{ background: "rgba(12,16,23,0.9)" }}>
                  {["Channel", "Language", "Started", "Duration", "Outcome", "Completeness", "Version"].map((h) => (
                    <th
                      key={h}
                      className="text-left px-4 py-3 text-[10px] font-mono uppercase tracking-[0.1em]"
                      style={{ color: "#4A5568", borderBottom: "1px solid rgba(255,255,255,0.06)" }}
                    >
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {[...Array(8)].map((_, i) => (
                  <tr key={i} style={{ borderBottom: "1px solid rgba(255,255,255,0.03)" }}>
                    {[...Array(7)].map((_, j) => (
                      <td key={j} className="px-4 py-4">
                        <div
                          className="h-3 rounded"
                          style={{
                            width: `${40 + ((i + j) % 5) * 10}%`,
                            background: "linear-gradient(90deg, rgba(255,255,255,0.04) 25%, rgba(255,255,255,0.08) 50%, rgba(255,255,255,0.04) 75%)",
                            backgroundSize: "400% 100%",
                            animation: "shimmer 1.6s ease-in-out infinite",
                            animationDelay: `${(i + j) * 0.05}s`,
                          }}
                        />
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <CallHistoryTable
            calls={calls}
            total={total}
            page={page}
            onPageChange={setPage}
            onRowClick={(id) => router.push(`/calls/${id}`)}
          />
        )}
      </div>
    </div>
  );
}
