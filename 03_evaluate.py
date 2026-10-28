"""Deterministische Evaluation (kein LLM-Judge) eines oder mehrerer Läufe.

  python 03_evaluate.py                         # alle Läufe in arbeitsdaten/runs/, Testset
  python 03_evaluate.py --split dev B_structured__qwen3-vl-4b-instruct__dev1
  python 03_evaluate.py --split all

Regeln je Feld (bei mehreren gültigen GT-Werten zählt der beste):
  Title : NLS (Zeichenebene) ODER Token-F1 (Wortebene) >= TITLE_MATCH_THRESHOLD; zusätzlich ANLS.
          Token-F1 verhindert, dass ein vollständigerer Titel als die GT als falsch zählt.
  ID    : exakte Übereinstimmung nach Normalisierung (ohne Leer-/Trennzeichen); zusätzlich ANLS
  Date  : gleiches Datum nach ISO-Normalisierung (Tag/Monat/Jahr); zusätzlich "Jahr korrekt"
  Scale : mindestens ein vorhergesagter Maßstab ist in der GT enthalten
Kategorien: TP korrekt | TN korrekt leer | FN fehlt | FP halluziniert (GT leer) | WV falscher Wert
"""
from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path

import common
import config as C

FIELD_DE = {"Title": "Titel", "Date": "Datum", "ID": "ID", "Scale": "Maßstab"}


# ------------------------------------------------------------------
# Bewertung eines Feldes
# ------------------------------------------------------------------
def score(field: str, pred, alts: list) -> dict:
    r = {"category": None, "correct": 0, "sim": None, "lenient": None}
    if not alts:
        r["category"] = "TN" if pred is None else "FP"
        r["correct"] = int(pred is None)
        return r
    if pred is None:
        r.update(category="FN", sim=0.0, lenient=0)
        return r

    if field == "Title":
        r["sim"] = max(common.nls(common.norm_text(pred), common.norm_text(a)) for a in alts)
        r["lenient"] = max(common.token_f1(pred, a) for a in alts)   # Token-F1
        ok = max(r["sim"], r["lenient"]) >= C.TITLE_MATCH_THRESHOLD
    elif field == "ID":
        r["sim"] = max(common.nls(common.norm_id(pred), common.norm_id(a)) for a in alts)
        ok = any(common.norm_id(pred) == common.norm_id(a) for a in alts)
    elif field == "Date":
        pd = common.parse_date(pred)
        gds = [common.parse_date(a) for a in alts]
        if pd is None:
            ok = any(common.norm_text(pred) == common.norm_text(a) for a in alts)
        else:
            ok = pd in gds
        r["lenient"] = int(ok or (pd is not None and any(g and g[0] == pd[0] for g in gds)))
    else:  # Scale
        gs = set().union(*(common.scale_set(a) for a in alts))
        ok = bool(common.scale_set(pred) & gs)
    r["category"] = "TP" if ok else "WV"
    r["correct"] = int(ok)
    return r


def anls(sim) -> float:
    return 0.0 if sim is None or sim < C.ANLS_TAU else sim


def mean(xs):
    xs = [x for x in xs if x is not None]
    return sum(xs) / len(xs) if xs else None


# ------------------------------------------------------------------
# Lauf auswerten
# ------------------------------------------------------------------
def load_predictions(run_dir: Path) -> dict:
    f = run_dir / "predictions.jsonl"
    recs = {}
    if f.exists():
        for line in f.read_text(encoding="utf-8").splitlines():
            if line.strip():
                r = json.loads(line)
                recs[r["doc_id"]] = r   # bei Duplikaten gewinnt der letzte Eintrag
    return recs


def evaluate_run(run_dir: Path, docs: list, gt: dict) -> tuple[list, dict]:
    preds = load_predictions(run_dir)
    docs = [d for d in docs if d["doc_id"] in preds]
    rows = []
    for d in docs:
        rec = preds[d["doc_id"]]
        for f in C.FIELDS:
            s = score(f, rec["pred"].get(f), gt[d["doc_id"]][f])
            rows.append({"doc_id": d["doc_id"], "quality": d["quality"],
                         "layout": d.get("layout", ""), "field": f,
                         "gt": " | ".join(gt[d["doc_id"]][f]), "pred": rec["pred"].get(f) or "",
                         **s})
    m = {"run": run_dir.name, "n_docs": len(docs)}
    if not docs:
        return rows, m
    for f in C.FIELDS:
        fr = [r for r in rows if r["field"] == f]
        cats = defaultdict(int)
        for r in fr:
            cats[r["category"]] += 1
        n_empty = cats["TN"] + cats["FP"]
        m[f] = {
            "acc": mean([r["correct"] for r in fr]), **{k: cats[k] for k in
                                                       ("TP", "TN", "FN", "FP", "WV")},
            "halluc_rate": cats["FP"] / n_empty if n_empty else None,
            "miss_rate": cats["FN"] / (len(fr) - n_empty) if len(fr) > n_empty else None,
        }
        if f in ("Title", "ID"):
            nonempty = [r for r in fr if r["category"] not in ("TN", "FP")]
            m[f]["anls"] = mean([anls(r["sim"]) for r in nonempty])
            m[f]["mean_nls"] = mean([r["sim"] for r in nonempty])
        if f == "Date":
            m[f]["year_acc"] = mean([r["lenient"] if r["lenient"] is not None else r["correct"]
                                     for r in fr])
    m["macro_acc"] = mean([m[f]["acc"] for f in C.FIELDS])
    by_doc = defaultdict(list)
    for r in rows:
        by_doc[r["doc_id"]].append(r["correct"])
    m["docs_all_correct"] = sum(all(v) for v in by_doc.values())
    tn_fp = sum(m[f]["TN"] + m[f]["FP"] for f in C.FIELDS)
    m["halluc_rate"] = sum(m[f]["FP"] for f in C.FIELDS) / tn_fp if tn_fp else None
    recs = [preds[d["doc_id"]] for d in docs]
    m["valid_rate"] = mean([int(r["valid"]) for r in recs])
    m["fallback_rate"] = mean([int(r.get("fallback", False)) for r in recs])
    m["errors"] = sum(1 for r in recs if r.get("error"))
    m["sec_per_doc"] = mean([r["seconds"] for r in recs])
    return rows, m


def pct(x) -> str:
    return "–" if x is None else f"{100 * x:.1f}"


# ------------------------------------------------------------------
# Main
# ------------------------------------------------------------------
if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("runs", nargs="*", help="Laufnamen (Standard: alle in arbeitsdaten/runs/)")
    ap.add_argument("--split", default="test", choices=["all", "dev", "test"])
    ap.add_argument("--errors", action="store_true", help="alle Fehler einzeln auflisten")
    args = ap.parse_args()

    run_dirs = ([common.run_dir(r) for r in args.runs]
                or sorted(p for p in C.RUNS_DIR.iterdir() if p.is_dir()))
    docs, gt = common.load_docs(args.split), common.load_gt()
    C.RESULTS_DIR.mkdir(exist_ok=True)

    summary, breakdown = [], []
    for rd in run_dirs:
        rows, m = evaluate_run(rd, docs, gt)
        if not m["n_docs"]:
            continue
        if m["n_docs"] < len(docs):
            print(f"[Warnung] {rd.name}: nur {m['n_docs']}/{len(docs)} Dokumente vorhanden")
        common.write_csv(rd / f"eval_{args.split}.csv", rows, list(rows[0].keys()))
        if args.errors:
            print(f"\nFehler in {rd.name}:")
            for r in rows:
                if not r["correct"]:
                    print(f"  {r['doc_id']}  {r['field']:<6} {r['category']}  "
                          f"GT: {r['gt'][:60] or '(leer)'}  |  Modell: {r['pred'][:60] or '(leer)'}")
        (rd / f"metrics_{args.split}.json").write_text(json.dumps(m, indent=2), "utf-8")
        summary.append(m)
        for key in ("quality", "layout"):
            for val in sorted({r[key] for r in rows if r[key]}):
                sub = [r for r in rows if r[key] == val]
                b = {"run": rd.name, "group": key, "value": val,
                     "n_docs": len({r["doc_id"] for r in sub}),
                     "macro_acc": mean([mean([r["correct"] for r in sub if r["field"] == f])
                                        for f in C.FIELDS])}
                for f in C.FIELDS:
                    b[f] = mean([r["correct"] for r in sub if r["field"] == f])
                breakdown.append(b)

    if not summary:
        raise SystemExit(f"Keine Vorhersagen für Split '{args.split}' gefunden.")

    # ---- Konsolentabelle + Markdown ----
    hdr = ["Lauf", "n", "Titel", "Datum", "ID", "Maßstab", "Makro", "ANLS-T", "Halluz.",
           "alle 4", "JSON ok", "s/Plan"]
    lines = ["| " + " | ".join(hdr) + " |", "|" + "---|" * len(hdr)]
    for m in summary:
        lines.append("| " + " | ".join([
            m["run"], str(m["n_docs"]), *(pct(m[f]["acc"]) for f in C.FIELDS), pct(m["macro_acc"]),
            pct(m["Title"]["anls"]), pct(m["halluc_rate"]), str(m["docs_all_correct"]),
            pct(m["valid_rate"]),
            "–" if m["sec_per_doc"] is None else f"{m['sec_per_doc']:.0f}"]) + " |")
    md = "\n".join(lines)
    print(f"\nErgebnisse (Split: {args.split}, Angaben in %)\n" + md)

    # ---- Dateien für die Hausarbeit ----
    (C.RESULTS_DIR / f"summary_{args.split}.md").write_text(md + "\n", "utf-8")
    flat = []
    for m in summary:
        row = {k: v for k, v in m.items() if not isinstance(v, dict)}
        for f in C.FIELDS:
            for k, v in m[f].items():
                row[f"{f}_{k}"] = v
        flat.append(row)
    common.write_csv(C.RESULTS_DIR / f"summary_{args.split}.csv", flat, list(flat[0].keys()))
    if breakdown:
        common.write_csv(C.RESULTS_DIR / f"breakdown_{args.split}.csv", breakdown,
                         list(breakdown[0].keys()))

    tex = [r"\begin{table}[htb]", r"\centering",
           r"\caption{Feldgenauigkeit je Bedingung in \%% (Split %s, $n=%d$)}" % (args.split, summary[0]["n_docs"]),
           r"\label{tab:results}", r"\begin{tabular}{lrrrrrr}", r"\toprule",
           r"Bedingung & Titel & Datum & ID & Maßstab & Makro & Halluz. \\", r"\midrule"]
    for m in summary:
        name = m["run"].split("__")[0].replace("_", r"\_")
        tex.append(" & ".join([name, *(pct(m[f]["acc"]) for f in C.FIELDS), pct(m["macro_acc"]),
                               pct(m["halluc_rate"])]) + r" \\")
    tex += [r"\bottomrule", r"\end{tabular}", r"\end{table}"]
    (C.RESULTS_DIR / f"table_{args.split}.tex").write_text("\n".join(tex) + "\n", "utf-8")
    print(f"\nGespeichert in {common.show(C.RESULTS_DIR)}/ "
          f"(summary_{args.split}.csv/.md, breakdown_{args.split}.csv, table_{args.split}.tex)")
