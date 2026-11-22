export function Panel({ title, note, children }: { title: string; note?: string; children: React.ReactNode }) {
  return (
    <section className="panel">
      <h3>{title}</h3>
      {note && <p className="muted">{note}</p>}
      {children}
    </section>
  );
}
