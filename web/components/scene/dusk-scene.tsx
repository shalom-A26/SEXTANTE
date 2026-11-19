"use client";

import { useEffect, useRef } from "react";
import * as THREE from "three";

import { sceneState } from "./state";

// Fullscreen dusk: sky gradient + setting sun (background quad), a waving field of
// grass points and the sextant drawn in 3D lines. Scroll (sceneState.progress)
// sets the sun and turns dusk into night; the pointer tilts the camera.

const SKY = `
uniform float uTime; uniform float uProgress; uniform vec2 uRes;
varying vec2 vUv;
float hash(vec2 p) { return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453); }
void main() {
  vec2 uv = vUv;
  float night = smoothstep(0.08, 0.6, uProgress);
  float horizon = 0.46 + 0.04 * night;
  vec3 sky = mix(vec3(0.725, 0.408, 0.486), vec3(0.18, 0.07, 0.07), night);       // --sky -> ground
  vec3 glow = mix(vec3(0.925, 0.753, 0.659), vec3(0.55, 0.25, 0.2), night);        // --horizon
  vec3 top = mix(vec3(0.42, 0.2, 0.26), vec3(0.1, 0.035, 0.035), night);
  float t = smoothstep(horizon, 1.0, uv.y);
  vec3 col = mix(glow, sky, smoothstep(0.0, 0.35, t));
  col = mix(col, top, smoothstep(0.35, 1.0, t));
  // Sun sinks below the horizon as you scroll.
  vec2 sunPos = vec2(0.5, horizon + 0.11 - 0.5 * uProgress);
  vec2 d = (uv - sunPos) * vec2(uRes.x / uRes.y, 1.0);
  float r = length(d);
  col += vec3(1.0, 0.82, 0.68) * smoothstep(0.075, 0.07, r) * step(horizon, uv.y) * (1.0 - night * 0.6);
  col += vec3(0.97, 0.64, 0.29) * 0.35 * exp(-r * 6.0) * (1.0 - night * 0.7);
  // Stars come out at night.
  vec2 g = floor(uv * uRes / 3.0);
  float star = step(0.9975, hash(g)) * smoothstep(horizon + 0.05, 1.0, uv.y);
  col += star * night * (0.6 + 0.4 * sin(uTime * 2.0 + hash(g) * 40.0));
  gl_FragColor = vec4(col, 1.0);
}`;

const GRASS_VERT = `
uniform float uTime; uniform float uProgress; uniform float uPixel;
attribute float aSeed;
varying float vDepth; varying float vSeed;
void main() {
  vec3 p = position;
  float wind = sin(p.x * 0.35 + uTime * 1.3 + aSeed * 6.0) * 0.18 + sin(p.z * 0.6 + uTime * 0.8) * 0.12;
  p.y += wind * (0.4 + aSeed);
  p.x += wind * 0.5;
  vec4 mv = modelViewMatrix * vec4(p, 1.0);
  gl_Position = projectionMatrix * mv;
  vDepth = clamp(-mv.z / 40.0, 0.0, 1.0);
  vSeed = aSeed;
  gl_PointSize = uPixel * (0.7 + aSeed * 1.6) * (9.0 / -mv.z);
}`;

const GRASS_FRAG = `
uniform float uProgress;
varying float vDepth; varying float vSeed;
void main() {
  vec2 c = gl_PointCoord - 0.5;
  if (dot(c, c) > 0.25) discard;
  float night = smoothstep(0.08, 0.6, uProgress);
  vec3 near = vec3(0.37, 0.14, 0.125);   // #5e2420
  vec3 far = vec3(0.85, 0.57, 0.49);     // #d9917e
  vec3 col = mix(near, far, vDepth);
  col = mix(col, col * 0.35, night);
  col += vec3(0.97, 0.64, 0.29) * step(0.985, vSeed) * (0.4 + night);  // a few fireflies
  gl_FragColor = vec4(col, 0.9 - vDepth * 0.4);
}`;

function sextant() {
  // Same drawing as the logo glyph: arc, two radii and the index arm.
  const pts: number[] = [];
  const seg = (a: THREE.Vector3, b: THREE.Vector3) => pts.push(a.x, a.y, a.z, b.x, b.y, b.z);
  const apex = new THREE.Vector3(0, 2.2, 0);
  const R = 3.2;
  const arc = (a: number) => new THREE.Vector3(Math.sin(a) * R, apex.y - Math.cos(a) * R, 0);
  const from = -Math.PI / 6;
  const to = Math.PI / 6;
  for (let i = 0; i < 48; i++) seg(arc(from + ((to - from) * i) / 48), arc(from + ((to - from) * (i + 1)) / 48));
  for (let i = 0; i <= 30; i++) {
    const a = from + ((to - from) * i) / 30;
    const len = i % 5 === 0 ? 0.28 : 0.14;
    seg(arc(a), new THREE.Vector3(Math.sin(a) * (R - len), apex.y - Math.cos(a) * (R - len), 0));
  }
  seg(apex, arc(from));
  seg(apex, arc(to));
  const geo = new THREE.BufferGeometry();
  geo.setAttribute("position", new THREE.Float32BufferAttribute(pts, 3));
  return geo;
}

export default function DuskScene() {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const host = ref.current!;
    const renderer = new THREE.WebGLRenderer({ antialias: true, powerPreference: "high-performance" });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 1.75));
    host.appendChild(renderer.domElement);

    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(50, 1, 0.1, 100);
    camera.position.set(0, 1.6, 10);

    const uniforms = {
      uTime: { value: 0 }, uProgress: { value: 0 }, uRes: { value: new THREE.Vector2() },
      uPixel: { value: renderer.getPixelRatio() },
    };

    // Background quad written straight in clip space, always behind everything.
    const sky = new THREE.Mesh(new THREE.PlaneGeometry(2, 2), new THREE.ShaderMaterial({
      uniforms, fragmentShader: SKY, depthWrite: false, depthTest: false,
      vertexShader: "varying vec2 vUv; void main() { vUv = uv; gl_Position = vec4(position.xy, 0.999, 1.0); }",
    }));
    sky.frustumCulled = false;
    sky.renderOrder = -1;
    scene.add(sky);

    const COUNT = window.innerWidth < 768 ? 9000 : 22000;
    const pos = new Float32Array(COUNT * 3);
    const seed = new Float32Array(COUNT);
    for (let i = 0; i < COUNT; i++) {
      const depth = Math.pow(Math.random(), 1.5);
      pos[i * 3] = (Math.random() - 0.5) * (20 + depth * 60);
      pos[i * 3 + 1] = -1.2 + Math.random() * 0.5;
      pos[i * 3 + 2] = 6 - depth * 40;
      seed[i] = Math.random();
    }
    const grassGeo = new THREE.BufferGeometry();
    grassGeo.setAttribute("position", new THREE.BufferAttribute(pos, 3));
    grassGeo.setAttribute("aSeed", new THREE.BufferAttribute(seed, 1));
    const grass = new THREE.Points(grassGeo, new THREE.ShaderMaterial({
      uniforms, vertexShader: GRASS_VERT, fragmentShader: GRASS_FRAG, transparent: true, depthWrite: false,
    }));
    scene.add(grass);

    const lineMat = new THREE.LineBasicMaterial({ color: 0xfbf1ec, transparent: true, opacity: 0.55 });
    const instrument = new THREE.LineSegments(sextant(), lineMat);
    instrument.position.set(0, 0.6, -2);
    scene.add(instrument);

    const resize = () => {
      const { clientWidth: w, clientHeight: h } = host;
      renderer.setSize(w, h, false);
      camera.aspect = w / h;
      camera.updateProjectionMatrix();
      uniforms.uRes.value.set(w, h);
    };
    resize();
    window.addEventListener("resize", resize);

    const pointer = { x: 0, y: 0 };
    const move = (e: PointerEvent) => {
      pointer.x = e.clientX / window.innerWidth - 0.5;
      pointer.y = e.clientY / window.innerHeight - 0.5;
    };
    window.addEventListener("pointermove", move);

    const start = performance.now();
    let frame = 0;
    const tick = () => {
      frame = requestAnimationFrame(tick);
      if (document.hidden) return;
      const t = (performance.now() - start) / 1000;
      const p = sceneState.progress;
      uniforms.uTime.value = t;
      uniforms.uProgress.value += (p - uniforms.uProgress.value) * 0.08;
      camera.position.x += (pointer.x * 1.2 - camera.position.x) * 0.04;
      camera.position.y += (1.6 - pointer.y * 0.6 - p * 0.8 - camera.position.y) * 0.04;
      camera.lookAt(0, 0.6, -6);
      // The index arm sweeps with the chapter, plus a slow drift.
      instrument.rotation.y = p * Math.PI * 2 + Math.sin(t * 0.3) * 0.15;
      instrument.rotation.z = Math.sin(t * 0.2) * 0.05;
      lineMat.opacity = 0.55 * (1 - Math.min(1, p * 1.6));
      renderer.render(scene, camera);
    };
    tick();

    return () => {
      cancelAnimationFrame(frame);
      window.removeEventListener("resize", resize);
      window.removeEventListener("pointermove", move);
      renderer.dispose();
      grassGeo.dispose();
      instrument.geometry.dispose();
      host.removeChild(renderer.domElement);
    };
  }, []);

  return <div ref={ref} className="scene-canvas" aria-hidden="true" />;
}
