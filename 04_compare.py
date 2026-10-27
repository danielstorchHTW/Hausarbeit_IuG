"""Gepaarter statistischer Vergleich zweier Läufe auf denselben Plänen.

  python 04_compare.py A_baseline__qwen3-vl-4b-instruct B_structured__qwen3-vl-4b-instruct

Tests:
  - Exakter McNemar-Test je Feld (richtig/falsch), Holm-Korrektur über die 4 Felder
  - Wilcoxon-Vorzeichen-Rang-Test auf der Titel-Ähnlichkeit (NLS)
  - Paired Bootstrap: 95%-Konfidenzintervall der Differenz der Makro-Genauigkeit
"""
from __future__ import annotations

import argparse
import importlib.util
import random
from math import comb
from pathlib import Path

import common
import config as C

spec = importlib.util.spec_from_file_location("ev", C.ROOT / "03_evaluate.py")
ev = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ev)


def mcnemar_exact(b: int, c: int) -> float:
    """Zweiseitiger exakter McNemar-Test (Binomialtest auf den diskordanten Paaren)."""
    n = b + c
    if n == 0:
        return 1.0
    k = min(b, c)
    return min(1.0, 2 * sum(comb(n, i) for i in range(k + 1)) / 2 ** n)


def holm(pvals: list) -> list:
    order = sorted(range(len(pvals)), key=lambda i: pvals[i])
    adj, running = [0.0] * len(pvals), 0.0
    for rank, i in enumerate(order):
        running = max(running, min(1.0, (len(pvals) - rank) * pvals[i]))
        adj[i] = running
    return adj


ap = argparse.ArgumentParser()
ap.add_argument("run_a")
ap.add_argument("run_b")
ap.add_argument("--split", default="test", choices=["all", "dev", "test"])
args = ap.parse_args()

docs, gt = common.load_docs(args.split), common.load_gt()
ra, ma = ev.evaluate_run(common.run_dir(args.run_a), docs, gt)
rb, mb = ev.evaluate_run(common.run_dir(args.run_b), docs, gt)
key = lambda r: (r["doc_id"], r["field"])  # noqa: E731
A, B = {key(r): r for r in ra}, {key(r): r for r in rb}
shared_docs = sorted({k[0] for k in A} & {k[0] for k in B})
if not shared_docs:
    raise SystemExit("Keine gemeinsamen Dokumente.")

name_a, name_b = common.run_dir(args.run_a).name, common.run_dir(args.run_b).name
out = [f"Vergleich (Split {args.split}, n = {len(shared_docs)} Pläne)",
       f"  A = {name_a}", f"  B = {name_b}", "",
       f"{'Feld':<8} {'Acc A':>7} {'Acc B':>7} {'Diff':>7} {'b(A+B-)':>8} {'c(A-B+)':>8} "
       f"{'p':>7} {'p_Holm':>7}"]
csv_rows, pvals = [], []
for f in C.FIELDS:
    a = [A[(d, f)]["correct"] for d in shared_docs]
    b_ = [B[(d, f)]["correct"] for d in shared_docs]
    b = sum(1 for x, y in zip(a, b_) if x and not y)
    c = sum(1 for x, y in zip(a, b_) if y and not x)
    p = mcnemar_exact(b, c)
    pvals.append(p)
    csv_rows.append({"field": f, "acc_a": sum(a) / len(a), "acc_b": sum(b_) / len(b_),
                     "b_a_only": b, "c_b_only": c, "p_mcnemar": p})
for row, p_adj in zip(csv_rows, holm(pvals)):
    row["p_holm"] = p_adj
    out.append(f"{row['field']:<8} {100 * row['acc_a']:7.1f} {100 * row['acc_b']:7.1f} "
               f"{100 * (row['acc_b'] - row['acc_a']):+7.1f} {row['b_a_only']:8d} "
               f"{row['c_b_only']:8d} {row['p_mcnemar']:7.3f} {p_adj:7.3f}")

# Wilcoxon auf Titel-NLS (nur Pläne mit Titel in der GT)
ta = [A[(d, "Title")]["sim"] for d in shared_docs if gt[d]["Title"]]
tb = [B[(d, "Title")]["sim"] for d in shared_docs if gt[d]["Title"]]
try:
    from scipy.stats import wilcoxon
    if any(x != y for x, y in zip(ta, tb)):
        w = wilcoxon(tb, ta, zero_method="wilcox")
        out += ["", f"Titel-NLS: Mittel A = {sum(ta) / len(ta):.3f}, B = {sum(tb) / len(tb):.3f}, "
                    f"Wilcoxon W = {w.statistic:.1f}, p = {w.pvalue:.3f} (n = {len(ta)})"]
    else:
        out += ["", "Titel-NLS: identisch in A und B"]
except ImportError:
    out += ["", "scipy fehlt: pip install scipy"]

# Paired Bootstrap für Differenz der Makro-Genauigkeit
def macro(rows_by_key, ds):
    return sum(sum(rows_by_key[(d, f)]["correct"] for d in ds) / len(ds) for f in C.FIELDS) / 4


rng = random.Random(C.SPLIT_SEED)
diffs = []
for _ in range(C.BOOTSTRAP_ITERS):
    sample = [rng.choice(shared_docs) for _ in shared_docs]
    diffs.append(macro(B, sample) - macro(A, sample))
diffs.sort()
lo, hi = diffs[int(0.025 * len(diffs))], diffs[int(0.975 * len(diffs)) - 1]
d_obs = macro(B, shared_docs) - macro(A, shared_docs)
out += [f"Makro-Genauigkeit: A = {100 * macro(A, shared_docs):.1f} %, "
        f"B = {100 * macro(B, shared_docs):.1f} %, Differenz = {100 * d_obs:+.1f} Pp. "
        f"[95%-KI {100 * lo:+.1f}; {100 * hi:+.1f}]",
        "", "b = nur A richtig, c = nur B richtig. p < 0,05 (nach Holm) gilt als signifikant."]

text = "\n".join(out)
print(text)
C.RESULTS_DIR.mkdir(exist_ok=True)
stem = f"compare_{name_a}_VS_{name_b}_{args.split}"
(C.RESULTS_DIR / f"{stem}.txt").write_text(text + "\n", "utf-8")
common.write_csv(C.RESULTS_DIR / f"{stem}.csv", csv_rows, list(csv_rows[0].keys()))
print(f"\nGespeichert: results/{stem}.txt/.csv")
