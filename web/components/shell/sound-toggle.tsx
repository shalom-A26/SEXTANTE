"use client";

import { useEffect, useState } from "react";

import { onSoundChange, setSound, soundOn } from "@/lib/ambient";

export function SoundToggle() {
  const [on, setOn] = useState(false);
  useEffect(() => {
    setOn(soundOn());
    return onSoundChange(setOn);
  }, []);
  return (
    <button type="button" className={`sound-btn mono${on ? " sound-on" : ""}`} onClick={() => setSound(!on)}
      aria-pressed={on} aria-label={on ? "Silenciar sonido ambiente" : "Activar sonido ambiente"}>
      <span className="sound-bars" aria-hidden="true"><i /><i /><i /></span>
      {on ? "Sonido" : "Silencio"}
    </button>
  );
}
