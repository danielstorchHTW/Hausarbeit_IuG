
# Prompt-Design für die Metadatenextraktion aus historischen U-Bahn-Bauplänen

Code zur Hausarbeit „Prompt-Design für die lokale Metadatenextraktion aus historischen U-Bahn-Bauplänen“ (IuG, HTW Berlin).

Ein kleines, lokal laufendes Vision-Language-Modell (`qwen3-vl:4b-instruct` über Ollama) liest
**Titel, Datum, Plannummer und Maßstab** aus gescannten Bauplänen der Berliner U-Bahn aus.
Verglichen werden vier Varianten:

| | Prompt | Bildausschnitt |
|---|---|---|
| A | Prompt aus dem Projekt (Freitext) | fest, unten rechts |
| B | strukturierter Prompt (JSON) | fest, unten rechts |
| C | Prompt-Kette: erst Schriftfeld suchen, dann B | vom Modell gewählt |
| D | strukturierter Prompt (JSON) | ganze Seite |

Die Prompts stehen in `prompts/`, ihre Entwicklung ist in `prompts/CHANGELOG.md` beschrieben.

## Daten

Die Baupläne und die Ground Truth sind **vertraulich** (kritische Infrastruktur) und deshalb
**nicht** in diesem Repository. Der Code erwartet sie eine Ordnerebene höher:

```
Hausarbeit/
├── plans/                     Scans (nicht im Repo)
├── ground_truth.csv           Ground Truth (nicht im Repo)
├── arbeitsdaten/              wird vom Code erzeugt (nicht im Repo)
└── prompt-design-bauplaene/   dieses Repository
```

## Ausführen

Voraussetzungen: Python ≥ 3.10 und [Ollama](https://ollama.com). Getestet auf einem MacBook Air M1 (8 GB).

```bash
# Ollama in einem eigenen Terminal starten (die Variablen sparen Speicher)
OLLAMA_FLASH_ATTENTION=1 OLLAMA_KV_CACHE_TYPE=q8_0 ollama serve

# Umgebung einrichten
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
ollama pull qwen3-vl:4b-instruct

python 00_check_setup.py      # prüft die Umgebung
python 01_prepare_data.py     # Pseudonyme, Split 8 Entwicklung / 34 Test, Bild-Cache
python 01b_annotate_layout.py # Lage des Schriftfelds je Plan manuell erfassen
./run_all.sh                  # alle vier Varianten + Auswertung (ca. 2 Stunden)
```

## Dateien

| Datei | Aufgabe |
|---|---|
| `config.py` | alle Einstellungen (Modell, Bildgrößen, Varianten) |
| `common.py` | Hilfsfunktionen |
| `02_run_extraction.py` | führt eine Variante aus |
| `03_evaluate.py` | bewertet die Ausgaben mit festen Regeln (ohne LLM-Bewerter) |
| `04_compare.py` | vergleicht zwei Varianten paarweise (inkl. Bootstrap-Konfidenzintervall) |
| `05_plot.py` | erstellt die Abbildung |
| `results/` | Ergebnistabellen und Abbildung (nur Kennzahlen, keine Planinhalte) |
| `results/split.csv` | Zuordnung der Pläne (Pseudonyme) zu Entwicklungs- und Testset, mit Qualität und Lage des Schriftfelds |

## Hinweis zur KI-Nutzung

Der Code wurde mit Unterstützung von Claude (Anthropic) erstellt und überarbeitet.
Versuchsaufbau, Durchführung, Annotation und Auswertung der Ergebnisse lagen beim Autor;
alle Ergebnisse in `results/` stammen aus eigenen Läufen.
