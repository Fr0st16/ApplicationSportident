#!/usr/bin/env python3
"""
Constantes partagées entre les modules UI (grille de balises, presets).
Anciennement dupliquées dans ui_parcours.py et ui_lecture_puce.py.
"""

BALISE_MIN = 31
BALISE_MAX = 256
BALISES_TOUTES = list(range(BALISE_MIN, BALISE_MAX + 1))  # 226 balises (31-256)
GRID_COLS = 18

# Presets : nombre de balises - liste (à partir de BALISE_MIN)
PRESETS = {
    10: list(range(31, 41)),
    24: list(range(31, 55)),
    26: list(range(31, 57)),
}
