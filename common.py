"""Gemeinsame Hilfsfunktionen: Daten laden, Bilder, Ollama-Client, Parsing, Normalisierung."""
from __future__ import annotations

import base64
import csv
import io
import json
import re
import time
import unicodedata
import urllib.error
import urllib.request
from pathlib import Path

from PIL import Image

import config as C

Image.MAX_IMAGE_PIXELS = None


# ==================================================================
# Prompts
# ==================================================================
def load_prompt(name: str) -> dict:
    """Liest prompts/<name>.txt. Abschnitte '### SYSTEM' und '### USER' (SYSTEM optional).
    Ohne Abschnittsmarker ist der ganze Text der User-Prompt (z. B. p0_baseline)."""
    text = (C.PROMPTS_DIR / f"{name}.txt").read_text(encoding="utf-8")
    if "### USER" not in text:
        return {"system": None, "user": text.strip()}
    system = None
    if "### SYSTEM" in text:
        system = text.split("### SYSTEM", 1)[1].split("### USER", 1)[0].strip()
    user = text.split("### USER", 1)[1].strip()
    return {"system": system, "user": user}


# ==================================================================
# Datensatz
# ==================================================================
def nfc(s: str) -> str:
    return unicodedata.normalize("NFC", s)


def stem_key(name: str) -> str:
    """Dateiname -> Vergleichsschlüssel (NFC, ohne Endung, casefold).
    macOS speichert Umlaute in Dateinamen als NFD, die CSV als NFC."""
    name = nfc(name.strip())
    if Path(name).suffix.lower() in (".tif", ".tiff", ".pdf", ".png", ".jpg", ".jpeg"):
        name = name[: -len(Path(name).suffix)]
    return name.strip().casefold()


def read_csv(path: Path) -> list[dict]:
    with open(path, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def write_csv(path: Path, rows: list[dict], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


def show(path: Path) -> str:
    """Pfad kurz anzeigen (relativ zum Hausarbeit-Ordner)."""
    try:
        return str(Path(path).resolve().relative_to(C.PRIVATE))
    except ValueError:
        return str(path)


def run_dir(name_or_path: str) -> Path:
    """Akzeptiert einen Laufnamen (z. B. 'B_structured__qwen3-vl-4b-instruct') oder einen Pfad."""
    p = Path(name_or_path)
    return p if p.is_dir() else C.RUNS_DIR / name_or_path


def load_docs(split: str = "all") -> list[dict]:
    if not C.DOCS_CSV.exists():
        raise SystemExit(f"{show(C.DOCS_CSV)} fehlt. Zuerst: python 01_prepare_data.py")
    docs = read_csv(C.DOCS_CSV)
    if split != "all":
        docs = [d for d in docs if d["split"] == split]
    return docs


def split_cell(cell: str, field: str) -> list[str]:
    """GT-Zelle -> Liste gültiger Alternativen. Trenner: ';' und '|'.
    Bei ID zusätzlich ' / ' (z. B. 'XY 123 / AB C 45 / Blatt 7')."""
    if cell is None:
        return []
    parts = re.split(r"[;|]", cell)
    if field == "ID":
        parts = [p for part in parts for p in re.split(r"\s+/\s+", part)] + [cell]
    out = []
    for p in parts:
        p = p.strip()
        if p and not is_empty(p) and p not in out:
            out.append(p)
    return out


def load_gt() -> dict:
    """{doc_id: {field: [Alternativen]}}"""
    gt = {}
    for row in read_csv(C.GT_CLEAN):
        gt[row["doc_id"]] = {f: split_cell(row[f], f) for f in C.FIELDS}
    return gt


# ==================================================================
# Bilder
# ==================================================================
def cache_pages(doc_id: str) -> list[Path]:
    pages = sorted(C.CACHE_DIR.glob(f"{doc_id}_p*.jpg"),
                   key=lambda p: int(p.stem.rsplit("_p", 1)[1]))
    if not pages:
        raise FileNotFoundError(f"Kein Cache für {doc_id}. 01_prepare_data.py ausführen.")
    return pages


def shrink(img: Image.Image, max_side: int) -> Image.Image:
    """Verkleinert proportional auf max_side (lange Seite). Vergrößert nie."""
    w, h = img.size
    if max(w, h) <= max_side:
        return img
    factor = max(w, h) / max_side
    if factor >= 2:
        img = img.reduce(int(factor))      # schnelles Vorverkleinern
        w, h = img.size
    scale = max_side / max(w, h)
    return img.resize((max(1, round(w * scale)), max(1, round(h * scale))), Image.LANCZOS)


def crop_rel(img: Image.Image, box: tuple) -> Image.Image:
    w, h = img.size
    l, t, r, b = box
    return img.crop((int(l * w), int(t * h), int(r * w), int(b * h)))


def to_b64(img: Image.Image) -> str:
    if img.mode not in ("L", "RGB"):
        img = img.convert("L")
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=90)
    return base64.b64encode(buf.getvalue()).decode("ascii")


# ==================================================================
# Ollama
# ==================================================================
def _http(method: str, path: str, payload: dict | None = None, timeout: float = 10):
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    req = urllib.request.Request(C.OLLAMA_URL + path, data=data, method=method,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def ollama_version() -> str:
    return _http("GET", "/api/version").get("version", "?")


def ollama_models() -> dict:
    """{name: digest} der lokal installierten Modelle."""
    return {m["name"]: m.get("digest", "") for m in _http("GET", "/api/tags").get("models", [])}


def ollama_chat(model: str, user: str, image_b64: str, system: str | None = None,
                fmt=None) -> dict:
    """Ein Bild + Prompt -> Antworttext und Laufzeitmetriken."""
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": user, "images": [image_b64]})
    payload = {
        "model": model,
        "messages": messages,
        "stream": False,
        "options": C.OPTIONS,
        "keep_alive": C.KEEP_ALIVE,
    }
    if fmt is not None:
        payload["format"] = fmt
    if C.THINK is not None:
        payload["think"] = C.THINK
    t0 = time.time()
    for attempt in range(3):   # Verbindungsabbrüche bis zu 2x wiederholen
        try:
            r = _http("POST", "/api/chat", payload, timeout=C.REQUEST_TIMEOUT_S)
            break
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", "replace")
            raise RuntimeError(f"Ollama HTTP {e.code}: {body}") from None
        except OSError as e:   # URLError, Timeout, Verbindung abgelehnt
            if attempt == 2:
                raise RuntimeError(f"Ollama nicht erreichbar: {e}") from None
            print(f"   [Verbindung fehlgeschlagen: {e} -> neuer Versuch in 10 s]", flush=True)
            time.sleep(10)
    n_prompt = r.get("prompt_eval_count") or 0
    if n_prompt > 0.9 * C.OPTIONS["num_ctx"]:
        print(f"[Warnung] {n_prompt} Prompt-Tokens nahe am Limit num_ctx={C.OPTIONS['num_ctx']} "
              "-> Bildgröße senken oder num_ctx erhöhen")
    return {
        "content": (r.get("message") or {}).get("content", ""),
        "wall_s": round(time.time() - t0, 2),
        "prompt_tokens": r.get("prompt_eval_count"),
        "output_tokens": r.get("eval_count"),
        "load_s": round((r.get("load_duration") or 0) / 1e9, 2),
    }


# JSON-Schemata für strukturierte Ausgabe (Ollama "format")
_NULLABLE = {"type": ["string", "null"]}
EXTRACT_SCHEMA = {
    "type": "object",
    "properties": {"title": _NULLABLE, "date": _NULLABLE, "id": _NULLABLE, "scale": _NULLABLE},
    "required": ["title", "date", "id", "scale"],
}
BBOX_SCHEMA = {
    "type": "object",
    "properties": {"bbox_2d": {"type": "array", "items": {"type": "number"},
                               "minItems": 4, "maxItems": 4}},
    "required": ["bbox_2d"],
}


# ==================================================================
# Antworten parsen
# ==================================================================
NOT_FOUND = {"", "not found", "notfound", "n/a", "na", "none", "null", "-", "--", "unknown",
             "nicht gefunden", "nicht vorhanden", "nicht lesbar", "kein", "keine", "unbekannt"}


def is_empty(v) -> bool:
    return v is None or str(v).strip().strip(".").strip().casefold() in NOT_FOUND


def clean(v):
    if v is None:
        return None
    v = str(v).strip()
    return None if is_empty(v) else v


def _json_obj(text: str):
    try:
        return json.loads(text)
    except Exception:
        m = re.search(r"\{.*\}", text, re.S)
        if m:
            try:
                return json.loads(m.group(0))
            except Exception:
                return None
    return None


def parse_kv(text: str) -> tuple[dict, bool]:
    """Format des Projekt-Prompts: 'Title: ...' Zeilen."""
    out = {f: None for f in C.FIELDS}
    found = False
    for line in text.splitlines():
        line = line.replace("*", "").strip()
        m = re.match(r"^(Title|Date|ID|Scale)\s*:\s*(.*)$", line, re.I)
        if m:
            key = {f.lower(): f for f in C.FIELDS}[m.group(1).lower()]
            out[key] = clean(m.group(2))
            found = True
    return out, found


def parse_json_fields(text: str) -> tuple[dict, bool]:
    obj = _json_obj(text)
    out = {f: None for f in C.FIELDS}
    if not isinstance(obj, dict):
        return out, False
    low = {str(k).lower(): v for k, v in obj.items()}
    for f in C.FIELDS:
        v = low.get(f.lower())
        if isinstance(v, list):
            v = "; ".join(str(x) for x in v if x is not None)
        out[f] = clean(v)
    return out, True


def parse_bbox(text: str):
    obj = _json_obj(text)
    if isinstance(obj, dict):
        box = obj.get("bbox_2d") or obj.get("bbox")
    elif isinstance(obj, list):
        box = obj[0].get("bbox_2d") if obj and isinstance(obj[0], dict) else obj
    else:
        box = None
    if isinstance(box, list) and len(box) == 4:
        try:
            return [float(x) for x in box]
        except (TypeError, ValueError):
            return None
    return None


# ==================================================================
# Normalisierung & Ähnlichkeit (Evaluation)
# ==================================================================
def levenshtein(a: str, b: str) -> int:
    if len(a) < len(b):
        a, b = b, a
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


def nls(a: str, b: str) -> float:
    """Normalisierte Levenshtein-Ähnlichkeit in [0,1] (Grundlage von ANLS)."""
    if not a and not b:
        return 1.0
    return 1.0 - levenshtein(a, b) / max(len(a), len(b))


def token_f1(pred: str, gold: str) -> float:
    """Token-F1 (Rajpurkar et al. 2016) auf normalisierten Wörtern. Robust gegen
    zusätzliche oder fehlende Wörter (z. B. GT 'X Y', Modell 'X Y Grundriss')."""
    from collections import Counter
    p, g = norm_text(pred).split(), norm_text(gold).split()
    if not p or not g:
        return 0.0
    common_n = sum((Counter(p) & Counter(g)).values())
    if common_n == 0:
        return 0.0
    prec, rec = common_n / len(p), common_n / len(g)
    return 2 * prec * rec / (prec + rec)


def norm_text(s: str) -> str:
    s = unicodedata.normalize("NFKC", s).casefold().replace("ß", "ss")
    s = re.sub(r"[^\w\s]", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def norm_id(s: str) -> str:
    s = unicodedata.normalize("NFKC", s).casefold()
    return re.sub(r"[\s\-_/.,:;]", "", s)


MONTHS = {
    "januar": 1, "jan": 1, "january": 1, "februar": 2, "feb": 2, "february": 2, "märz": 3,
    "maerz": 3, "mär": 3, "mrz": 3, "mar": 3, "march": 3, "april": 4, "apr": 4, "mai": 5,
    "may": 5, "juni": 6, "jun": 6, "june": 6, "juli": 7, "jul": 7, "july": 7, "august": 8,
    "aug": 8, "september": 9, "sep": 9, "sept": 9, "oktober": 10, "okt": 10, "oct": 10,
    "october": 10, "november": 11, "nov": 11, "dezember": 12, "dez": 12, "dec": 12,
    "december": 12,
}


def _year(y: str) -> int:
    v = int(y)
    if len(y) == 2:
        return 2000 + v if v <= 30 else 1900 + v
    return v


def parse_date(s: str):
    """Erstes Datum im String -> (Jahr, Monat|None, Tag|None) oder None."""
    t = unicodedata.normalize("NFKC", s).casefold().replace(",", ".")
    m = re.search(r"\b(\d{4})-(\d{1,2})-(\d{1,2})\b", t)
    if m:
        return int(m[1]), int(m[2]), int(m[3])
    m = re.search(r"\b(\d{1,2})\s*[./\-]\s*(\d{1,2})\s*[./\-]\s*(\d{4}|\d{2})\b", t)
    if m and 1 <= int(m[2]) <= 12 and 1 <= int(m[1]) <= 31:
        return _year(m[3]), int(m[2]), int(m[1])
    m = re.search(r"\b(\d{1,2})\s*\.?\s*([a-zäöü]{3,9})\.?\s*(\d{4}|\d{2})\b", t)
    if m and m[2] in MONTHS:
        return _year(m[3]), MONTHS[m[2]], int(m[1])
    m = re.search(r"\b([a-zäöü]{3,9})\.?\s*(\d{4})\b", t)
    if m and m[1] in MONTHS:
        return int(m[2]), MONTHS[m[1]], None
    m = re.search(r"\b(\d{1,2})\s*[./]\s*(\d{4}|\d{2})\b", t)
    if m and 1 <= int(m[1]) <= 12:
        return _year(m[2]), int(m[1]), None
    m = re.search(r"\b(1[89]\d\d|20\d\d)\b", t)
    if m:
        return int(m[1]), None, None
    return None


def scale_set(s: str) -> set:
    """Alle Maßstäbe 1:n inkl. Kurzform '1:200/500' -> {'1:200','1:500'}."""
    t = unicodedata.normalize("NFKC", s).replace(",", ".")
    out = set()
    for m in re.finditer(r"(\d+)\s*:\s*(\d+(?:\.\d+)?)((?:\s*/\s*\d+(?:\.\d+)?)*)", t):
        a = m.group(1)
        for b in [m.group(2)] + re.findall(r"\d+(?:\.\d+)?", m.group(3) or ""):
            out.add(f"{int(a)}:{float(b):g}")
    return out
