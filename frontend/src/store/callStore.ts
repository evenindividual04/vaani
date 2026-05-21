// Zustand store for live call state
"use client";

import { create } from "zustand";
import type { CallRecord, ConversationTurn, FNOLRecord, TurnMetrics, WSMessage } from "@/lib/types";

interface LiveCall {
  call_id: string;
  channel: string;
  language: string;
  started_at: string;
  turns: ConversationTurn[];
  fnol: Partial<FNOLRecord>;
  completeness_score: number;
  missing_fields: string[];
  metrics: TurnMetrics[];
  fsm_state: string;
  outcome?: string;
}

interface CallStore {
  // Live calls (indexed by call_id)
  liveCalls: Record<string, LiveCall>;
  // History list (paginated, from API)
  callHistory: CallRecord[];
  historyTotal: number;
  historyPage: number;
  // Currently viewed call
  selectedCallId: string | null;

  // Actions
  handleWSMessage: (msg: WSMessage) => void;
  setCallHistory: (calls: CallRecord[], total: number, page: number) => void;
  selectCall: (callId: string | null) => void;
  clearLiveCalls: () => void;
}

export const useCallStore = create<CallStore>((set, get) => ({
  liveCalls: {
    "mock_live_1": {
      call_id: "mock_live_1",
      channel: "phone",
      language: "en-US",
      started_at: new Date(Date.now() - 120000).toISOString(),
      turns: [
        { turn_index: 0, speaker: "agent", text: "Hello, this is Vaani from National Insurance. How can I help you today?", language: "en", timestamp_ms: Date.now() - 110000, fsm_state: "GREETING" as any },
        { turn_index: 1, speaker: "user", text: "Hi, I just had a car accident and need to file a claim.", language: "en", timestamp_ms: Date.now() - 100000, fsm_state: "GREETING" as any },
        { turn_index: 2, speaker: "agent", text: "I'm so sorry to hear that. Are you safe and do you need any emergency services?", language: "en", timestamp_ms: Date.now() - 90000, fsm_state: "COLLECT_INFO" as any },
        { turn_index: 3, speaker: "user", text: "Yes, I'm safe. No ambulance needed.", language: "en", timestamp_ms: Date.now() - 80000, fsm_state: "COLLECT_INFO" as any },
      ],
      fnol: { policy_number: "Pol-12345", location: "Downtown Seattle" },
      completeness_score: 0.35,
      missing_fields: ["vehicle_details", "date_of_loss", "description"],
      metrics: [
        { turn_index: 0, stt_ms: 120, llm_ms: 450, llm_ttft_ms: 180, tts_ms: 220, total_ms: 790, stt_provider: "sarvam", llm_provider: "groq", tts_provider: "sarvam", fallback_triggered: false },
        { turn_index: 2, stt_ms: 110, llm_ms: 500, llm_ttft_ms: 190, tts_ms: 240, total_ms: 850, stt_provider: "sarvam", llm_provider: "groq", tts_provider: "sarvam", fallback_triggered: false },
      ],
      fsm_state: "COLLECT_INFO",
    },
    "mock_live_2": {
      call_id: "mock_live_2",
      channel: "web",
      language: "hi-IN",
      started_at: new Date(Date.now() - 45000).toISOString(),
      turns: [
        { turn_index: 0, speaker: "agent", text: "नमस्ते, वाणी में आपका स्वागत है।", language: "hi", timestamp_ms: Date.now() - 40000, fsm_state: "GREETING" as any },
      ],
      fnol: {},
      completeness_score: 0.0,
      missing_fields: ["policy_number", "location", "vehicle_details", "date_of_loss", "description"],
      metrics: [],
      fsm_state: "GREETING",
    }
  },
  callHistory: [],
  historyTotal: 0,
  historyPage: 1,
  selectedCallId: "mock_live_1",

  handleWSMessage: (msg: WSMessage) => {
    set((state) => {
      switch (msg.type) {
        case "call_started": {
          const newCall: LiveCall = {
            call_id: msg.call_id,
            channel: msg.channel,
            language: msg.language,
            started_at: msg.started_at,
            turns: [],
            fnol: {},
            completeness_score: 0,
            missing_fields: [],
            metrics: [],
            fsm_state: "GREETING",
          };
          return {
            liveCalls: { ...state.liveCalls, [msg.call_id]: newCall },
          };
        }

        case "transcript_turn": {
          const call = state.liveCalls[msg.call_id];
          if (!call) return state;
          const newTurn: ConversationTurn = {
            turn_index: msg.turn_index,
            speaker: msg.speaker as "user" | "agent",
            text: msg.text,
            language: msg.language,
            timestamp_ms: msg.timestamp_ms,
            fsm_state: msg.fsm_state,
          };
          return {
            liveCalls: {
              ...state.liveCalls,
              [msg.call_id]: {
                ...call,
                turns: [...call.turns, newTurn],
              },
            },
          };
        }

        case "fnol_update": {
          const call = state.liveCalls[msg.call_id];
          if (!call) return state;
          return {
            liveCalls: {
              ...state.liveCalls,
              [msg.call_id]: {
                ...call,
                fnol: { ...call.fnol, ...(msg.fields as Partial<FNOLRecord>) },
                completeness_score: msg.completeness_score,
                missing_fields: msg.missing_fields,
              },
            },
          };
        }

        case "pipeline_metrics": {
          const call = state.liveCalls[msg.call_id];
          if (!call) return state;
          const metric: TurnMetrics = {
            turn_index: msg.turn_index,
            stt_ms: msg.stt_ms,
            llm_ms: msg.llm_ms,
            llm_ttft_ms: msg.llm_ttft_ms,
            tts_ms: msg.tts_ms,
            total_ms: msg.total_ms,
            stt_provider: msg.stt_provider,
            llm_provider: msg.llm_provider,
            tts_provider: msg.tts_provider,
            fallback_triggered: msg.fallback_triggered,
          };
          return {
            liveCalls: {
              ...state.liveCalls,
              [msg.call_id]: {
                ...call,
                metrics: [...call.metrics, metric],
              },
            },
          };
        }

        case "fsm_transition": {
          const call = state.liveCalls[msg.call_id];
          if (!call) return state;
          return {
            liveCalls: {
              ...state.liveCalls,
              [msg.call_id]: { ...call, fsm_state: msg.to_state },
            },
          };
        }

        case "call_ended": {
          const call = state.liveCalls[msg.call_id];
          if (!call) return state;
          return {
            liveCalls: {
              ...state.liveCalls,
              [msg.call_id]: { ...call, outcome: msg.outcome },
            },
          };
        }

        default:
          return state;
      }
    });
  },

  setCallHistory: (calls, total, page) =>
    set({ callHistory: calls, historyTotal: total, historyPage: page }),

  selectCall: (callId) => set({ selectedCallId: callId }),

  clearLiveCalls: () => set({ liveCalls: {} }),
}));
