"""Führt eine Versuchsbedingung auf den Plänen aus und speichert die Rohausgaben.

Beispiele:
  python 02_run_extraction.py --condition A_baseline --split dev --limit 3 --tag pilot
  python 02_run_extraction.py --condition B_structured --split dev --tag dev
  python 02_run_extraction.py --condition C_twostage            # alle 42 Pläne
  python 02_run_extraction.py --condition A_baseline --model qwen2.5vl:3b

Ergebnis: arbeitsdaten/runs/<condition>__<modell>[__<tag>]/predictions.jsonl + config.json
Abgebrochene Läufe setzen beim erneuten Start dort fort, wo sie aufgehört haben.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import platform
import re
import time
from datetime import datetime

from PIL import Image

import common
import config as C

ap = argparse.ArgumentParser()
ap.add_argument("--condition", required=True, choices=list(C.CONDITIONS))
ap.add_argument("--model", default=C.MODEL)
ap.add_argument("--split", default="all", choices=["all", "dev", "test"])
ap.add_argument("--limit", type=int, default=0, help="nur die ersten N Dokumente")
ap.add_argument("--docs", default="", help="kommagetrennte doc_ids, z. B. doc_03,doc_17")
ap.add_argument("--tag", default="", help="Zusatz im Ordnernamen, z. B. pilot oder dev")
ap.add_argument("--overwrite", action="store_true", help="vorhandene Ergebnisse verwerfen")
ap.add_argument("--save-inputs", action="store_true",
                help="gesendete Bilder in arbeitsdaten/runs/<lauf>/inputs/ speichern (Fehleranalyse)")
args = ap.parse_args()

cond = C.CONDITIONS[args.condition]
prompt = common.load_prompt(cond["prompt"])
locate = common.load_prompt(C.LOCATE_PROMPT)
structured = cond["prompt"] != "p0_baseline"   # Baseline bleibt im Originalformat (Freitext)

model_slug = re.sub(r"[^\w.-]+", "-", args.model)
run_name = f"{args.condition}__{model_slug}" + (f"__{args.tag}" if args.tag else "")
run_dir = C.RUNS_DIR / run_name
run_dir.mkdir(parents=True, exist_ok=True)
pred_file = run_dir / "predictions.jsonl"
if args.overwrite and pred_file.exists():
    pred_file.unlink()

docs = common.load_docs(args.split)
if args.docs:
    wanted = set(args.docs.split(","))
    docs = [d for d in docs if d["doc_id"] in wanted]
if args.limit:
    docs = docs[: args.limit]

done = set()
if pred_file.exists():
    # nur erfolgreich verarbeitete Pläne gelten als erledigt
    done = {r["doc_id"] for r in (json.loads(l) for l in
            pred_file.read_text(encoding="utf-8").splitlines() if l) if not r.get("error")}

# ------------------------------------------------------------------
# Protokoll der Laufkonfiguration (für den Methodikteil)
# ------------------------------------------------------------------
print("Verbinde mit Ollama ...", flush=True)
try:
    models = common.ollama_models()
except Exception as e:  # noqa: BLE001
    raise SystemExit(f"Ollama nicht erreichbar ({e}). Läuft 'ollama serve' im anderen Fenster?")
if args.model not in models:
    raise SystemExit(f"Modell {args.model} nicht installiert: ollama pull {args.model}")
used_prompts = {cond["prompt"]: prompt}
if cond["input"] == "twostage":
    used_prompts[C.LOCATE_PROMPT] = locate
cfg = {
    "run": run_name, "condition": args.condition, **cond, "model": args.model,
    "model_digest": models[args.model], "ollama_version": common.ollama_version(),
    "options": C.OPTIONS, "think": C.THINK, "structured_output": structured,
    "image": {"cache_max": C.CACHE_MAX_SIDE, "crop_max": C.CROP_MAX_SIDE,
              "full_max": C.FULL_MAX_SIDE, "locate_max": C.LOCATE_MAX_SIDE,
              "fixed_crop": C.FIXED_CROP, "bbox_pad": C.BBOX_PAD, "bbox_min": C.BBOX_MIN_SIZE},
    "prompts": {k: {**v, "sha256": hashlib.sha256((str(v["system"]) + v["user"]).encode())
                    .hexdigest()[:12]} for k, v in used_prompts.items()},
    "machine": f"{platform.system()} {platform.machine()} | Python {platform.python_version()}",
    "started": datetime.now().isoformat(timespec="seconds"),
}
(run_dir / "config.json").write_text(json.dumps(cfg, indent=2, ensure_ascii=False), "utf-8")


# ------------------------------------------------------------------
# Hilfsfunktionen
# ------------------------------------------------------------------
CURRENT = {"tag": ""}   # doc_id + Seite, für --save-inputs


def save_input(img: Image.Image, stage: str) -> None:
    if args.save_inputs:
        (run_dir / "inputs").mkdir(exist_ok=True)
        img.save(run_dir / "inputs" / f"{CURRENT['tag']}_{stage}.jpg", "JPEG", quality=85)


def extract(img: Image.Image, max_side: int) -> dict:
    small = common.shrink(img, max_side)
    save_input(small, "extract")
    r = common.ollama_chat(args.model, prompt["user"], common.to_b64(small), prompt["system"],
                           fmt=common.EXTRACT_SCHEMA if structured else None)
    fields, valid = (common.parse_json_fields if structured else common.parse_kv)(r["content"])
    return {"raw": r["content"], "fields": fields, "valid": valid, "sent_size": small.size,
            "wall_s": r["wall_s"], "prompt_tokens": r["prompt_tokens"],
            "output_tokens": r["output_tokens"]}


def locate_box(page: Image.Image) -> dict:
    """Stufe 1: Schriftfeld lokalisieren -> relative Box (l, t, r, b) oder None."""
    small = common.shrink(page, C.LOCATE_MAX_SIDE)
    save_input(small, "locate")
    r = common.ollama_chat(args.model, locate["user"], common.to_b64(small), locate["system"],
                           fmt=common.BBOX_SCHEMA)
    box = common.parse_bbox(r["content"])
    rel = None
    if box:
        x1, y1, x2, y2 = box
        if max(box) > 1000:   # Modell hat Pixel des gesendeten Bildes geliefert
            sx, sy = small.size
            x1, x2, y1, y2 = x1 / sx * 1000, x2 / sx * 1000, y1 / sy * 1000, y2 / sy * 1000
        l, t, rr, b = (max(0.0, min(1.0, v / 1000)) for v in (min(x1, x2), min(y1, y2),
                                                               max(x1, x2), max(y1, y2)))
        if rr - l > 0.005 and b - t > 0.005:
            # Rand hinzufügen und Mindestgröße sicherstellen
            l, t, rr, b = l - C.BBOX_PAD, t - C.BBOX_PAD, rr + C.BBOX_PAD, b + C.BBOX_PAD
            cx, cy = (l + rr) / 2, (t + b) / 2
            hw, hh = max((rr - l) / 2, C.BBOX_MIN_SIZE / 2), max((b - t) / 2, C.BBOX_MIN_SIZE / 2)
            l, rr, t, b = max(0, cx - hw), min(1, cx + hw), max(0, cy - hh), min(1, cy + hh)
            rel = (round(l, 4), round(t, 4), round(rr, 4), round(b, 4))
    return {"raw": r["content"], "bbox_raw": box, "crop_rel": rel, "wall_s": r["wall_s"],
            "prompt_tokens": r["prompt_tokens"], "output_tokens": r["output_tokens"]}


def run_page(page: Image.Image) -> dict:
    mode = cond["input"]
    if mode == "crop":
        return {"stage2": extract(common.crop_rel(page, C.FIXED_CROP), C.CROP_MAX_SIDE)}
    if mode == "full":
        return {"stage2": extract(page, C.FULL_MAX_SIDE)}
    s1 = locate_box(page)
    if s1["crop_rel"] is None:   # Fallback: ganze Seite
        return {"stage1": s1, "fallback": True, "stage2": extract(page, C.FULL_MAX_SIDE)}
    return {"stage1": s1, "fallback": False,
            "stage2": extract(common.crop_rel(page, s1["crop_rel"]), C.CROP_MAX_SIDE)}


# ------------------------------------------------------------------
# Hauptschleife
# ------------------------------------------------------------------
todo = [d for d in docs if d["doc_id"] not in done]
print(f"Lauf: {run_name} | {len(todo)} offen, {len(done)} bereits erledigt")
t_run = time.time()
n_fail = 0
with open(pred_file, "a", encoding="utf-8") as out:
    for i, d in enumerate(todo, 1):
        t0 = time.time()
        rec = {"doc_id": d["doc_id"], "pages": [], "error": None}
        try:
            for p in common.cache_pages(d["doc_id"]):
                CURRENT["tag"] = p.stem
                with Image.open(p) as im:
                    page = im.convert("L")
                rec["pages"].append(run_page(page))
        except Exception as e:  # noqa: BLE001
            n_fail += 1
            print(f"[{i}/{len(todo)}] {d['doc_id']} FEHLER: {e}", flush=True)
            if n_fail >= 2:
                raise SystemExit("\nAbbruch nach 2 Fehlern in Folge. Ollama prüfen und denselben "
                                 "Befehl erneut starten – fertige Pläne werden übersprungen.")
            continue   # Fehler wird nicht gespeichert -> Plan wird beim nächsten Start wiederholt
        n_fail = 0
        # Mehrseitige Dokumente: je Feld erster nicht-leerer Wert in Seitenreihenfolge
        rec["pred"] = {f: next((pg["stage2"]["fields"][f] for pg in rec["pages"]
                                if pg["stage2"]["fields"][f]), None) for f in C.FIELDS}
        rec["valid"] = bool(rec["pages"]) and all(pg["stage2"]["valid"] for pg in rec["pages"])
        rec["fallback"] = any(pg.get("fallback") for pg in rec["pages"])
        rec["seconds"] = round(time.time() - t0, 2)
        out.write(json.dumps(rec, ensure_ascii=False) + "\n")
        out.flush()
        eta = (time.time() - t_run) / i * (len(todo) - i)
        status = "FEHLER " + rec["error"][:80] if rec["error"] else json.dumps(rec["pred"],
                                                                              ensure_ascii=False)
        print(f"[{i}/{len(todo)}] {d['doc_id']} {rec['seconds']:.0f}s "
              f"(Rest ~{eta / 60:.0f} min) {status}", flush=True)

print(f"Fertig in {(time.time() - t_run) / 60:.1f} min -> {common.show(pred_file)}")
