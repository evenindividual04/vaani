"use client";

import type { FNOLRecord } from "@/lib/types";
import { completenessColor, incidentTypeLabel } from "@/lib/utils";

// ── Completeness Bar ──────────────────────────────────────────────────────────

interface CompletenessBarProps {
  score: number;
  missingFields?: string[];
}

export function CompletenessBar({ score, missingFields = [] }: CompletenessBarProps) {
  const pct = Math.round(score * 100);
  const color = completenessColor(score);

  return (
    <div>
      <div className="flex items-center justify-between mb-2">
        <span className="text-[10px] font-mono tracking-[0.12em]" style={{ color: "#4A5568" }}>
          FNOL COMPLETENESS
        </span>
        <span
          className="text-sm font-mono font-bold"
          style={{ color }}
        >
          {pct}%
        </span>
      </div>

      {/* Track */}
      <div className="h-1.5 rounded-full overflow-hidden bg-[#2A2A2A]">
        <div
          className="h-full rounded-full transition-all duration-500"
          style={{ width: `${pct}%`, background: color }}
        />
      </div>

      {/* Missing fields */}
      {missingFields.length > 0 && (
        <div className="mt-2.5 flex flex-wrap gap-1.5">
          {missingFields.map((f) => (
            <span
              key={f}
              className="text-[9px] font-mono px-1.5 py-0.5 rounded uppercase tracking-wide bg-[#1C1C1C] text-[#A1A1AA] border border-[#2A2A2A]"
            >
              {f.replace(/_/g, " ")}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}

// ── FNOL Record Card ──────────────────────────────────────────────────────────

interface FNOLRecordCardProps {
  fnol: Partial<FNOLRecord>;
  completenessScore?: number;
  missingFields?: string[];
}

const SECTIONS = [
  {
    title: "Incident",
    fields: [
      { key: "policy_number",    label: "Policy #" },
      { key: "incident_type",   label: "Type" },
      { key: "incident_date",   label: "Date" },
      { key: "incident_location", label: "Location" },
    ],
  },
  {
    title: "Details",
    fields: [
      { key: "injuries_reported",   label: "Injuries" },
      { key: "vehicle_damage",      label: "Vehicle Dmg" },
      { key: "third_party_involved", label: "Third Party" },
    ],
  },
  {
    title: "Contact",
    fields: [
      { key: "callback_number", label: "Callback #" },
    ],
  },
];

function renderValue(key: string, value: unknown): string {
  if (value === null || value === undefined) return "—";
  if (typeof value === "boolean") return value ? "Yes" : "No";
  if (key === "incident_type") return incidentTypeLabel(String(value));
  return String(value);
}

function confidenceColor(conf: number): string {
  if (conf >= 0.85) return "#00E676";
  if (conf >= 0.6)  return "#F5A623";
  return "#FF4545";
}

export function FNOLRecordCard({ fnol, completenessScore = 0, missingFields = [] }: FNOLRecordCardProps) {
  return (
    <div className="rounded-lg overflow-hidden bg-[#111111] border border-[#2A2A2A] shadow-sm">
      <div className="px-4 py-3 border-b border-[#2A2A2A]">
        <CompletenessBar score={completenessScore} missingFields={missingFields} />
      </div>

      {/* Sections */}
      <div className="divide-y divide-[#2A2A2A]">
        {SECTIONS.map((section) => (
          <div key={section.title} className="px-4 py-3">
            <div className="text-[10px] font-medium text-[#52525B] mb-2 uppercase tracking-wide">
              {section.title}
            </div>
            <div className="space-y-1.5">
              {section.fields.map(({ key, label }) => {
                const value = (fnol as any)[key];
                const hasValue = value !== null && value !== undefined;
                const conf = (fnol.extraction_confidence ?? {})[key] ?? 0;

                return (
                  <div key={key} className="flex items-center gap-2">
                    <span className="text-[11px] font-mono w-24 flex-shrink-0 text-[#71717A]">
                      {label}
                    </span>
                    <span
                      className="flex-1 text-[12px] font-medium truncate"
                      style={{ color: hasValue ? "#FAFAFA" : "#3E3E3E" }}
                      title={hasValue ? String(value) : undefined}
                    >
                      {renderValue(key, value)}
                    </span>
                    {hasValue && conf > 0 && (
                      <div
                        className="flex-shrink-0 w-1.5 h-1.5 rounded-full"
                        style={{ background: confidenceColor(conf) }}
                        title={`${Math.round(conf * 100)}% confidence`}
                      />
                    )}
                  </div>
                );
              })}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
