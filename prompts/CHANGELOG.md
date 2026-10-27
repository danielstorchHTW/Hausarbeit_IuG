# Prompt-Entwicklung (nur auf dem Dev-Set, 8 Pläne)

Die Prompt-Versionen sind für den Anhang der Hausarbeit dokumentiert. `p0_baseline.txt` bleibt
unverändert (Originalprompt aus dem Projekt).

## v1 (dev1)
Erste strukturierte Fassung: Rolle, Felddefinitionen, Null-Regel, JSON-Schema (`history/*_v1.txt`).

Dev-Ergebnis (Makro-Genauigkeit): A 31,2 % · B 34,4 % · C 56,2 %

Beobachtete Fehlerarten auf dem Dev-Set:
- Titel: Beschriftungen von Bauteilen oder Ansichten ("Schnitt D-D", "vorhandene Bebauung") sowie
  Firmen-, Orts- und Datumsvermerke ("Berlin, den …, … Gesellschaft") wurden als Titel ausgegeben.
- ID: Bei C wurden lange Ziffernfolgen bzw. andere Nummern gewählt. Bei A/B (fester Ausschnitt)
  lagen die IDs nahe an der GT (einzelne Ziffern falsch), d. h. die Plannummer steht teils am Blattrand.
- Datum: ein ID-ähnlicher String wurde als Datum ausgegeben.
- Maßstab: eine Flächenrechnung ("1:52 x 87 = 132 m²") wurde als Maßstab ausgegeben.

## v2 (dev2)
- title: Negativliste erweitert (Firmen/Behörden, "Ort, den Datum", Bauteil-/Ansichtsbeschriftungen).
- date: Abgrenzung zu Nummern mit Bindestrich.
- id: Formatbeschreibung der Archiv-/Plannummer (aus dem Dev-Set abgeleitet), mögliche Lage als
  Stempel am Rand, Rückfall auf Blattnummer, Negativliste (lange Ziffernfolgen), Hinweis "jede Ziffer prüfen".
- scale: nur echte Maßstabsangaben.
- s1_locate: Box soll eine neben dem Schriftfeld stehende Plannummer mit einschließen.

Dev-Ergebnis (Makro-Genauigkeit, Titel-Metrik inkl. Token-F1; v1-Werte neu berechnet):

| Bedingung | v1 | v2 |
|---|---|---|
| A (unverändert) | 31,2 % | – |
| B | 37,5 % | 40,6 % |
| C | 59,4 % | 56,2 % |

Beobachtungen:
- B: ID-Feld verbessert (37,5 → 50,0 %). Titelfehler bleiben bestehen, wenn das Schriftfeld
  außerhalb des festen Ausschnitts liegt (kein Prompt-Problem, sondern ein Input-Problem).
- C: Maßstab verbessert (75,0 → 87,5 %), Datum und ID bei einem Plan verschlechtert. Der
  erweiterte Lokalisierungsbereich vergrößert den Ausschnitt (38 → 55 s pro Plan).
- Verbleibende ID-Fehler sind überwiegend Lesefehler einzelner Zeichen (z. B. 0/1-Vertauschung,
  E→Z), d. h. Grenzen der Texterkennung des Modells, die sich per Prompt nicht beheben lassen.

## Entscheidung: v2 eingefroren
Die Unterschiede zwischen v1 und v2 betragen jeweils ein einzelnes Feld (1 von 32) und liegen damit im
Rauschbereich des kleinen Dev-Sets. Um eine Überanpassung an die 8 Dev-Pläne zu vermeiden, wurde die
Prompt-Entwicklung nach zwei Runden beendet. Gewählt wurde v2, weil die Regeln inhaltlich begründet
sind (Fehlerarten statt Einzelfälle) und B profitiert, während C gleichwertig bleibt.
Danach keine Änderungen an den Prompts. Die Prompt-Prüfsummen in `config.json` jedes Laufs belegen, dass dev2 und alle Testläufe denselben Prompt verwenden.
