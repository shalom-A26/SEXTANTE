// Self-check for the guide's in-browser pipeline. Run: node scripts/check-guide.ts
import assert from "node:assert/strict";

import { analyze, BANDS, matchSkills, repairMojibake, salaryBand, tokenize } from "../components/guide/pipeline.ts";
import { RECAPTURE, ROWS, SAMPLE_CV } from "../components/guide/rows.ts";

assert.equal(repairMojibake(ROWS[0].title), "Técnico en Logística");
assert.ok(!/Ã|Â/.test(repairMojibake(ROWS[0].description)));
assert.equal(repairMojibake("Técnico"), "Técnico", "clean text must pass through");

// Longest match wins: "excel avanzado" beats "excel".
assert.deepEqual(matchSkills(tokenize("Excel avanzado")).map((h) => h.skill), ["Excel avanzado"]);
assert.deepEqual(matchSkills(tokenize("Excel básico")).map((h) => h.skill), ["utilizar hojas de cálculo"]);

assert.equal(RECAPTURE.url, ROWS[4].url, "the recapture shares its key with row 5");

const a = analyze(ROWS, SAMPLE_CV);
const dup = a.pairs.filter((p) => p.duplicate);
assert.deepEqual(dup.map((p) => [p.i, p.j]), [[1, 2]], `only rows 2 and 3 are duplicates: ${JSON.stringify(a.pairs.map((p) => [p.i, p.j, +p.cosine.toFixed(2), p.estimate]))}`);

for (const v of a.tfidf.vectors) assert.ok(Math.abs(Math.hypot(...v.values()) - 1) < 1e-9, "tf-idf rows are L2-normalized");

const again = analyze(ROWS, SAMPLE_CV);
assert.deepEqual(again.clusters.labels, a.clusters.labels, "k-means is deterministic");
assert.equal(a.clusters.labels[1], a.clusters.labels[2], "the duplicate pair shares a segment");

for (const p of a.logistic.probs) assert.ok(Math.abs(p.reduce((s, v) => s + v, 0) - 1) < 1e-9, "softmax sums to 1");
const predicted = a.logistic.classes[a.logistic.probs[2].indexOf(Math.max(...a.logistic.probs[2]))];
assert.equal(salaryBand(ROWS[2]), null, "row 3 has no salary");
assert.equal(BANDS[predicted], BANDS[salaryBand(ROWS[1])!], "row 3 is predicted in its twin's band");

const prSum = [...a.ranks.values()].reduce((s, v) => s + v, 0);
assert.ok(Math.abs(prSum - 1) < 1e-6, `pagerank sums to 1 (${prSum})`);
assert.ok(a.communities.modularity > 0, "louvain finds structure");

for (const m of a.matches) assert.ok(m.score >= 0 && m.score <= 100);
const bestRow = a.matches.indexOf(a.matches.reduce((x, y) => (y.score > x.score ? y : x)));
assert.ok(bestRow === 1 || bestRow === 2, "the data-analyst CV matches a data-analyst posting");

console.log("guide pipeline OK", {
  clusters: a.clusters.labels, silhouette: +a.clusters.silhouette.toFixed(3), modularity: +a.communities.modularity.toFixed(3),
  duplicate: dup.map((p) => ({ cos: +p.cosine.toFixed(3), est: p.estimate, jac: +p.jaccard.toFixed(3) })),
  bands: a.bands, matches: a.matches.map((m) => m.score),
});
