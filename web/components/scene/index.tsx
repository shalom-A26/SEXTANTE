"use client";

import dynamic from "next/dynamic";
import { useEffect, useState } from "react";
import { createPortal } from "react-dom";

import { DuskField } from "@/components/field";

const DuskScene = dynamic(() => import("./dusk-scene"), { ssr: false });

function webglOk() {
  try {
    return !!document.createElement("canvas").getContext("webgl2");
  } catch {
    return false;
  }
}

/** Fixed background: WebGL dusk when possible, the static SVG field otherwise. */
export function Scene() {
  const [live, setLive] = useState<boolean | null>(null);
  useEffect(() => {
    setLive(webglOk() && !window.matchMedia("(prefers-reduced-motion: reduce)").matches);
  }, []);
  if (live === null) return null;
  // Portaled to <body>: the page transition transforms its wrapper, which would
  // otherwise turn this fixed layer into one as tall as the page.
  return createPortal(
    <div className="scene" aria-hidden="true">
      {live ? <DuskScene /> : <DuskField />}
      <div className="scene-veil" />
    </div>,
    document.body,
  );
}
