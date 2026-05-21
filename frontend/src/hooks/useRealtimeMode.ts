"use client";

import { useState, useEffect } from "react";

export const REALTIME_MODE_KEY = "vaani_realtime_mode";

export function isRealtimeMode(): boolean {
  if (typeof window === "undefined") return true;
  const stored = localStorage.getItem(REALTIME_MODE_KEY);
  if (stored !== null) return stored === "true";
  return true; // default: realtime on
}

export function setRealtimeMode(enabled: boolean): void {
  if (typeof window === "undefined") return;
  localStorage.setItem(REALTIME_MODE_KEY, String(enabled));
}

export function useRealtimeMode() {
  const [enabled, setEnabled] = useState(true);

  useEffect(() => {
    setEnabled(isRealtimeMode());
  }, []);

  const toggle = () => {
    const next = !enabled;
    setRealtimeMode(next);
    setEnabled(next);
  };

  return { enabled, toggle };
}
