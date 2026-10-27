"""
Zentrale Konfiguration des Experiments.

Alle Parameter, die in der Hausarbeit im Methodikteil genannt werden,
stehen hier an EINER Stelle. Nach dem Einfrieren (git tag) nicht mehr ändern.
"""
from pathlib import Path

# ------------------------------------------------------------------
# Pfade
# ------------------------------------------------------------------
# Code-Ordner (= GitHub-Repository). Alles Vertrauliche liegt EINE Ebene darüber,
# also außerhalb des Repositories, und kann so nicht versehentlich gepusht werden:
#
#   Hausarbeit/
#   ├── plans/  ground_truth.csv     vertraulich (Originaldaten)
#   ├── arbeitsdaten/                vertraulich (Cache, Rohausgaben) – wird erzeugt
#   └── prompt-design-bauplaene/     dieser Ordner: Code, Prompts, aggregierte Ergebnisse
ROOT = Path(__file__).resolve().parent
PRIVATE = ROOT.parent
PLANS_DIR = PRIVATE / "plans"                  # Originalscans
GT_RAW = PRIVATE / "ground_truth.csv"          # Original-Ground-Truth aus dem Projekt
WORK_DIR = PRIVATE / "arbeitsdaten"
DATA_DIR = WORK_DIR / "data"                   # erzeugt von 01_prepare_data.py
CACHE_DIR = DATA_DIR / "cache"                 # vorverarbeitete Seitenbilder
DOCS_CSV = DATA_DIR / "docs.csv"               # doc_id <-> Datei, Split, Qualität, Layout
GT_CLEAN = DATA_DIR / "ground_truth_clean.csv"
RUNS_DIR = WORK_DIR / "runs"                   # Rohausgaben je Lauf (enthalten Planinhalte!)
PROMPTS_DIR = ROOT / "prompts"
RESULTS_DIR = ROOT / "results"                 # nur aggregierte Zahlen -> darf ins Repo

# ------------------------------------------------------------------
# Modell (lokal via Ollama)
# ------------------------------------------------------------------
OLLAMA_URL = "http://localhost:11434"
MODEL = "qwen3-vl:4b-instruct"             # Hauptmodell (Instruct = ohne Thinking)
# Falls der Tag nicht existiert: "qwen3-vl:4b" und THINK = False setzen.
THINK = None                               # None = Parameter nicht senden; False = Thinking explizit aus

# Deterministische Dekodierung -> reproduzierbare Läufe
OPTIONS = {
    "temperature": 0,
    "seed": 42,
    "num_ctx": 4096,       # reicht für Bild (max. ~2300 Tokens) + Prompt; spart RAM auf 8-GB-Macs
    "num_predict": 512,    # verhindert Endlosschleifen
}
KEEP_ALIVE = "30m"
REQUEST_TIMEOUT_S = 600

# ------------------------------------------------------------------
# Bildverarbeitung
# ------------------------------------------------------------------
CACHE_MAX_SIDE = 8000      # Auflösung der Zwischenspeicherung (Scans sind bis 28.000 px breit)
PDF_DPI = 200
CROP_MAX_SIDE = 1536       # Bildgröße, die beim Extraktionsschritt an das Modell geht
FULL_MAX_SIDE = 1536       # Bildgröße bei Ganzseiten-Input
LOCATE_MAX_SIDE = 1280     # Bildgröße für Stufe 1 (Schriftfeld lokalisieren)

# Fester Ausschnitt aus dem Projekt (DIN EN ISO 7200: Schriftfeld unten rechts)
FIXED_CROP = (0.55, 0.65, 1.0, 1.0)   # (links, oben, rechts, unten) relativ

# Zweistufig: Rand um die vorhergesagte Box und Mindestgröße (relativ zur Seite)
BBOX_PAD = 0.03
BBOX_MIN_SIZE = 0.08

# ------------------------------------------------------------------
# Versuchsbedingungen
# ------------------------------------------------------------------
# prompt: Datei in prompts/   |   input: crop | full | twostage
CONDITIONS = {
    "A_baseline":  {"prompt": "p0_baseline", "input": "crop"},      # Projekt-Prompt (Referenz)
    "B_structured": {"prompt": "p1_structured", "input": "crop"},   # FF1: Prompt-Design
    "C_twostage":  {"prompt": "p1_structured", "input": "twostage"},  # FF2: Prompt-Chaining
    # Kontrolle: trennt "Lokalisieren" von "nur ganze Seite sehen"
    "D_fullpage":  {"prompt": "p1_structured", "input": "full"},
}
LOCATE_PROMPT = "s1_locate"

# ------------------------------------------------------------------
# Datensplit und Evaluation
# ------------------------------------------------------------------
SPLIT_SEED = 42
DEV_PER_QUALITY = 4        # 4 "good" + 4 "average" = 8 Dev-Pläne, Rest = Testset
FIELDS = ["Title", "Date", "ID", "Scale"]
TITLE_MATCH_THRESHOLD = 0.80   # normalisierte Levenshtein-Ähnlichkeit für "Titel korrekt"
ANLS_TAU = 0.5                 # Schwelle aus Biten et al. (2019)
BOOTSTRAP_ITERS = 10000
