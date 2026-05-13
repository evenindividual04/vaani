// WebSocket hook for /ws/live monitor
"use client";

import { useEffect, useRef, useCallback } from "react";
import { useCallStore } from "@/store/callStore";
import { getAuthToken } from "@/lib/api";
import type { WSMessage } from "@/lib/types";

const WS_URL = process.env.NEXT_PUBLIC_WS_URL || "ws://localhost:8000";
const RECONNECT_DELAY_MS = 3000;

export function useCallWebSocket() {
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const handleWSMessage = useCallStore((s) => s.handleWSMessage);

  const connect = useCallback(() => {
    const token = getAuthToken();
    if (!token) return;

    const ws = new WebSocket(`${WS_URL}/ws/live?token=${token}`);
    wsRef.current = ws;

    ws.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data) as WSMessage;
        if (msg.type !== "ping") {
          handleWSMessage(msg);
        }
      } catch {
        // ignore parse errors
      }
    };

    ws.onclose = () => {
      reconnectTimer.current = setTimeout(connect, RECONNECT_DELAY_MS);
    };

    ws.onerror = () => {
      ws.close();
    };
  }, [handleWSMessage]);

  useEffect(() => {
    connect();
    return () => {
      if (reconnectTimer.current) clearTimeout(reconnectTimer.current);
      wsRef.current?.close();
    };
  }, [connect]);

  const isConnected = wsRef.current?.readyState === WebSocket.OPEN;
  return { isConnected };
}
