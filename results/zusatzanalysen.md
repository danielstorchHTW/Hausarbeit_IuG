# Zusatzanalysen (Testset, n = 34 Pläne)

## Paarweise Vergleiche (Makro-Differenz in Pp., 95%-Bootstrap-KI, Pläne nur erste/nur zweite richtig)
| Vergleich | Diff | KI | je Feld |
|---|---|---|---|
| A' -> A | +0.7 | [-5.1; +5.9] | Title 1/5, Date 4/2, ID 2/2, Scale 1/0 |
| A -> B | +7.4 | [+2.9; +12.5] | Title 1/8, Date 2/3, ID 0/2, Scale 0/0 |
| B -> C | +1.5 | [-8.1; +11.8] | Title 3/8, Date 6/4, ID 8/4, Scale 3/6 |
| C -> D | -5.1 | [-16.2; +6.6] | Title 11/4, Date 10/2, ID 0/9, Scale 6/5 |
| A' -> B | +8.1 | [+1.5; +14.7] | Title 1/12, Date 3/2, ID 2/4, Scale 1/0 |
| A' -> C | +9.6 | [-1.5; +19.9] | Title 2/18, Date 6/3, ID 7/5, Scale 3/5 |

## Laufzeit je Plan in s
| Bedingung | Mittel | Median | Maximum |
|---|---|---|---|
| A | 21.0 | 19.8 | 40 |
| B | 31.4 | 30.6 | 53 |
| C | 55.6 | 51.8 | 84 |
| D | 71.1 | 36.6 | 955 |

## Makro-Genauigkeit nach Lage des Schriftfelds in %
| Bedingung | unten rechts | anderswo/ohne |
|---|---|---|
| A' | 46.6 (n=29) | 20.0 (n=5) |
| A | 47.4 (n=29) | 20.0 (n=5) |
| B | 56.0 (n=29) | 20.0 (n=5) |
| C | 51.7 (n=29) | 55.0 (n=5) |
| D | 42.2 (n=29) | 75.0 (n=5) |

## Falsche IDs: andere Nummer (NLS < 0,3) / Variante der richtigen (NLS >= 0,3)
- A': 15 falsch, davon 8 andere Nummer, 7 Variante (davon 3 mit NLS >= 0,8)
- A: 17 falsch, davon 8 andere Nummer, 9 Variante (davon 4 mit NLS >= 0,8)
- B: 17 falsch, davon 10 andere Nummer, 7 Variante (davon 2 mit NLS >= 0,8)
- C: 21 falsch, davon 14 andere Nummer, 7 Variante (davon 3 mit NLS >= 0,8)
- D: 15 falsch, davon 3 andere Nummer, 12 Variante (davon 6 mit NLS >= 0,8)

## Titel
- A ohne Titel: 8 Pläne, davon 5 mit Schriftfeld nicht unten rechts; in B danach: TP 0, WV 6, FN 2
- Nur B richtig: 8 Pläne, davon 8 unten rechts; Kategorie in A: WV
- B auf Plänen mit Schriftfeld nicht unten rechts: TP 0, WV 3, FN 2

## Determinismus (Testlauf vs. Entwicklungslauf, 8 Entwicklungspläne)
- A: 8/8 identische Ausgaben (gleiche Prompt-Prüfsumme: True)
- B: 8/8 identische Ausgaben (gleiche Prompt-Prüfsumme: True)
- C: 8/8 identische Ausgaben (gleiche Prompt-Prüfsumme: True)
