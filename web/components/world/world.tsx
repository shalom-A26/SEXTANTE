"use client";

import { useEffect, useRef } from "react";
import * as THREE from "three";
import { Reflector } from "three/examples/jsm/objects/Reflector.js";

import { buildShapes, prng } from "./shapes";
import { worldState } from "./state";

// A procedural dusk valley: hills of swaying grass around a reflecting lake,
// a ring of standing stones, drifting petals and a particle swarm that morphs
// into one shape per chapter while the camera travels with the scroll.

const LAKE = new THREE.Vector2(0, -20);
const LAKE_R = new THREE.Vector2(19, 12);
const SUN_DIR = new THREE.Vector3(0.15, 0.1, -1).normalize();

// Value noise + fbm (CPU side, for the terrain).
const rnd = prng(7);
const PERM = Array.from({ length: 512 }, () => rnd());
function vnoise(x: number, y: number) {
  const xi = Math.floor(x);
  const yi = Math.floor(y);
  const xf = x - xi;
  const yf = y - yi;
  const h = (i: number, j: number) => PERM[(((i * 73) ^ (j * 151)) >>> 0) % 512];
  const s = (t: number) => t * t * (3 - 2 * t);
  const a = h(xi, yi), b = h(xi + 1, yi), c = h(xi, yi + 1), d = h(xi + 1, yi + 1);
  return a + (b - a) * s(xf) + (c - a) * s(yf) + (a - b - c + d) * s(xf) * s(yf);
}
function fbm(x: number, y: number) {
  let v = 0, amp = 0.5, f = 1;
  for (let o = 0; o < 4; o++) { v += vnoise(x * f, y * f) * amp; f *= 2.03; amp *= 0.5; }
  return v;
}
function lakeDist(x: number, z: number) {
  return Math.hypot((x - LAKE.x) / LAKE_R.x, (z - LAKE.y) / LAKE_R.y);
}
export function heightAt(x: number, z: number) {
  const base = 0.25 + fbm(x * 0.035 + 10, z * 0.035) * 2.4 + Math.max(0, Math.hypot(x, z + 20) - 45) * 0.22;
  const d = lakeDist(x, z);
  const shore = THREE.MathUtils.smoothstep(d, 0.82, 1.25);
  return THREE.MathUtils.lerp(-1.6, base, shore);
}

// Camera, look-at target and swarm position per chapter (world units).
// cam.y is the height above the ground under the camera.
const KEYS = [
  { cam: [0, 3.4, 2], look: [0, 4.2, -24], swarm: [0, 9.5, -27] },
  { cam: [-14, 2.6, -4], look: [-1, 6.5, -22], swarm: [8, 8.5, -22] },
  { cam: [6, 6, -6], look: [-2, 6, -34], swarm: [-2, 10.5, -38] },
  { cam: [17, 2.2, -14], look: [1, 5.5, -27], swarm: [-9, 8, -28] },
  { cam: [0, 1.4, -1], look: [0, 5.2, -24], swarm: [0, 8, -20] },
];
const curve = (k: "cam" | "look" | "swarm") =>
  new THREE.CatmullRomCurve3(KEYS.map((key) => new THREE.Vector3(...(key[k] as [number, number, number]))), false, "centripetal");

const SKY_FRAG = `
uniform float uTime; uniform vec3 uSun;
varying vec3 vDir;
float h(vec2 p){ return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453); }
float n(vec2 p){ vec2 i=floor(p), f=fract(p); f=f*f*(3.-2.*f);
  return mix(mix(h(i),h(i+vec2(1,0)),f.x), mix(h(i+vec2(0,1)),h(i+vec2(1,1)),f.x), f.y); }
float fbm(vec2 p){ float v=0., a=.5; for(int i=0;i<5;i++){ v+=n(p)*a; p*=2.02; a*=.5; } return v; }
void main(){
  vec3 d = normalize(vDir);
  float y = d.y;
  vec3 top = vec3(0.56, 0.29, 0.40);      // dusk mauve
  vec3 mid = vec3(0.80, 0.47, 0.52);      // --sky, warmed
  vec3 hor = vec3(0.95, 0.66, 0.58);      // --horizon, deepened
  vec3 col = mix(hor, mid, smoothstep(0.0, 0.22, y));
  col = mix(col, top, smoothstep(0.22, 0.75, y));
  float s = max(dot(d, uSun), 0.);
  col += vec3(1.0, 0.62, 0.32) * pow(s, 12.) * 0.55 + vec3(1.0, 0.9, 0.8) * smoothstep(0.9993, 0.9997, s);
  // Soft pink clouds, slowly drifting, thinning toward the horizon.
  vec2 uv = d.xz / max(y + 0.18, 0.05);
  float c = fbm(uv * 0.55 + vec2(uTime * 0.008, 0.));
  c = smoothstep(0.5, 0.85, c) * smoothstep(0.02, 0.25, y);
  col = mix(col, vec3(0.98, 0.74, 0.74), c * 0.55);
  gl_FragColor = vec4(col, 1.);
}`;

const GRASS_VERT = `
uniform float uTime; uniform vec2 uPointer;
attribute float aSeed;
varying float vH; varying float vSeed; varying float vFog;
void main(){
  vec3 p = position;
  float t = uv.y;
  p.x *= (1.0 - t) * (1.0 - t * 0.2);
  vec4 world = modelMatrix * instanceMatrix * vec4(p, 1.0);
  float gust = sin(world.x * 0.18 + uTime * 1.4) * 0.5 + sin(world.z * 0.27 + uTime * 0.9 + aSeed * 3.) * 0.5;
  world.x += (gust * 0.35 + uPointer.x * 0.25) * t * t;
  world.z += (gust * 0.2) * t * t;
  vec4 mv = viewMatrix * world;
  gl_Position = projectionMatrix * mv;
  vH = t; vSeed = aSeed; vFog = smoothstep(30., 140., -mv.z);
}`;

const GRASS_FRAG = `
uniform vec3 uFog;
varying float vH; varying float vSeed; varying float vFog;
void main(){
  vec3 base = vec3(0.27, 0.08, 0.10);
  vec3 tip = mix(vec3(0.74, 0.33, 0.27), vec3(0.93, 0.55, 0.40), vSeed);
  vec3 col = mix(base, tip, pow(vH, 1.3));
  col = mix(col, uFog, vFog * 0.85);
  gl_FragColor = vec4(col, 1.0);
}`;

const SWARM_VERT = `
uniform float uMorph; uniform float uTime; uniform float uPixel;
attribute vec3 aS0; attribute vec3 aS1; attribute vec3 aS2; attribute vec3 aS3; attribute vec3 aS4;
attribute float aSeed; attribute vec3 aColor;
varying vec3 vColor; varying float vFade;
float w(float k){ return clamp(1.0 - abs(uMorph - k), 0.0, 1.0); }
void main(){
  vec3 p = aS0 * w(0.) + aS1 * w(1.) + aS2 * w(2.) + aS3 * w(3.) + aS4 * w(4.);
  float travel = sin(fract(uMorph) * 3.14159);
  vec3 swirl = vec3(sin(uTime * 0.7 + aSeed * 40.), cos(uTime * 0.6 + aSeed * 27.), sin(uTime * 0.5 + aSeed * 13.));
  p += swirl * (0.08 + travel * 2.4 * aSeed);
  vec4 mv = modelViewMatrix * vec4(p, 1.0);
  gl_Position = projectionMatrix * mv;
  gl_PointSize = uPixel * (0.7 + aSeed * 1.1) * (110.0 / -mv.z);
  vColor = aColor; vFade = smoothstep(120., 40., -mv.z);
}`;

const SWARM_FRAG = `
varying vec3 vColor; varying float vFade;
void main(){
  vec2 c = gl_PointCoord - 0.5;
  float d = length(c);
  if (d > 0.5) discard;
  vec3 col = vColor * (1.05 - d * 0.5);
  gl_FragColor = vec4(col, vFade);
}`;

const PETAL_VERT = `
uniform float uTime;
attribute vec3 aBase; attribute float aSeed;
varying float vSeed; varying vec2 vUv;
void main(){
  vUv = uv;
  float t = uTime * (0.25 + aSeed * 0.35);
  vec3 c = aBase;
  c.y = mod(aBase.y - t * 1.5, 26.0) - 2.0;
  c.x += sin(t + aSeed * 30.) * 3.0 + t * 1.2;
  c.x = mod(c.x + 60., 120.) - 60.;
  c.z += cos(t * 0.8 + aSeed * 20.) * 2.0;
  float a = t * 2. + aSeed * 10.;
  vec3 p = position;
  p.xy = mat2(cos(a), -sin(a), sin(a), cos(a)) * p.xy;
  p.yz = mat2(cos(a * .7), -sin(a * .7), sin(a * .7), cos(a * .7)) * p.yz;
  gl_Position = projectionMatrix * viewMatrix * vec4(c + p, 1.0);
  vSeed = aSeed;
}`;

export default function World() {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const host = ref.current!;
    const small = window.innerWidth < 768;
    const renderer = new THREE.WebGLRenderer({ antialias: !small, powerPreference: "high-performance" });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, small ? 1.25 : 1.5));
    renderer.outputColorSpace = THREE.SRGBColorSpace;
    host.appendChild(renderer.domElement);

    const scene = new THREE.Scene();
    const fogColor = new THREE.Color(0.88, 0.55, 0.52);
    scene.fog = new THREE.Fog(fogColor, 55, 230);
    const camera = new THREE.PerspectiveCamera(55, 1, 0.1, 600);

    const uniforms = {
      uTime: { value: 0 }, uMorph: { value: 0 }, uPixel: { value: renderer.getPixelRatio() },
      uPointer: { value: new THREE.Vector2() }, uSun: { value: SUN_DIR }, uFog: { value: fogColor },
    };

    scene.add(new THREE.HemisphereLight(0xffd3bc, 0x4a1a1e, 1.5));
    const sun = new THREE.DirectionalLight(0xffb27a, 2.2);
    sun.position.copy(SUN_DIR).multiplyScalar(100).setY(40);
    scene.add(sun);

    // Sky dome.
    const sky = new THREE.Mesh(new THREE.SphereGeometry(500, 32, 16), new THREE.ShaderMaterial({
      uniforms, side: THREE.BackSide, depthWrite: false, fog: false, fragmentShader: SKY_FRAG,
      vertexShader: "varying vec3 vDir; void main(){ vDir = position; gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); }",
    }));
    scene.add(sky);

    // Terrain with vertex colours: wine hills, warm sand at the shore.
    const SEG = small ? 140 : 220;
    const ground = new THREE.PlaneGeometry(320, 320, SEG, SEG);
    ground.rotateX(-Math.PI / 2);
    const gp = ground.attributes.position as THREE.BufferAttribute;
    const colors = new Float32Array(gp.count * 3);
    const hill = new THREE.Color(0x5a2026), sand = new THREE.Color(0xc98a78), deep = new THREE.Color(0x3a1418), c = new THREE.Color();
    for (let i = 0; i < gp.count; i++) {
      const x = gp.getX(i), z = gp.getZ(i);
      const y = heightAt(x, z);
      gp.setY(i, y);
      const d = lakeDist(x, z);
      c.copy(deep).lerp(sand, THREE.MathUtils.smoothstep(d, 0.8, 0.95)).lerp(hill, THREE.MathUtils.smoothstep(d, 1.0, 1.2));
      colors.set([c.r, c.g, c.b], i * 3);
    }
    ground.setAttribute("color", new THREE.BufferAttribute(colors, 3));
    ground.computeVertexNormals();
    scene.add(new THREE.Mesh(ground, new THREE.MeshLambertMaterial({ vertexColors: true })));

    // Lake: a planar mirror tinted with the dusk.
    const water = new Reflector(new THREE.CircleGeometry(1, 64), {
      color: 0xb7909a, textureWidth: Math.round(window.innerWidth * 0.5), textureHeight: Math.round(window.innerHeight * 0.5),
    });
    water.rotation.x = -Math.PI / 2;
    water.scale.set(LAKE_R.x * 1.25, LAKE_R.y * 1.25, 1);
    water.position.set(LAKE.x, 0, LAKE.y);
    scene.add(water);

    // Standing stones ringing the valley.
    const r = prng(42);
    const STONES = 90;
    const stones = new THREE.InstancedMesh(new THREE.DodecahedronGeometry(1, 0),
      new THREE.MeshStandardMaterial({ color: 0x7d4752, roughness: 1, flatShading: true }), STONES);
    const m = new THREE.Matrix4(), q = new THREE.Quaternion(), s = new THREE.Vector3(), pos = new THREE.Vector3();
    for (let i = 0; i < STONES; i++) {
      const a = r() * Math.PI * 2;
      const rad = 36 + r() * 34;
      const x = LAKE.x + Math.cos(a) * rad * 1.3, z = LAKE.y + Math.sin(a) * rad;
      if (z > 4 && Math.abs(x) < 30) continue; // keep the foreground open
      pos.set(x, heightAt(x, z) - 0.6, z);
      q.setFromEuler(new THREE.Euler((r() - 0.5) * 0.3, r() * Math.PI, (r() - 0.5) * 0.25));
      s.set(1.6 + r() * 2.6, 3 + r() * 7, 1.4 + r() * 2.2);
      stones.setMatrixAt(i, m.compose(pos, q, s));
    }
    scene.add(stones);

    // Grass: instanced blades on dry land.
    const BLADES = small ? 22000 : 70000;
    const blade = new THREE.PlaneGeometry(0.07, 1, 1, 4);
    blade.translate(0, 0.5, 0);
    const grassMat = new THREE.ShaderMaterial({ uniforms, vertexShader: GRASS_VERT, fragmentShader: GRASS_FRAG, side: THREE.DoubleSide });
    const grass = new THREE.InstancedMesh(blade, grassMat, BLADES);
    const seeds = new Float32Array(BLADES);
    let placed = 0;
    while (placed < BLADES) {
      const rad = Math.pow(r(), 0.7) * 90;
      const a = r() * Math.PI * 2;
      const x = Math.cos(a) * rad * 1.2, z = -14 + Math.sin(a) * rad;
      if (lakeDist(x, z) < 1.08) continue;
      pos.set(x, heightAt(x, z) - 0.05, z);
      q.setFromEuler(new THREE.Euler((r() - 0.5) * 0.4, r() * Math.PI, (r() - 0.5) * 0.4));
      const h = 0.35 + r() * 0.8;
      s.set(0.8 + r() * 0.8, h, 1);
      grass.setMatrixAt(placed, m.compose(pos, q, s));
      seeds[placed++] = r();
    }
    blade.setAttribute("aSeed", new THREE.InstancedBufferAttribute(seeds, 1));
    grass.frustumCulled = false;
    scene.add(grass);

    // Petals drifting through the valley.
    const PETALS = small ? 120 : 260;
    const petalGeo = new THREE.InstancedBufferGeometry();
    const petalShape = new THREE.PlaneGeometry(0.16, 0.1);
    petalGeo.setIndex(petalShape.index);
    petalGeo.setAttribute("position", petalShape.attributes.position);
    petalGeo.setAttribute("uv", petalShape.attributes.uv);
    const base = new Float32Array(PETALS * 3), pseed = new Float32Array(PETALS);
    for (let i = 0; i < PETALS; i++) {
      base.set([(r() - 0.5) * 120, r() * 26, -60 + r() * 75], i * 3);
      pseed[i] = r();
    }
    petalGeo.setAttribute("aBase", new THREE.InstancedBufferAttribute(base, 3));
    petalGeo.setAttribute("aSeed", new THREE.InstancedBufferAttribute(pseed, 1));
    petalGeo.instanceCount = PETALS;
    const petals = new THREE.Mesh(petalGeo, new THREE.ShaderMaterial({
      uniforms, side: THREE.DoubleSide,
      vertexShader: PETAL_VERT, fragmentShader: "varying float vSeed; varying vec2 vUv; void main(){ vec2 c = vUv - 0.5; if (dot(c * vec2(1.0, 1.7), c * vec2(1.0, 1.7)) > 0.25) discard; gl_FragColor = vec4(mix(vec3(0.85,0.42,0.42), vec3(0.98,0.72,0.5), vSeed), 1.0); }",
    }));
    petals.frustumCulled = false;
    scene.add(petals);

    // The swarm.
    const N = small ? 4500 : 9000;
    const shapes = buildShapes(N);
    const swarmGeo = new THREE.BufferGeometry();
    shapes.forEach((shape, i) => swarmGeo.setAttribute(`aS${i}`, new THREE.BufferAttribute(shape, 3)));
    swarmGeo.setAttribute("position", new THREE.BufferAttribute(shapes[0], 3));
    const sseed = new Float32Array(N), scol = new Float32Array(N * 3);
    const palette = [0xf7a24b, 0xffd3a6, 0xfbf1ec, 0xf27c8c, 0xe0761b, 0xffffff].map((h) => new THREE.Color(h));
    for (let i = 0; i < N; i++) {
      sseed[i] = r();
      const col = palette[Math.floor(Math.pow(r(), 1.3) * palette.length)];
      scol.set([col.r, col.g, col.b], i * 3);
    }
    swarmGeo.setAttribute("aSeed", new THREE.BufferAttribute(sseed, 1));
    swarmGeo.setAttribute("aColor", new THREE.BufferAttribute(scol, 3));
    const swarm = new THREE.Points(swarmGeo, new THREE.ShaderMaterial({
      uniforms, vertexShader: SWARM_VERT, fragmentShader: SWARM_FRAG, transparent: true,
    }));
    swarm.frustumCulled = false;
    scene.add(swarm);

    const camCurve = curve("cam"), lookCurve = curve("look"), swarmCurve = curve("swarm");
    const look = new THREE.Vector3();

    const resize = () => {
      const { clientWidth: w, clientHeight: h } = host;
      renderer.setSize(w, h, false);
      camera.aspect = w / h;
      camera.fov = w / h < 1 ? 70 : 55;
      camera.updateProjectionMatrix();
    };
    resize();
    const ro = new ResizeObserver(resize);
    ro.observe(host);

    const pointer = new THREE.Vector2();
    const move = (e: PointerEvent) => pointer.set(e.clientX / window.innerWidth - 0.5, e.clientY / window.innerHeight - 0.5);
    window.addEventListener("pointermove", move);

    // Pause when the section is off screen or the tab is hidden.
    let visible = true;
    const io = new IntersectionObserver(([entry]) => { visible = entry.isIntersecting; });
    io.observe(host);

    const start = performance.now();
    let p = 0;
    let last = performance.now();
    let frame = 0;
    let first = true;
    const tick = () => {
      frame = requestAnimationFrame(tick);
      if (!visible || document.hidden) return;
      const now = performance.now();
      const t = (now - start) / 1000;
      // Frame-rate independent easing toward the scroll position.
      const k = 1 - Math.exp(-Math.min(0.25, (now - last) / 1000) * 3.5);
      last = now;
      p += (worldState.progress - p) * k;
      // Hold on each chapter, travel in between.
      const seg = Math.min(Math.floor(p), KEYS.length - 2);
      const f = THREE.MathUtils.smoothstep(p - seg, 0.18, 0.82);
      const u = (seg + f) / (KEYS.length - 1);
      uniforms.uTime.value = t;
      uniforms.uMorph.value = seg + f;
      uniforms.uPointer.value.lerp(pointer, k);
      camCurve.getPoint(u, camera.position);
      camera.position.y += Math.max(0, heightAt(camera.position.x, camera.position.z));
      camera.position.x += uniforms.uPointer.value.x * 1.6;
      camera.position.y -= uniforms.uPointer.value.y * 0.8;
      lookCurve.getPoint(u, look);
      camera.lookAt(look);
      swarmCurve.getPoint(u, swarm.position);
      swarm.position.y += Math.sin(t * 0.8) * 0.25;
      swarm.rotation.y = Math.sin(t * 0.25) * 0.35 + (seg + f) * 0.6;
      renderer.render(scene, camera);
      if (first) { first = false; worldState.ready = true; window.dispatchEvent(new Event("world-ready")); }
    };
    tick();

    return () => {
      cancelAnimationFrame(frame);
      ro.disconnect();
      io.disconnect();
      window.removeEventListener("pointermove", move);
      scene.traverse((o) => {
        const mesh = o as THREE.Mesh;
        mesh.geometry?.dispose();
        const mat = mesh.material as THREE.Material | undefined;
        mat?.dispose?.();
      });
      water.dispose();
      renderer.dispose();
      host.removeChild(renderer.domElement);
    };
  }, []);

  return <div ref={ref} className="world-canvas" aria-hidden="true" />;
}
