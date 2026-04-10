import { useCallback, useEffect, useRef, useState } from "react";

const STORAGE_KEY = "myday-noise";

function buildBrownNoise(ctx: AudioContext): AudioBufferSourceNode {
  const bufferSize = 2 * ctx.sampleRate;
  const buffer = ctx.createBuffer(1, bufferSize, ctx.sampleRate);
  const output = buffer.getChannelData(0);
  let lastOut = 0;
  for (let i = 0; i < bufferSize; i++) {
    const white = Math.random() * 2 - 1;
    output[i] = (lastOut + 0.02 * white) / 1.02;
    lastOut = output[i];
    output[i] *= 3.5;
  }
  const source = ctx.createBufferSource();
  source.buffer = buffer;
  source.loop = true;
  return source;
}

export function useBrownNoise() {
  const ctxRef = useRef<AudioContext | null>(null);
  const sourceRef = useRef<AudioBufferSourceNode | null>(null);
  const gainRef = useRef<GainNode | null>(null);
  const [active, setActive] = useState(false);

  const start = useCallback(() => {
    if (!ctxRef.current) {
      ctxRef.current = new (window.AudioContext || (window as any).webkitAudioContext)();
    }
    const ctx = ctxRef.current;
    gainRef.current = ctx.createGain();
    gainRef.current.gain.value = 0.25;
    gainRef.current.connect(ctx.destination);
    sourceRef.current = buildBrownNoise(ctx);
    sourceRef.current.connect(gainRef.current);
    sourceRef.current.start();
    setActive(true);
    try { localStorage.setItem(STORAGE_KEY, "1"); } catch (_) {}
  }, []);

  const stop = useCallback(() => {
    if (sourceRef.current) {
      try { sourceRef.current.stop(); } catch (_) {}
      sourceRef.current = null;
    }
    setActive(false);
    try { localStorage.setItem(STORAGE_KEY, "0"); } catch (_) {}
  }, []);

  const toggle = useCallback(() => {
    active ? stop() : start();
  }, [active, start, stop]);

  // Auto-resume saved preference on first user interaction
  useEffect(() => {
    const saved = localStorage.getItem(STORAGE_KEY);
    if (saved !== "1") return;
    const resume = () => { start(); document.removeEventListener("click", resume); };
    document.addEventListener("click", resume);
    return () => document.removeEventListener("click", resume);
  }, [start]);

  return { active, toggle };
}
