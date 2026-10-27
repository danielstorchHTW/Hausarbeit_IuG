"""Hilfe beim Ausfüllen der Spalte 'layout' in arbeitsdaten/data/docs.csv.

Öffnet jeden Plan in der Vorschau (macOS) und fragt nach der Lage des Schriftfelds:
  1 = br     (unten rechts)
  2 = other  (an anderer Stelle)
  3 = none   (kein abgegrenztes Schriftfeld)
  Enter = überspringen, q = speichern und beenden

Bereits ausgefüllte Pläne werden übersprungen (außer mit --all).
Aufruf:  python 01b_annotate_layout.py
"""
from __future__ import annotations

import argparse
import subprocess

import common
import config as C

ap = argparse.ArgumentParser()
ap.add_argument("--all", action="store_true", help="auch bereits ausgefüllte Pläne erneut abfragen")
args = ap.parse_args()

docs = common.load_docs("all")
fields = ["doc_id", "file", "datatype", "quality", "split", "layout"]
choices = {"1": "br", "2": "other", "3": "none"}
plan_files = {common.stem_key(p.name): p for p in C.PLANS_DIR.iterdir()}

todo = [d for d in docs if args.all or not d["layout"]]
print(f"{len(todo)} Pläne offen. Eingabe: 1 = unten rechts | 2 = woanders | 3 = kein Schriftfeld "
      f"| Enter = überspringen | q = beenden\n")

for i, d in enumerate(todo, 1):
    path = plan_files[common.stem_key(d["file"])]
    subprocess.run(["open", "-a", "Preview", str(path)], check=False)
    while True:
        ans = input(f"[{i}/{len(todo)}] {d['doc_id']}  {d['file']}  -> ").strip().lower()
        if ans in choices or ans in ("", "q"):
            break
        print("   Bitte 1, 2, 3, Enter oder q eingeben.")
    if ans == "q":
        break
    if ans:
        d["layout"] = choices[ans]
        common.write_csv(C.DOCS_CSV, docs, fields)   # nach jeder Eingabe speichern
        print(f"   gespeichert: {d['layout']}")

done = sum(1 for d in docs if d["layout"])
print(f"\n{done}/{len(docs)} Pläne haben ein Layout. Datei: {common.show(C.DOCS_CSV)}")
for v in ("br", "other", "none"):
    print(f"  {v:<6} {sum(d['layout'] == v for d in docs)}")
