"""Zusätzliche Auswertungen für die Hausarbeit (Testset). Schreibt results/zusatzanalysen.md.

  - Projektausgaben (A_projekt) gegen Bedingung A: Einfluss des Modellwechsels
  - Laufzeit: Median und Maximum je Bedingung
  - Makro-Genauigkeit nach Lage des Schriftfelds
  - Art der falschen IDs: andere Nummer (NLS < 0,3) oder Variante der richtigen (NLS >= 0,3)
  - Titel ohne Ausgabe in A: Lage des Schriftfelds und Ergebnis in B
  - Determinismus: Testlauf gegen Entwicklungslauf auf den 8 Entwicklungsplänen
Aufruf:  python 07_zusatzanalysen.py   (vorher 06_import_projekt.py)
"""
from __future__ import annotations

import importlib.util
import json
import random
import statistics

import common
import config as C

spec = importlib.util.spec_from_file_location("ev", C.ROOT / "03_evaluate.py")
ev = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ev)

M = "qwen3-vl-4b-instruct"
RUNS = {"A'": "A_projekt__qwen2.5vl-3b", "A": f"A_baseline__{M}", "B": f"B_structured__{M}",
        "C": f"C_twostage__{M}", "D": f"D_fullpage__{M}"}
docs, gt = common.load_docs("test"), common.load_gt()
test_ids = {d["doc_id"] for d in docs}
rows = {k: ev.evaluate_run(common.run_dir(v), docs, gt)[0] for k, v in RUNS.items()}
corr = {k: {(r["doc_id"], r["field"]): r["correct"] for r in v} for k, v in rows.items()}
ids = sorted(test_ids)
out = ["# Zusatzanalysen (Testset, n = %d Pläne)" % len(ids), ""]


def macro(c, sample):
    return sum(sum(c[(d, f)] for d in sample) / len(sample) for f in C.FIELDS) / 4


def compare(a, b):
    rng = random.Random(C.SPLIT_SEED)
    diffs = sorted(macro(corr[b], s) - macro(corr[a], s)
                   for s in ([rng.choice(ids) for _ in ids] for _ in range(C.BOOTSTRAP_ITERS)))
    lo, hi = diffs[int(0.025 * len(diffs))], diffs[int(0.975 * len(diffs)) - 1]
    cells = []
    for f in C.FIELDS:
        only_a = sum(corr[a][(d, f)] and not corr[b][(d, f)] for d in ids)
        only_b = sum(corr[b][(d, f)] and not corr[a][(d, f)] for d in ids)
        cells.append(f"{f} {only_a}/{only_b}")
    return (f"| {a} -> {b} | {100 * (macro(corr[b], ids) - macro(corr[a], ids)):+.1f} "
            f"| [{100 * lo:+.1f}; {100 * hi:+.1f}] | {', '.join(cells)} |")


out += ["## Paarweise Vergleiche (Makro-Differenz in Pp., 95%-Bootstrap-KI, Pläne nur erste/nur zweite richtig)",
        "| Vergleich | Diff | KI | je Feld |", "|---|---|---|---|"]
out += [compare(a, b) for a, b in [("A'", "A"), ("A", "B"), ("B", "C"), ("C", "D"), ("A'", "B"), ("A'", "C")]]

out += ["", "## Laufzeit je Plan in s", "| Bedingung | Mittel | Median | Maximum |", "|---|---|---|---|"]
for k, v in RUNS.items():
    preds = ev.load_predictions(common.run_dir(v))
    s = [preds[d]["seconds"] for d in ids if preds[d].get("seconds") is not None]
    if s:
        out.append(f"| {k} | {statistics.mean(s):.1f} | {statistics.median(s):.1f} | {max(s):.0f} |")

out += ["", "## Makro-Genauigkeit nach Lage des Schriftfelds in %",
        "| Bedingung | unten rechts | anderswo/ohne |", "|---|---|---|"]
for k, rs in rows.items():
    br = [r["correct"] for r in rs if r["layout"] == "br"]
    other = [r["correct"] for r in rs if r["layout"] != "br"]
    out.append(f"| {k} | {100 * sum(br) / len(br):.1f} (n={len(br) // 4}) "
               f"| {100 * sum(other) / len(other):.1f} (n={len(other) // 4}) |")

out += ["", "## Falsche IDs: andere Nummer (NLS < 0,3) / Variante der richtigen (NLS >= 0,3)"]
for k, rs in rows.items():
    wv = [r for r in rs if r["field"] == "ID" and r["category"] == "WV"]
    other = sum(1 for r in wv if r["sim"] < 0.3)
    near = sum(1 for r in wv if r["sim"] >= 0.8)
    out.append(f"- {k}: {len(wv)} falsch, davon {other} andere Nummer, {len(wv) - other} Variante "
               f"(davon {near} mit NLS >= 0,8)")

a_fn = [r for r in rows["A"] if r["field"] == "Title" and r["category"] == "FN"]
b_t = {r["doc_id"]: r for r in rows["B"] if r["field"] == "Title"}
a_t = {r["doc_id"]: r for r in rows["A"] if r["field"] == "Title"}
gain = [d for d in b_t if b_t[d]["correct"] and not a_t[d]["correct"]]
out += ["", "## Titel",
        f"- A ohne Titel: {len(a_fn)} Pläne, davon {sum(r['layout'] != 'br' for r in a_fn)} mit "
        f"Schriftfeld nicht unten rechts; in B danach: "
        + ", ".join(f"{c} {sum(b_t[r['doc_id']]['category'] == c for r in a_fn)}" for c in ("TP", "WV", "FN")),
        f"- Nur B richtig: {len(gain)} Pläne, davon {sum(b_t[d]['layout'] == 'br' for d in gain)} unten rechts; "
        f"Kategorie in A: " + ", ".join(sorted({a_t[d]['category'] for d in gain})),
        "- B auf Plänen mit Schriftfeld nicht unten rechts: "
        + ", ".join(f"{c} {sum(1 for d in b_t if b_t[d]['layout'] != 'br' and b_t[d]['category'] == c)}"
                    for c in ("TP", "WV", "FN"))]

out += ["", "## Determinismus (Testlauf vs. Entwicklungslauf, 8 Entwicklungspläne)"]
for k, dev in [("A", f"A_baseline__{M}__dev1"), ("B", f"B_structured__{M}__dev2"), ("C", f"C_twostage__{M}__dev2")]:
    t, d = ev.load_predictions(common.run_dir(RUNS[k])), ev.load_predictions(common.run_dir(dev))
    same = sum(t[x]["pred"] == d[x]["pred"] for x in d if x in t)
    sha = lambda r: [p["sha256"] for p in json.loads((common.run_dir(r) / "config.json").read_text())["prompts"].values()]  # noqa: E731
    out.append(f"- {k}: {same}/{len(d)} identische Ausgaben (gleiche Prompt-Prüfsumme: {sha(RUNS[k]) == sha(dev)})")

text = "\n".join(out) + "\n"
print(text)
(C.RESULTS_DIR / "zusatzanalysen.md").write_text(text, "utf-8")
print("Gespeichert: results/zusatzanalysen.md")
