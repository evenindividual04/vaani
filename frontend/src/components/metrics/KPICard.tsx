"use client";

import { useEffect, useRef } from "react";

interface KPICardProps {
  label: string;
  value: string | number;
  unit?: string;
  color?: string;
  trend?: "up" | "down" | "neutral";
  delta?: string;
  icon?: React.ReactNode;
}

function useCountUp(target: number, duration = 800) {
  const ref = useRef<HTMLSpanElement>(null);
  useEffect(() => {
    const el = ref.current;
    if (!el || isNaN(target)) return;
    const start = Date.now();
    const startVal = 0;
    const tick = () => {
      const progress = Math.min((Date.now() - start) / duration, 1);
      const eased = 1 - Math.pow(1 - progress, 3);
      el.textContent = String(Math.round(startVal + (target - startVal) * eased));
      if (progress < 1) requestAnimationFrame(tick);
    };
    requestAnimationFrame(tick);
  }, [target, duration]);
  return ref;
}

export function KPICard({ label, value, unit, color = "#F0F4F8", trend, delta, icon }: KPICardProps) {
  const numericValue = typeof value === "number" ? value : parseFloat(String(value));
  const isCountable = !isNaN(numericValue) && typeof value === "number";
  const countRef = useCountUp(isCountable ? numericValue : 0);

  const trendColor = trend === "up" ? "#00E676" : trend === "down" ? "#FF4545" : "#8B9BB4";
  const trendArrow = trend === "up" ? "↑" : trend === "down" ? "↓" : "→";

  return (
    <div className="rounded-lg p-5 animate-fade-in-up bg-[#111111] border border-[#2A2A2A] shadow-sm">
      {/* Header */}
      <div className="flex items-start justify-between mb-4">
        <span className="text-[10px] font-mono uppercase tracking-[0.12em] text-[#71717A]">
          {label}
        </span>
        {icon && (
          <div
            className="w-7 h-7 rounded-lg flex items-center justify-center"
            style={{ background: `${color}12`, color }}
          >
            {icon}
          </div>
        )}
      </div>

      {/* Value */}
      <div className="flex items-end gap-1.5">
        <div
          className="text-3xl font-bold font-mono leading-none tracking-tight"
          style={{ color }}
        >
          {isCountable ? (
            <span ref={countRef}>0</span>
          ) : (
            <span>{value}</span>
          )}
        </div>
        {unit && (
          <span className="text-xs font-mono pb-0.5 text-[#52525B]">
            {unit}
          </span>
        )}
      </div>

      {/* Trend */}
      {(trend || delta) && (
        <div className="flex items-center gap-1 mt-3">
          {trend && (
            <span className="text-xs font-mono font-bold" style={{ color: trendColor }}>
              {trendArrow}
            </span>
          )}
          {delta && (
            <span className="text-[10px] font-mono" style={{ color: trendColor }}>
              {delta}
            </span>
          )}
          <span className="text-[10px] font-mono text-[#52525B] ml-1">vs last hour</span>
        </div>
      )}
    </div>
  );
}
