export function Glyph() {
  // A sextant: arc, two radii and the index arm.
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true" className="glyph">
      <path d="M4 18 A 11 11 0 0 1 20 18" fill="none" stroke="currentColor" strokeWidth="1.6" />
      <path d="M12 4 L4 18 M12 4 L20 18 M12 4 L15 18" fill="none" stroke="currentColor" strokeWidth="1.4" />
      <circle cx="12" cy="4" r="1.8" fill="currentColor" />
    </svg>
  );
}
