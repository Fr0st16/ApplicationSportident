#!/usr/bin/env python3
"""
Génération et écriture de l'export CSV des pointages.

Déplacé depuis ui/lecture_puce.py (_count_max_punches, _build_csv_rows) et
ui/app_main.py (_exporter_tous, qui dupliquait l'en-tête et la boucle
d'écriture du fichier). Fonctions pures : prennent les données lues
(card_data, noms, parcours) en paramètres au lieu de dépendre de `self`.
"""
import csv
from datetime import datetime

from core.constants import BALISE_MIN, BALISE_MAX
from core.validation import evaluer_ordre, statut_balise

CSV_HEADER_BASE = [
    "Numéro puce", "Participant", "Parcours", "Nb postes", "Passage",
    "Départ", "Arrivée", "Temps course",
]


def _fmt_time(val):
    if val is None:
        return ""
    if isinstance(val, datetime):
        return val.strftime("%d/%m/%Y %H:%M:%S")
    return str(val)


def _get_punch_statuses(punches_terrain, parcours):
    """Statut ('ok'/'bad') de chaque pointage terrain vis-à-vis d'un parcours."""
    if not parcours:
        return [None] * len(punches_terrain)
    ordre_valide = ordre_invalide = None
    if parcours.get("ordre"):
        _, ordre_valide, ordre_invalide = evaluer_ordre(punches_terrain, parcours["balises"])
    return [
        "ok" if statut_balise(p[0], parcours, ordre_valide, ordre_invalide) == "ok" else "bad"
        for p in punches_terrain
    ]


def count_max_punches(card_data):
    """Nombre max de pointages terrain sur toutes les puces d'un card_data."""
    max_p = 0
    for passages in card_data.values():
        for data in passages:
            n = len([p for p in data.get("punches", []) if BALISE_MIN <= p[0] <= BALISE_MAX])
            if n > max_p:
                max_p = n
    return max_p


def csv_header(max_punches):
    header = list(CSV_HEADER_BASE)
    for i in range(1, max_punches + 1):
        header += [f"Balise {i}", f"Temps {i}"]
    return header


def build_csv_rows(card_data, noms, parcours, max_punches):
    """Génère les lignes CSV pour toutes les puces d'un card_data.

    Colonnes : Numéro puce | Participant | Parcours | Nb postes | Passage |
               Départ | Arrivée | Temps course | [Balise i | Temps i]...

    Pour un parcours défini : n'exporte que les balises effectivement pointées,
    triées par numéro croissant. Si une balise pointée n'appartient pas au
    parcours attendu (ou est hors-séquence en mode ordre), la colonne temps
    contiendra "PM" (poste manquant).
    """
    parcours_nom = parcours["nom"] if parcours else "Lecture libre"
    parcours_set = set(parcours.get("balises", [])) if parcours else set()
    nb_postes    = len(parcours["balises"]) if parcours else ""
    rows = []
    for card_number, passages in card_data.items():
        nom = noms.get(card_number, "")
        for passage_num, data in enumerate(passages, start=1):
            punches = [
                p for p in data.get("punches", [])
                if BALISE_MIN <= p[0] <= BALISE_MAX
            ]
            # Dédupliquer : garder le dernier pointage pour chaque balise
            last_punch = {}
            for p in punches:
                last_punch[p[0]] = p[1]

            # Statuts des pointages (utile en mode 'ordre') — on garde le statut
            # correspondant à la dernière occurrence de chaque balise.
            punch_status_by_code = {}
            if parcours:
                statuses = _get_punch_statuses(punches, parcours)
                for (p, st) in zip(punches, statuses):
                    punch_status_by_code[p[0]] = st

            start  = data.get("start")
            finish = data.get("finish")
            if isinstance(start, datetime) and isinstance(finish, datetime):
                delta    = finish - start
                total_s  = int(delta.total_seconds())
                h, rem   = divmod(abs(total_s), 3600)
                m, s     = divmod(rem, 60)
                temps_course = f"{h:02d}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"
            else:
                temps_course = ""

            row = [
                card_number,
                nom,
                parcours_nom,
                nb_postes,
                passage_num,
                _fmt_time(start),
                _fmt_time(finish),
                temps_course,
            ]

            # Utiliser uniquement les balises réellement pointées, triées numériquement
            balises_pointes = sorted(last_punch.keys())
            for b in balises_pointes:
                row.append(str(b))
                if parcours and b not in parcours_set:
                    row.append("PM")
                # En mode 'ordre', si le pointage est hors-séquence, indiquer PM
                elif parcours and parcours.get("ordre") and punch_status_by_code.get(b) != "ok":
                    row.append("PM")
                else:
                    t = last_punch.get(b)
                    row.append(t.strftime("%H:%M:%S") if t else "")

            # Compléter pour atteindre max_punches
            row += [""] * ((max_punches - len(balises_pointes)) * 2)

            rows.append(row)
    return rows


def write_csv(chemin, max_punches, rows):
    """Écrit l'en-tête et les lignes fournies dans un fichier CSV (';', utf-8-sig)."""
    with open(chemin, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f, delimiter=";")
        writer.writerow(csv_header(max_punches))
        for row in rows:
            writer.writerow(row)
