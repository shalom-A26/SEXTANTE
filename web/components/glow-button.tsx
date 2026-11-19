import Link from "next/link";

// Hook-style arrow (↪) used across the site.
export function HookArrow({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true" className={className} fill="none" stroke="currentColor" strokeWidth="1.6">
      <path d="M5 4v7a4 4 0 0 0 4 4h10" />
      <path d="M15 11l4 4-4 4" />
    </svg>
  );
}

type Props = {
  children: string;
  href?: string;
  size?: "sm" | "lg";
  solid?: boolean;
  external?: boolean;
  className?: string;
} & Omit<React.ButtonHTMLAttributes<HTMLButtonElement>, "children">;

/** Glass pill with a spinning gradient stroke; the label rolls up on hover. */
export function GlowButton({ children, href, size, solid, external, className, ...button }: Props) {
  const cls = ["glow-btn", size, solid && "solid", className].filter(Boolean).join(" ");
  const inner = (
    <>
      <span className="gb-text"><span>{children}</span><span aria-hidden="true">{children}</span></span>
      <HookArrow className="gb-icon" />
      <span className="gb-shadow" aria-hidden="true" />
    </>
  );
  if (href && external) return <a href={href} className={cls} target="_blank" rel="noopener noreferrer">{inner}</a>;
  if (href) return <Link href={href} className={cls}>{inner}</Link>;
  return <button className={cls} {...button}>{inner}</button>;
}
