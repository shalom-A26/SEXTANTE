"use client";

import { useRef } from "react";

import { FINE_POINTER, gsap, MOTION_OK, SplitText, useGSAP } from "./gsap";

type Div = React.HTMLAttributes<HTMLDivElement>;

/** Children rise and fade in, one after another, when the block scrolls into view. */
export function Reveal({ children, stagger = 0.08, y = 32, delay = 0, ...props }: Div & {
  stagger?: number;
  y?: number;
  delay?: number;
}) {
  const ref = useRef<HTMLDivElement>(null);
  useGSAP(() => {
    gsap.matchMedia().add(MOTION_OK, () => {
      gsap.from(ref.current!.children, {
        y, autoAlpha: 0, filter: "blur(6px)", duration: 1.1, stagger, delay,
        scrollTrigger: { trigger: ref.current, start: "top 88%", once: true },
      });
    });
  }, { scope: ref });
  return <div ref={ref} {...props}>{children}</div>;
}

/** Heading whose words slide up out of a mask. */
export function SplitHeading({ as: Tag = "h2", children, className, delay = 0, onScroll = true }: {
  as?: "h1" | "h2" | "h3" | "p";
  children: React.ReactNode;
  className?: string;
  delay?: number;
  onScroll?: boolean;
}) {
  const ref = useRef<HTMLHeadingElement>(null);
  useGSAP(() => {
    gsap.matchMedia().add(MOTION_OK, () => {
      SplitText.create(ref.current, {
        type: "words", mask: "words", autoSplit: true,
        onSplit: (self) => gsap.from(self.words, {
          yPercent: 115, rotate: 3, duration: 1.2, stagger: 0.07, delay,
          scrollTrigger: onScroll ? { trigger: ref.current, start: "top 90%", once: true } : undefined,
        }),
      });
    });
  }, { scope: ref });
  return <Tag ref={ref} className={className}>{children}</Tag>;
}

/** A number that counts up to its value the first time it is seen. */
export function CountUp({ value, format = (v) => Math.round(v).toLocaleString("es-CO"), duration = 1.8 }: {
  value: number;
  format?: (value: number) => string;
  duration?: number;
}) {
  const ref = useRef<HTMLSpanElement>(null);
  useGSAP(() => {
    gsap.matchMedia().add(MOTION_OK, () => {
      const counter = { v: 0 };
      gsap.to(counter, {
        v: value, duration, ease: "power3.out",
        onUpdate: () => { if (ref.current) ref.current.textContent = format(counter.v); },
        scrollTrigger: { trigger: ref.current, start: "top 95%", once: true },
      });
    });
  }, { dependencies: [value], scope: ref });
  return <span ref={ref}>{format(value)}</span>;
}

/** Wrapper that pulls its child toward the pointer and springs back on leave. */
export function Magnetic({ children, strength = 0.35, className }: {
  children: React.ReactNode;
  strength?: number;
  className?: string;
}) {
  const ref = useRef<HTMLSpanElement>(null);
  useGSAP(() => {
    gsap.matchMedia().add(FINE_POINTER, () => {
      const el = ref.current!;
      const target = el.firstElementChild as HTMLElement;
      const x = gsap.quickTo(target, "x", { duration: 0.6, ease: "power3.out" });
      const y = gsap.quickTo(target, "y", { duration: 0.6, ease: "power3.out" });
      const move = (event: PointerEvent) => {
        const box = el.getBoundingClientRect();
        x((event.clientX - box.left - box.width / 2) * strength);
        y((event.clientY - box.top - box.height / 2) * strength);
      };
      const leave = () => {
        gsap.to(target, { x: 0, y: 0, duration: 1.1, ease: "elastic.out(1, 0.35)" });
      };
      el.addEventListener("pointermove", move);
      el.addEventListener("pointerleave", leave);
      return () => {
        el.removeEventListener("pointermove", move);
        el.removeEventListener("pointerleave", leave);
      };
    });
  }, { scope: ref });
  return <span ref={ref} className={`magnetic ${className ?? ""}`}>{children}</span>;
}
