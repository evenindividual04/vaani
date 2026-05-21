"use client";

import { useState, useEffect } from "react";
import { useMockMode } from "@/hooks/useMockMode";
import { useRealtimeMode } from "@/hooks/useRealtimeMode";

const LLM_PROVIDERS = ["auto", "groq", "gemini"] as const;
type LLMProvider = (typeof LLM_PROVIDERS)[number];

async function setLLMProvider(provider: LLMProvider, token: string | null) {
  if (!token) return;
  await fetch(`${process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"}/config/llm_provider`, {
    method: "PUT",
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
    body: JSON.stringify({ provider }),
  });
}

export function DevToolbar() {
  const [mounted, setMounted] = useState(false);
  const { enabled: mockOn, toggle: toggleMock } = useMockMode();
  const { enabled: realtimeOn, toggle: toggleRealtime } = useRealtimeMode();
  const [llmProvider, setLlmProvider] = useState<LLMProvider>("auto");
  const [open, setOpen] = useState(false);

  useEffect(() => { setMounted(true); }, []);
  if (!mounted) return null;

  const handleLLM = async (p: LLMProvider) => {
    setLlmProvider(p);
    const token = typeof window !== "undefined" ? localStorage.getItem("vaani_token") : null;
    await setLLMProvider(p, token);
  };

  return (
    <div className="fixed bottom-4 right-4 z-50 flex flex-col items-end gap-2">
      {open && (
        <div className="bg-[#1A1A1A] border border-[#333] rounded-lg p-3 flex flex-col gap-3 min-w-[200px] shadow-xl text-xs">
          <div className="text-[#888] font-mono uppercase tracking-wider text-[10px]">Dev Tools</div>

          <label className="flex items-center justify-between gap-3 cursor-pointer">
            <span className="text-[#CCC]">Mock API</span>
            <button
              onClick={toggleMock}
              className={`relative w-9 h-5 rounded-full transition-colors ${mockOn ? "bg-amber-500" : "bg-[#333]"}`}
            >
              <span className={`absolute top-0.5 left-0.5 w-4 h-4 bg-white rounded-full transition-transform ${mockOn ? "translate-x-4" : ""}`} />
            </button>
          </label>

          <label className="flex items-center justify-between gap-3 cursor-pointer">
            <span className="text-[#CCC]">Realtime WS</span>
            <button
              onClick={toggleRealtime}
              className={`relative w-9 h-5 rounded-full transition-colors ${realtimeOn ? "bg-green-500" : "bg-[#333]"}`}
            >
              <span className={`absolute top-0.5 left-0.5 w-4 h-4 bg-white rounded-full transition-transform ${realtimeOn ? "translate-x-4" : ""}`} />
            </button>
          </label>

          <div className="flex flex-col gap-1">
            <span className="text-[#888]">LLM Provider</span>
            <div className="flex gap-1">
              {LLM_PROVIDERS.map((p) => (
                <button
                  key={p}
                  onClick={() => handleLLM(p)}
                  className={`flex-1 py-1 rounded text-[10px] font-mono uppercase transition-colors ${llmProvider === p ? "bg-blue-600 text-white" : "bg-[#2A2A2A] text-[#888] hover:bg-[#333]"}`}
                >
                  {p}
                </button>
              ))}
            </div>
          </div>

          {mockOn && (
            <div className="text-amber-400 text-[10px] font-mono">⚠ Mock data active</div>
          )}
        </div>
      )}

      <button
        onClick={() => setOpen((o) => !o)}
        className="w-8 h-8 bg-[#1A1A1A] border border-[#333] rounded-full flex items-center justify-center text-[#888] hover:text-white hover:border-[#555] transition-colors shadow-lg font-mono text-xs"
        title="Dev Tools"
      >
        ⚙
      </button>
    </div>
  );
}
