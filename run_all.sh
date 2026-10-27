#!/usr/bin/env bash
# Hauptexperiment: alle vier Bedingungen auf allen Plänen, danach Auswertung (Testset).
# Start:  caffeinate -i ./run_all.sh   (verhindert, dass der Mac einschläft)
set -e
cd "$(dirname "$0")"
source .venv/bin/activate
for c in A_baseline B_structured C_twostage D_fullpage; do
  python 02_run_extraction.py --condition "$c"
done
python 03_evaluate.py --split test
M=qwen3-vl-4b-instruct
python 04_compare.py A_baseline__$M B_structured__$M    # FF1
python 04_compare.py B_structured__$M C_twostage__$M    # FF2
python 04_compare.py C_twostage__$M D_fullpage__$M      # Kontrolle
python 05_plot.py --split test
