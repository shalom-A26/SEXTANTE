"use client";

// Ambient dusk soundscape synthesised with Web Audio (no audio files):
// wind (filtered noise with a slow sweep) under a soft, detuned pad.
type Engine = { ctx: AudioContext; master: GainNode };

let engine: Engine | null = null;
const listeners = new Set<(on: boolean) => void>();
let on = false;

function build(): Engine {
  const ctx = new AudioContext();
  const master = ctx.createGain();
  master.gain.value = 0;
  master.connect(ctx.destination);

  // Wind: 4 s of looping noise through a band-pass whose centre drifts.
  const noise = ctx.createBuffer(1, ctx.sampleRate * 4, ctx.sampleRate);
  const data = noise.getChannelData(0);
  let last = 0;
  for (let i = 0; i < data.length; i++) {
    last = (last + 0.02 * (Math.random() * 2 - 1)) / 1.02; // brown-ish noise
    data[i] = last * 3.5;
  }
  const src = ctx.createBufferSource();
  src.buffer = noise;
  src.loop = true;
  const band = ctx.createBiquadFilter();
  band.type = "bandpass";
  band.frequency.value = 500;
  band.Q.value = 0.7;
  const sweep = ctx.createOscillator();
  const sweepDepth = ctx.createGain();
  sweep.frequency.value = 0.06;
  sweepDepth.gain.value = 320;
  sweep.connect(sweepDepth).connect(band.frequency);
  const windGain = ctx.createGain();
  windGain.gain.value = 0.55;
  src.connect(band).connect(windGain).connect(master);
  src.start();
  sweep.start();

  // Pad: A minor add9, each voice slightly detuned, through a warm low-pass.
  const low = ctx.createBiquadFilter();
  low.type = "lowpass";
  low.frequency.value = 900;
  const padGain = ctx.createGain();
  padGain.gain.value = 0.05;
  low.connect(padGain).connect(master);
  [110, 164.81, 220, 246.94, 329.63].forEach((f, i) => {
    for (const detune of [-7, 7]) {
      const osc = ctx.createOscillator();
      osc.type = i % 2 ? "sine" : "triangle";
      osc.frequency.value = f;
      osc.detune.value = detune;
      const g = ctx.createGain();
      g.gain.value = 0.18 / (i + 1);
      // Each voice breathes at its own slow rate.
      const lfo = ctx.createOscillator();
      const depth = ctx.createGain();
      lfo.frequency.value = 0.05 + i * 0.023;
      depth.gain.value = 0.08 / (i + 1);
      lfo.connect(depth).connect(g.gain);
      osc.connect(g).connect(low);
      osc.start();
      lfo.start();
    }
  });
  return { ctx, master };
}

export function soundOn() {
  return on;
}

export function setSound(next: boolean) {
  if (next && !engine) engine = build();
  on = next;
  if (engine) {
    const { ctx, master } = engine;
    if (next) void ctx.resume();
    master.gain.cancelScheduledValues(ctx.currentTime);
    master.gain.setTargetAtTime(next ? 0.5 : 0, ctx.currentTime, next ? 1.2 : 0.25);
  }
  listeners.forEach((fn) => fn(on));
}

export function onSoundChange(fn: (on: boolean) => void) {
  listeners.add(fn);
  return () => { listeners.delete(fn); };
}
