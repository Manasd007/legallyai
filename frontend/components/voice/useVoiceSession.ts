"use client";

import { useCallback, useEffect, useRef, useState } from "react";

const VOICE_URL = process.env.NEXT_PUBLIC_VOICE_URL || "";

export const voiceEnabled = !!VOICE_URL;

export type CallResult = {
  summary: string;
  citations: string[];

  firstQuestion: string;
};

export type Turn = { role: "user" | "agent"; turn: number; final: string; partial: string };

export type Phase = "idle" | "connecting" | "live" | "summarizing";

export const turnText = (t: Turn) => [t.final, t.partial].filter(Boolean).join(" ");

const orderKey = (t: Turn) => t.turn * 2 + (t.role === "agent" ? 1 : 0);

export function useVoiceSession({ onComplete }: { onComplete: (r: CallResult) => void }) {
  const [phase, setPhase] = useState<Phase>("idle");
  const [status, setStatus] = useState("");
  const [turns, setTurns] = useState<Turn[]>([]);

  const [level, setLevel] = useState(0);

  const [agentSpeaking, setAgentSpeaking] = useState(false);

  const pcRef = useRef<RTCPeerConnection | null>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const micRef = useRef<MediaStream | null>(null);
  const audioElRef = useRef<HTMLAudioElement | null>(null);
  const audioCtxRef = useRef<AudioContext | null>(null);
  const rafRef = useRef<number | null>(null);
  const sessionRef = useRef("");
  const turnsRef = useRef<Turn[]>([]);
  turnsRef.current = turns;

  const teardown = useCallback(() => {
    if (rafRef.current !== null) cancelAnimationFrame(rafRef.current);
    rafRef.current = null;
    audioCtxRef.current?.close().catch(() => {});
    audioCtxRef.current = null;
    pcRef.current?.close();
    pcRef.current = null;
    micRef.current?.getTracks().forEach((t) => t.stop());
    micRef.current = null;
    wsRef.current?.close();
    wsRef.current = null;
    setLevel(0);
    setAgentSpeaking(false);
  }, []);

  useEffect(() => teardown, [teardown]);

  const upsert = useCallback((role: Turn["role"], turn: number, patch: Partial<Turn>) => {
    setTurns((prev) => {
      const i = prev.findIndex((t) => t.role === role && t.turn === turn);
      if (i === -1) {
        return [...prev, { role, turn, final: "", partial: "", ...patch }].sort(
          (a, b) => orderKey(a) - orderKey(b),
        );
      }
      return prev.map((t, j) => (j === i ? { ...t, ...patch } : t));
    });
  }, []);

  function startLevelMeter(stream: MediaStream) {
    try {
      const Ctx =
        window.AudioContext || (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
      const ctx = new Ctx();
      audioCtxRef.current = ctx;
      const source = ctx.createMediaStreamSource(stream);
      const analyser = ctx.createAnalyser();
      analyser.fftSize = 512;
      analyser.smoothingTimeConstant = 0.75;
      source.connect(analyser);
      const buf = new Uint8Array(analyser.frequencyBinCount);

      const tick = () => {
        analyser.getByteTimeDomainData(buf);
        let sum = 0;
        for (let i = 0; i < buf.length; i += 1) {
          const v = (buf[i] - 128) / 128;
          sum += v * v;
        }

        const rms = Math.sqrt(sum / buf.length);
        setLevel(Math.min(1, rms * 4));
        rafRef.current = requestAnimationFrame(tick);
      };
      rafRef.current = requestAnimationFrame(tick);
    } catch {
    }
  }

  function connectEvents(sessionId: string) {
    const ws = new WebSocket(`${VOICE_URL.replace(/^http/, "ws")}/ws/events/${sessionId}`);
    wsRef.current = ws;
    ws.onmessage = (msg) => {
      let ev: { type?: string; turn?: number; text?: string };
      try {
        ev = JSON.parse(msg.data);
      } catch {
        return;
      }
      switch (ev.type) {
        case "transcript.user.partial":
          upsert("user", ev.turn ?? 0, { partial: ev.text || "" });
          break;
        case "transcript.user.final":

          upsert("user", ev.turn ?? 0, { final: ev.text || "", partial: "" });
          break;
        case "transcript.agent":

          upsert("agent", ev.turn ?? 0, { final: ev.text || "" });
          setAgentSpeaking(true);
          break;
        case "status":
          setStatus(ev.text || "");
          break;
      }
    };
  }

  function waitForIce(pc: RTCPeerConnection) {
    if (pc.iceGatheringState === "complete") return Promise.resolve();
    return new Promise<void>((resolve) => {
      const check = () => {
        if (pc.iceGatheringState === "complete") {
          pc.removeEventListener("icegatheringstatechange", check);
          resolve();
        }
      };
      pc.addEventListener("icegatheringstatechange", check);
      setTimeout(resolve, 2000);
    });
  }

  const start = useCallback(
    async (audioEl: HTMLAudioElement | null) => {
      audioElRef.current = audioEl;
      const sessionId = crypto.randomUUID();
      sessionRef.current = sessionId;
      setTurns([]);
      setPhase("connecting");
      setStatus("Connecting…");

      try {
        micRef.current = await navigator.mediaDevices.getUserMedia({
          audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true },
        });
      } catch {
        setPhase("idle");
        setStatus("Microphone access denied");
        return;
      }
      startLevelMeter(micRef.current);
      connectEvents(sessionId);

      const pc = new RTCPeerConnection();
      pcRef.current = pc;
      micRef.current.getAudioTracks().forEach((t) => pc.addTrack(t, micRef.current!));
      pc.addTransceiver("audio", { direction: "recvonly" });
      pc.ontrack = (ev) => {
        if (audioElRef.current) audioElRef.current.srcObject = ev.streams[0];
      };
      pc.onconnectionstatechange = () => {
        if (["failed", "disconnected", "closed"].includes(pc.connectionState)) {
          setPhase((p) => (p === "live" ? "idle" : p));
          setStatus("Connection lost");
        }
      };

      await pc.setLocalDescription(await pc.createOffer());
      await waitForIce(pc);

      try {
        const resp = await fetch(`${VOICE_URL}/api/offer?session_id=${sessionId}`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ sdp: pc.localDescription!.sdp, type: pc.localDescription!.type }),
        });
        if (!resp.ok) throw new Error(String(resp.status));
        await pc.setRemoteDescription(await resp.json());
      } catch {
        teardown();
        setPhase("idle");
        setStatus("Couldn't reach the voice service");
        return;
      }

      setPhase("live");
      setStatus("Listening");
    },
    [teardown, upsert],
  );

  const stop = useCallback(async () => {
    setPhase("summarizing");
    setStatus("Writing your summary…");

    const firstQuestion = turnsRef.current.find((t) => t.role === "user" && t.final)?.final || "";

    let result: CallResult | null = null;
    try {
      const resp = await fetch(`${VOICE_URL}/api/summary/${sessionRef.current}`, { method: "POST" });
      if (resp.ok) {
        const data = await resp.json();
        if (data.summary) {
          result = { summary: data.summary, citations: data.citations || [], firstQuestion };
        }
      }
    } catch {
    }

    teardown();
    setTurns([]);
    setPhase("idle");
    setStatus("");
    if (result) onComplete(result);
  }, [onComplete, teardown]);

  const cancel = useCallback(() => {
    teardown();
    setTurns([]);
    setPhase("idle");
    setStatus("");
  }, [teardown]);

  return { phase, status, turns, level, agentSpeaking, start, stop, cancel };
}
