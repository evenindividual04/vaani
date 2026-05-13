// Web Audio API waveform visualizer hook
"use client";

import { useEffect, useRef, useCallback } from "react";

interface WaveformOptions {
  fftSize?: number;
  color?: string;
  backgroundColor?: string;
}

export function useWaveform(canvasRef: React.RefObject<HTMLCanvasElement>, options: WaveformOptions = {}) {
  const {
    fftSize = 256,
    color = "#14B8A6",
    backgroundColor = "#141414",
  } = options;

  const analyserRef = useRef<AnalyserNode | null>(null);
  const animFrameRef = useRef<number | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const audioCtxRef = useRef<AudioContext | null>(null);

  const draw = useCallback(() => {
    const canvas = canvasRef.current;
    const analyser = analyserRef.current;
    if (!canvas || !analyser) return;

    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const bufferLength = analyser.frequencyBinCount;
    const dataArray = new Uint8Array(bufferLength);
    analyser.getByteTimeDomainData(dataArray);

    const W = canvas.width;
    const H = canvas.height;
    ctx.fillStyle = backgroundColor;
    ctx.fillRect(0, 0, W, H);

    ctx.lineWidth = 1.5;
    ctx.strokeStyle = color;
    ctx.shadowColor = color;
    ctx.shadowBlur = 4;
    ctx.beginPath();

    const sliceWidth = W / bufferLength;
    let x = 0;
    for (let i = 0; i < bufferLength; i++) {
      const v = dataArray[i] / 128.0;
      const y = (v * H) / 2;
      if (i === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
      x += sliceWidth;
    }
    ctx.lineTo(W, H / 2);
    ctx.stroke();

    animFrameRef.current = requestAnimationFrame(draw);
  }, [canvasRef, color, backgroundColor]);

  const start = useCallback(async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      streamRef.current = stream;
      const audioCtx = new AudioContext();
      audioCtxRef.current = audioCtx;
      const source = audioCtx.createMediaStreamSource(stream);
      const analyser = audioCtx.createAnalyser();
      analyser.fftSize = fftSize;
      source.connect(analyser);
      analyserRef.current = analyser;
      draw();
      return stream;
    } catch {
      return null;
    }
  }, [fftSize, draw]);

  const stop = useCallback(() => {
    if (animFrameRef.current) cancelAnimationFrame(animFrameRef.current);
    streamRef.current?.getTracks().forEach((t) => t.stop());
    audioCtxRef.current?.close();
    analyserRef.current = null;
  }, []);

  useEffect(() => () => stop(), [stop]);

  return { start, stop };
}

// Decode base64 WAV and play via Web Audio API
export function useAudioPlayer() {
  const audioCtxRef = useRef<AudioContext | null>(null);
  const queueRef = useRef<AudioBuffer[]>([]);
  const playingRef = useRef(false);

  function getCtx() {
    if (!audioCtxRef.current || audioCtxRef.current.state === "closed") {
      audioCtxRef.current = new AudioContext();
    }
    return audioCtxRef.current;
  }

  async function enqueue(base64Wav: string) {
    const ctx = getCtx();
    const raw = atob(base64Wav);
    const bytes = new Uint8Array(raw.length);
    for (let i = 0; i < raw.length; i++) bytes[i] = raw.charCodeAt(i);
    const buffer = await ctx.decodeAudioData(bytes.buffer);
    queueRef.current.push(buffer);
    if (!playingRef.current) playNext();
  }

  function playNext() {
    const ctx = getCtx();
    const buffer = queueRef.current.shift();
    if (!buffer) { playingRef.current = false; return; }
    playingRef.current = true;
    const source = ctx.createBufferSource();
    source.buffer = buffer;
    source.connect(ctx.destination);
    source.onended = playNext;
    source.start();
  }

  return { enqueue };
}
