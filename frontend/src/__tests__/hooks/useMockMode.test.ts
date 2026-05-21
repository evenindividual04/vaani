import { describe, it, expect, beforeEach, vi } from "vitest";
import { isMockMode, setMockMode, MOCK_MODE_KEY } from "@/hooks/useMockMode";

describe("isMockMode", () => {
  it("returns false by default when nothing is set", () => {
    expect(isMockMode()).toBe(false);
  });

  it("returns true when localStorage key is 'true'", () => {
    localStorage.setItem(MOCK_MODE_KEY, "true");
    expect(isMockMode()).toBe(true);
  });

  it("returns false when localStorage key is 'false'", () => {
    localStorage.setItem(MOCK_MODE_KEY, "false");
    expect(isMockMode()).toBe(false);
  });

  it("env var NEXT_PUBLIC_USE_MOCK=true overrides localStorage false", () => {
    vi.stubEnv("NEXT_PUBLIC_USE_MOCK", "true");
    localStorage.setItem(MOCK_MODE_KEY, "false");
    expect(isMockMode()).toBe(true);
    vi.unstubAllEnvs();
  });

  it("localStorage takes precedence over env var when explicitly set", () => {
    vi.stubEnv("NEXT_PUBLIC_USE_MOCK", "false");
    localStorage.setItem(MOCK_MODE_KEY, "true");
    expect(isMockMode()).toBe(true);
    vi.unstubAllEnvs();
  });
});

describe("setMockMode", () => {
  it("persists true to localStorage", () => {
    setMockMode(true);
    expect(localStorage.getItem(MOCK_MODE_KEY)).toBe("true");
  });

  it("persists false to localStorage", () => {
    setMockMode(false);
    expect(localStorage.getItem(MOCK_MODE_KEY)).toBe("false");
  });

  it("isMockMode reflects setMockMode changes", () => {
    setMockMode(true);
    expect(isMockMode()).toBe(true);
    setMockMode(false);
    expect(isMockMode()).toBe(false);
  });
});
