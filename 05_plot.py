"""Abbildung für die Hausarbeit: Feldgenauigkeit je Bedingung (gruppiertes Balkendiagramm).

  python 05_plot.py                # liest results/summary_test.csv
  python 05_plot.py --split dev
"""
from __future__ import annotations

import argparse

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

import common  # noqa: E402
import config as C  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--split", default="test")
args = ap.parse_args()

rows = common.read_csv(C.RESULTS_DIR / f"summary_{args.split}.csv")
labels = ["Titel", "Datum", "ID", "Maßstab", "Makro"]
keys = [f"{f}_acc" for f in C.FIELDS] + ["macro_acc"]
greys = ["#d9d9d9", "#969696", "#525252", "#252525"]   # druckfreundlich (schwarz-weiß)

fig, ax = plt.subplots(figsize=(6.3, 2.8))
width = 0.8 / len(rows)
for i, r in enumerate(rows):
    xs = [j + (i - (len(rows) - 1) / 2) * width for j in range(len(labels))]
    vals = [100 * float(r[k]) for k in keys]
    ax.bar(xs, vals, width, label=r["run"].split("__")[0].replace("_", " "),
           color=greys[i % len(greys)], edgecolor="black", linewidth=0.5)
ax.set_xticks(range(len(labels)))
ax.set_xticklabels(labels)
ax.set_ylabel("Genauigkeit [%]")
ax.set_ylim(0, 100)
ax.legend(fontsize=8, frameon=False, ncol=len(rows), loc="upper center",
          bbox_to_anchor=(0.5, 1.18))
ax.spines[["top", "right"]].set_visible(False)
fig.tight_layout()
for ext in ("pdf", "png"):
    fig.savefig(C.RESULTS_DIR / f"fig_accuracy_{args.split}.{ext}", dpi=300, bbox_inches="tight")
print(f"Gespeichert: results/fig_accuracy_{args.split}.pdf/.png")
