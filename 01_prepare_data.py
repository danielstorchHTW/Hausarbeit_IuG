"""Bereitet den Datensatz vor (einmalig, ca. 2-5 Minuten).

1. Bereinigt die Ground Truth (z. B. verrutschte Spalten durch unmaskierte Kommas).
2. Ordnet jeder GT-Zeile ihre Plandatei zu und vergibt Pseudonyme doc_01 ... doc_42.
3. Erzeugt einen festen, nach Qualität geschichteten Dev/Test-Split.
4. Speichert jede Seite einmal als Graustufen-JPEG (max. 8000 px) in arbeitsdaten/data/cache/ (außerhalb des Repos).

Bestehende Split- und Layout-Einträge in arbeitsdaten/data/docs.csv bleiben erhalten
(außer mit --reset-split). Aufruf:  python 01_prepare_data.py
"""
from __future__ import annotations

import argparse
import csv
import random
import sys

from PIL import Image

import common
import config as C

ap = argparse.ArgumentParser()
ap.add_argument("--reset-split", action="store_true", help="Split neu ziehen (Vorsicht!)")
ap.add_argument("--skip-cache", action="store_true", help="Nur CSVs erzeugen, keine Bilder")
args = ap.parse_args()

# ------------------------------------------------------------------
# 1. Ground Truth einlesen und reparieren
# ------------------------------------------------------------------
with open(C.GT_RAW, encoding="utf-8-sig", newline="") as f:
    rows = list(csv.reader(f))
header, body = rows[0], [r for r in rows[1:] if any(c.strip() for c in r)]
n_cols = len(header)
gt_rows = []
for r in body:
    if len(r) == n_cols + 1:
        # Unmaskiertes Komma im Titel: Felder 1 und 2 gehören zusammen
        print(f"[Fix] Komma im Titel repariert: {r[0]}")
        r = [r[0], r[1] + "," + r[2]] + r[3:]
    elif len(r) != n_cols:
        sys.exit(f"Unerwartete Spaltenzahl ({len(r)}) in Zeile: {r}")
    gt_rows.append(dict(zip(header, (c.strip() for c in r))))

# ------------------------------------------------------------------
# 2. Plandateien zuordnen
# ------------------------------------------------------------------
plan_files = {common.stem_key(p.name): p for p in C.PLANS_DIR.iterdir()
              if p.suffix.lower() in (".tif", ".tiff", ".pdf", ".png", ".jpg", ".jpeg")}
missing = [r["File Name"] for r in gt_rows if common.stem_key(r["File Name"]) not in plan_files]
if missing:
    sys.exit("Keine Plandatei gefunden für:\n  " + "\n  ".join(missing))
extra = set(plan_files) - {common.stem_key(r["File Name"]) for r in gt_rows}
if extra:
    print(f"[Hinweis] {len(extra)} Pläne ohne GT-Eintrag werden ignoriert: {sorted(extra)}")

gt_rows.sort(key=lambda r: common.nfc(r["File Name"]).casefold())
old = {d["file"]: d for d in common.read_csv(C.DOCS_CSV)} if C.DOCS_CSV.exists() else {}

docs, gt_clean = [], []
for i, r in enumerate(gt_rows, 1):
    doc_id = f"doc_{i:02d}"
    path = plan_files[common.stem_key(r["File Name"])]
    fname = common.nfc(path.name)
    prev = old.get(fname, {})
    docs.append({
        "doc_id": doc_id, "file": fname, "datatype": r.get("Datatype", ""),
        "quality": r.get("Quality", ""), "split": prev.get("split", ""),
        "layout": prev.get("layout", ""),
    })
    gt_clean.append({"doc_id": doc_id, **{f: r[f] for f in C.FIELDS}})

# ------------------------------------------------------------------
# 3. Geschichteter Split (fest, Seed aus config)
# ------------------------------------------------------------------
if args.reset_split or not all(d["split"] for d in docs):
    rng = random.Random(C.SPLIT_SEED)
    for d in docs:
        d["split"] = "test"
    for q in sorted({d["quality"] for d in docs}):
        group = [d for d in docs if d["quality"] == q]
        for d in rng.sample(group, min(C.DEV_PER_QUALITY, len(group))):
            d["split"] = "dev"
    print("[Split] neu erzeugt")

common.write_csv(C.DOCS_CSV, docs, ["doc_id", "file", "datatype", "quality", "split", "layout"])
common.write_csv(C.GT_CLEAN, gt_clean, ["doc_id"] + C.FIELDS)
n_dev = sum(d["split"] == "dev" for d in docs)
print(f"[OK] {len(docs)} Dokumente | dev={n_dev} test={len(docs) - n_dev}")
print(f"     {common.show(C.DOCS_CSV)} und {common.show(C.GT_CLEAN)} geschrieben")

# ------------------------------------------------------------------
# 4. Seitenbilder cachen
# ------------------------------------------------------------------
if args.skip_cache:
    sys.exit(0)
C.CACHE_DIR.mkdir(parents=True, exist_ok=True)


def save_page(img: Image.Image, out) -> None:
    if img.mode != "L":
        img = img.convert("L")
    img = common.shrink(img, C.CACHE_MAX_SIDE)
    img.save(out, "JPEG", quality=92)


for d in docs:
    src = C.PLANS_DIR / d["file"]
    if not src.exists():  # NFD-Dateiname auf macOS
        src = plan_files[common.stem_key(d["file"])]
    if list(C.CACHE_DIR.glob(f"{d['doc_id']}_p*.jpg")):
        continue
    print(f"  cache {d['doc_id']} ...", flush=True)
    if src.suffix.lower() == ".pdf":
        import pypdfium2 as pdfium
        pdf = pdfium.PdfDocument(str(src))
        for p in range(len(pdf)):
            img = pdf[p].render(scale=C.PDF_DPI / 72).to_pil()
            save_page(img, C.CACHE_DIR / f"{d['doc_id']}_p{p + 1}.jpg")
        pdf.close()
    else:
        with Image.open(src) as im:
            n = getattr(im, "n_frames", 1)
            for p in range(n):
                im.seek(p)
                save_page(im.copy(), C.CACHE_DIR / f"{d['doc_id']}_p{p + 1}.jpg")

print(f"[OK] Cache vollständig: {len(list(C.CACHE_DIR.glob('*.jpg')))} Seitenbilder")
if not any(d["layout"] for d in docs):
    print(f"\nNächster manueller Schritt: Spalte 'layout' in {common.show(C.DOCS_CSV)} ausfüllen "
          "(br = Schriftfeld unten rechts, other = woanders, none = kein Schriftfeld).")
