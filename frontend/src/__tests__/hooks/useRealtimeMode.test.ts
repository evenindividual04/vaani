import { describe, it, expect } from "vitest";
import { isRealtimeMode, setRealtimeMode, REALTIME_MODE_KEY } from "@/hooks/useRealtimeMode";

describe("isRealtimeMode", () => {
  it("returns true by default (realtime on by default)", () => {
    expect(isRealtimeMode()).toBe(true);
  });

  it("returns false when localStorage key is 'false'", () => {
    localStorage.setItem(REALTIME_MODE_KEY, "false");
    expect(isRealtimeMode()).toBe(false);
  });

  it("returns true when localStorage key is 'true'", () => {
    localStorage.setItem(REALTIME_MODE_KEY, "true");
    expect(isRealtimeMode()).toBe(true);
  });
});

describe("setRealtimeMode", () => {
  it("persists false to localStorage", () => {
    setRealtimeMode(false);
    expect(localStorage.getItem(REALTIME_MODE_KEY)).toBe("false");
    expect(isRealtimeMode()).toBe(false);
  });

  it("persists true to localStorage", () => {
    setRealtimeMode(false);
    setRealtimeMode(true);
    expect(isRealtimeMode()).toBe(true);
  });
});
