"""Übernimmt die Ausgaben des lokalen Modells aus der Projektwoche als Lauf "A_projekt".

Die Datei results_local_vlm.txt wurde in der Projektwoche von application_llm_v1.py
(Qwen2.5-VL-3B, Temperatur 0,1, gleicher Prompt und Ausschnitt wie Bedingung A) erzeugt.
Sie wird hier nur umgewandelt, damit 03_evaluate.py sie mit denselben Regeln bewerten kann.
Laufzeiten sind nicht bekannt (seconds = None).

Erwartet:  ../arbeitsdaten/projekt_ausgaben/results_local_vlm.txt   (vertraulich, nicht im Repo)
Ergebnis:  ../arbeitsdaten/runs/A_projekt__qwen2.5vl-3b/predictions.jsonl
Aufruf:    python 06_import_projekt.py
"""
from __future__ import annotations

import json

import common
import config as C

SRC = C.WORK_DIR / "projekt_ausgaben" / "results_local_vlm.txt"
RUN = C.RUNS_DIR / "A_projekt__qwen2.5vl-3b"

text = SRC.read_text(encoding="utf-8")
by_file = {common.stem_key(d["file"]): d["doc_id"] for d in common.load_docs("all")}
recs = []
for block in text.split("FILE:")[1:]:
    name = block.splitlines()[0].strip()
    pred, valid = common.parse_kv(block)   # gleicher Parser wie für Bedingung A
    recs.append({"doc_id": by_file[common.stem_key(name)], "pred": pred, "valid": valid,
                 "fallback": False, "error": None, "seconds": None})

RUN.mkdir(parents=True, exist_ok=True)
(RUN / "predictions.jsonl").write_text(
    "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in recs), "utf-8")
(RUN / "config.json").write_text(json.dumps({
    "run": RUN.name, "condition": "A_baseline", "model": "qwen2.5vl:3b",
    "source": "Projektwoche, application_llm_v1.py (Temperatur 0.1)",
    "note": "nur umgewandelt, nicht neu ausgeführt"}, indent=2, ensure_ascii=False), "utf-8")
print(f"{len(recs)} Pläne übernommen -> {common.show(RUN / 'predictions.jsonl')}")
