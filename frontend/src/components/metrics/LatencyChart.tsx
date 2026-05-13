"use client";

import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
} from "recharts";

interface LatencyDataPoint {
  label: string;
  stt?: number;
  llm?: number;
  tts?: number;
  total?: number;
}

interface LatencyChartProps {
  data?: LatencyDataPoint[];
}

const MOCK_DATA: LatencyDataPoint[] = Array.from({ length: 12 }, (_, i) => ({
  label: `T-${11 - i}`,
  stt:   Math.round(180 + Math.random() * 120),
  llm:   Math.round(350 + Math.random() * 400),
  tts:   Math.round(120 + Math.random() * 80),
})).map((d) => ({ ...d, total: (d.stt ?? 0) + (d.llm ?? 0) + (d.tts ?? 0) }));

const CustomTooltip = ({ active, payload, label }: any) => {
  if (!active || !payload?.length) return null;
  return (
    <div
      className="rounded-lg px-3 py-2.5 text-xs font-mono space-y-1"
      style={{
        background: "rgba(10,14,22,0.95)",
        border: "1px solid rgba(255,255,255,0.1)",
        backdropFilter: "blur(12px)",
      }}
    >
      <div className="mb-1.5" style={{ color: "#4A5568" }}>{label}</div>
      {payload.map((p: any) => (
        <div key={p.name} className="flex items-center gap-3">
          <div className="w-2 h-2 rounded-full" style={{ background: p.color }} />
          <span style={{ color: "#8B9BB4" }}>{p.name.toUpperCase()}</span>
          <span className="ml-auto font-bold" style={{ color: p.color }}>
            {p.value}ms
          </span>
        </div>
      ))}
    </div>
  );
};

export function LatencyChart({ data = MOCK_DATA }: LatencyChartProps) {
  return (
    <div
      className="rounded-xl p-5"
      style={{
        background: "rgba(12,16,23,0.7)",
        border: "1px solid rgba(255,255,255,0.07)",
      }}
    >
      <div className="flex items-center justify-between mb-4">
        <div>
          <div className="text-sm font-medium" style={{ color: "#C8D4E0" }}>
            Pipeline Latency
          </div>
          <div className="text-[10px] font-mono mt-0.5" style={{ color: "#4A5568" }}>
            STT · LLM · TTS per turn (ms)
          </div>
        </div>
        <div
          className="text-[9px] font-mono px-2 py-1 rounded"
          style={{ background: "rgba(0,212,200,0.08)", color: "#00D4C8", border: "1px solid rgba(0,212,200,0.15)" }}
        >
          LIVE
        </div>
      </div>

      <ResponsiveContainer width="100%" height={180}>
        <AreaChart data={data} margin={{ top: 4, right: 4, bottom: 0, left: -20 }}>
          <defs>
            <linearGradient id="sttGrad" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%"  stopColor="#4C9EFF" stopOpacity={0.25}/>
              <stop offset="95%" stopColor="#4C9EFF" stopOpacity={0}/>
            </linearGradient>
            <linearGradient id="llmGrad" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%"  stopColor="#00D4C8" stopOpacity={0.25}/>
              <stop offset="95%" stopColor="#00D4C8" stopOpacity={0}/>
            </linearGradient>
            <linearGradient id="ttsGrad" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%"  stopColor="#F5A623" stopOpacity={0.25}/>
              <stop offset="95%" stopColor="#F5A623" stopOpacity={0}/>
            </linearGradient>
          </defs>
          <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.04)" />
          <XAxis
            dataKey="label"
            tick={{ fontSize: 9, fill: "#2D3748", fontFamily: "JetBrains Mono" }}
            axisLine={false}
            tickLine={false}
          />
          <YAxis
            tick={{ fontSize: 9, fill: "#2D3748", fontFamily: "JetBrains Mono" }}
            axisLine={false}
            tickLine={false}
            tickFormatter={(v) => `${v}ms`}
          />
          <Tooltip content={<CustomTooltip />} />
          <Area type="monotone" dataKey="stt" name="stt" stroke="#4C9EFF" strokeWidth={1.5} fill="url(#sttGrad)" dot={false} />
          <Area type="monotone" dataKey="llm" name="llm" stroke="#00D4C8" strokeWidth={1.5} fill="url(#llmGrad)" dot={false} />
          <Area type="monotone" dataKey="tts" name="tts" stroke="#F5A623" strokeWidth={1.5} fill="url(#ttsGrad)" dot={false} />
        </AreaChart>
      </ResponsiveContainer>

      {/* Legend */}
      <div className="flex items-center gap-4 mt-3">
        {[{ label: "STT", color: "#4C9EFF" }, { label: "LLM", color: "#00D4C8" }, { label: "TTS", color: "#F5A623" }].map((l) => (
          <div key={l.label} className="flex items-center gap-1.5">
            <div className="w-6 h-0.5 rounded-full" style={{ background: l.color }} />
            <span className="text-[9px] font-mono" style={{ color: "#4A5568" }}>{l.label}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
