"use client";

interface ProviderHealthCardProps {
  providers: Record<string, { status: string; consecutive_errors: number }>;
}

function statusColor(status: string): string {
  if (status === "healthy")     return "#00E676";
  if (status === "cooling_down") return "#F5A623";
  return "#FF4545";
}

function statusLabel(status: string): string {
  if (status === "healthy")      return "Healthy";
  if (status === "cooling_down") return "Cooling Down";
  return "Degraded";
}

function ProviderRow({ name, status, errors }: { name: string; status: string; errors: number }) {
  const color = statusColor(status);

  return (
    <div
      className="flex items-center gap-3 px-4 py-3 transition-all duration-150"
      style={{ borderBottom: "1px solid rgba(255,255,255,0.04)" }}
    >
      {/* Animated status dot */}
      <div className="relative flex-shrink-0">
        <div
          className="w-2 h-2 rounded-full"
          style={{ background: color, boxShadow: `0 0 6px ${color}80` }}
        />
        {status === "healthy" && (
          <div
            className="absolute inset-0 rounded-full"
            style={{
              background: color,
              animation: "ping-ring 2s cubic-bezier(0,0,0.2,1) infinite",
            }}
          />
        )}
      </div>

      {/* Provider name */}
      <div className="flex-1 min-w-0">
        <div className="text-xs font-mono" style={{ color: "#C8D4E0" }}>
          {name}
        </div>
        <div className="text-[9px] font-mono mt-0.5" style={{ color }}>
          {statusLabel(status)}
        </div>
      </div>

      {/* Error count */}
      {errors > 0 && (
        <div
          className="text-[9px] font-mono px-2 py-0.5 rounded"
          style={{
            background: "rgba(255,69,69,0.1)",
            color: "#FF4545",
            border: "1px solid rgba(255,69,69,0.2)",
          }}
        >
          {errors} err
        </div>
      )}

      {/* Status pill */}
      <div
        className="w-2 h-6 rounded-full flex-shrink-0"
        style={{
          background: `linear-gradient(180deg, ${color}, ${color}40)`,
          boxShadow: `0 0 6px ${color}40`,
        }}
      />
    </div>
  );
}

export function ProviderHealthCard({ providers }: ProviderHealthCardProps) {
  const entries = Object.entries(providers);
  const healthyCount = entries.filter(([, p]) => p.status === "healthy").length;

  return (
    <div
      className="rounded-xl overflow-hidden"
      style={{
        background: "rgba(12,16,23,0.7)",
        border: "1px solid rgba(255,255,255,0.07)",
      }}
    >
      {/* Header */}
      <div
        className="px-4 py-3 flex items-center justify-between"
        style={{ borderBottom: "1px solid rgba(255,255,255,0.06)" }}
      >
        <div>
          <div className="text-sm font-medium" style={{ color: "#C8D4E0" }}>
            Provider Health
          </div>
          <div className="text-[10px] font-mono mt-0.5" style={{ color: "#4A5568" }}>
            STT · LLM · TTS services
          </div>
        </div>
        <div
          className="text-xs font-mono px-2.5 py-1 rounded-lg"
          style={{
            background: healthyCount === entries.length ? "rgba(0,230,118,0.08)" : "rgba(255,69,69,0.08)",
            color:      healthyCount === entries.length ? "#00E676"              : "#FF4545",
            border: `1px solid ${healthyCount === entries.length ? "rgba(0,230,118,0.2)" : "rgba(255,69,69,0.2)"}`,
          }}
        >
          {healthyCount}/{entries.length} OK
        </div>
      </div>

      {/* Rows */}
      <div>
        {entries.length === 0 ? (
          <div
            className="px-4 py-6 text-center text-xs font-mono"
            style={{ color: "#2D3748" }}
          >
            No providers configured
          </div>
        ) : (
          entries.map(([name, p]) => (
            <ProviderRow
              key={name}
              name={name}
              status={p.status}
              errors={p.consecutive_errors}
            />
          ))
        )}
      </div>
    </div>
  );
}
