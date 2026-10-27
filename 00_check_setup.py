"""Prüft die Umgebung: Python-Pakete, Ollama, Modell und einen Testaufruf.

Der Testaufruf nutzt ein künstlich erzeugtes Schriftfeld (keine echten Pläne).
Aufruf:  python 00_check_setup.py
"""
from __future__ import annotations

import importlib
import sys
import time

import config as C

ok = True


def check(label: str, cond: bool, hint: str = "") -> None:
    global ok
    print(f"[{'OK' if cond else 'FEHLER'}] {label}" + ("" if cond else f"\n        -> {hint}"))
    ok &= cond


check(f"Python {sys.version.split()[0]} (>= 3.9)", sys.version_info >= (3, 9),
      "Neuere Python-Version installieren: brew install python@3.12")

for pkg in ["PIL", "pypdfium2", "scipy", "matplotlib"]:
    try:
        importlib.import_module(pkg)
        check(f"Paket {pkg}", True)
    except ImportError:
        check(f"Paket {pkg}", False, "pip install -r requirements.txt (im aktivierten .venv)")

check("Ordner plans/ vorhanden", C.PLANS_DIR.is_dir(), f"Pläne nach {C.PLANS_DIR} legen")
check("ground_truth.csv vorhanden", C.GT_RAW.is_file(), f"Datei nach {C.GT_RAW} legen")

import common  # noqa: E402  (erst nach Paketprüfung)

try:
    print(f"       Ollama-Version: {common.ollama_version()}")
    models = common.ollama_models()
    check("Ollama läuft", True)
except Exception as e:  # noqa: BLE001
    check("Ollama läuft", False, f"Ollama-App starten bzw. 'ollama serve' ({e})")
    sys.exit(1)

has_model = C.MODEL in models
check(f"Modell {C.MODEL} installiert", has_model, f"ollama pull {C.MODEL}")
if not has_model:
    print("       Installiert:", ", ".join(models) or "-")
    sys.exit(1)

# ---- Testaufruf mit synthetischem Schriftfeld ----
from PIL import Image, ImageDraw  # noqa: E402

img = Image.new("L", (900, 360), 255)
d = ImageDraw.Draw(img)
d.rectangle([10, 10, 890, 350], outline=0, width=4)
d.line([10, 120, 890, 120], fill=0, width=3)
d.line([450, 120, 450, 350], fill=0, width=3)
lines = [((30, 40), "U-Bhf. Musterstrasse Umbau Treppenanlage Grundriss"),
         ((30, 150), "Massstab 1:50"), ((470, 150), "Zeichnungs-Nr. X12-345"),
         ((30, 250), "Datum 12.03.1985")]
try:
    from PIL import ImageFont
    font = ImageFont.load_default(size=28)
except Exception:  # ältere Pillow-Versionen
    font = None
for xy, text in lines:
    d.text(xy, text, fill=0, font=font)

prompt = common.load_prompt("p1_structured")
print("       Testaufruf läuft (erster Aufruf lädt das Modell, kann ~30 s dauern) ...")
t0 = time.time()
try:
    r = common.ollama_chat(C.MODEL, prompt["user"], common.to_b64(img), prompt["system"],
                           fmt=common.EXTRACT_SCHEMA)
    fields, valid = common.parse_json_fields(r["content"])
    print(f"       Antwort: {r['content'][:300]}")
    print(f"       Dauer: {time.time() - t0:.1f} s | Prompt-Tokens: {r['prompt_tokens']} "
          f"| Output-Tokens: {r['output_tokens']}")
    check("Gültiges JSON zurückgegeben", valid, "Modell/Ollama-Version prüfen (ollama --version)")
    if "1:50" not in common.scale_set(fields["Scale"] or ""):
        print("[Hinweis] Maßstab 1:50 im Testbild nicht erkannt (kein Fehler, nur auffällig)")
except Exception as e:  # noqa: BLE001
    check("Testaufruf", False, str(e))

print("\nAlles bereit." if ok else "\nBitte die markierten Punkte beheben.")
