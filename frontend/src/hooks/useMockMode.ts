"use client";

import { useState, useEffect } from "react";

export const MOCK_MODE_KEY = "vaani_mock_mode";

export function isMockMode(): boolean {
  if (typeof window === "undefined") return false;
  // Env var forcing true always wins (deploy-time override)
  if (process.env.NEXT_PUBLIC_USE_MOCK === "true") return true;
  // Then check explicit localStorage choice
  const stored = localStorage.getItem(MOCK_MODE_KEY);
  if (stored !== null) return stored === "true";
  return false;
}

export function setMockMode(enabled: boolean): void {
  if (typeof window === "undefined") return;
  localStorage.setItem(MOCK_MODE_KEY, String(enabled));
}

export function useMockMode() {
  const [enabled, setEnabled] = useState(false);

  useEffect(() => {
    setEnabled(isMockMode());
  }, []);

  const toggle = () => {
    const next = !enabled;
    setMockMode(next);
    setEnabled(next);
  };

  return { enabled, toggle };
}
