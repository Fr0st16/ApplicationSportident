#!/usr/bin/env python3
"""
Parseurs de fichiers de définition de parcours (TSV, CSV, XML/TXT OCAD).

Déplacés depuis ui_parcours.py, où ils vivaient comme @staticmethod de
AppParcours alors qu'ils n'utilisent jamais `self` : main.py les appelait
déjà directement via `AppParcours._parser_xxx(...)`, uniquement pour parser
un fichier, sans jamais construire l'UI. Ce sont maintenant de simples
fonctions, sans dépendance à Tkinter.
"""
import os
import csv as _csv_module
import re
import xml.etree.ElementTree as ET

from core.constants import BALISE_MIN, BALISE_MAX


def parser_tsv(chemin):
    """Lit un fichier .tsv parcours et retourne {nom, balises, ordre}."""
    nom, balises, ordre = "", [], False
    with open(chemin, newline="", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            if line.startswith("#"):
                content = line[1:].strip()
                if content.lower().startswith("ordre:"):
                    val = content.split(":", 1)[1].strip().lower()
                    ordre = val in ("oui", "yes", "true", "1")
                elif not nom:
                    nom = content
            elif line.isdigit():
                balises.append(int(line))
    # Dédupliquer en préservant l'ordre
    seen, balises_uniques = set(), []
    for b in balises:
        if b not in seen:
            seen.add(b)
            balises_uniques.append(b)
    return {
        "nom": nom or os.path.splitext(os.path.basename(chemin))[0],
        "balises": balises_uniques,
        "ordre": ordre,
    }


def parser_csv_intelligent(chemin):
    """
    Analyse intelligente d'un fichier CSV quelconque.
    Détecte le séparateur, cherche un nom de parcours et collecte
    toutes les valeurs entières valides (BALISE_MIN-BALISE_MAX) dans l'ordre de lecture.
    Retourne (nom: str, balises: list[int]).
    """
    # 1. Détecter le séparateur le plus fréquent
    with open(chemin, encoding="utf-8-sig", errors="replace") as f:
        sample = f.read(8192)
    sep_counts = {sep: sample.count(sep) for sep in (";", ",", "\t", "|")}
    sep = (
        max(sep_counts, key=sep_counts.get) if max(sep_counts.values()) > 0 else ","
    )
    # 2. Lire toutes les lignes
    with open(chemin, newline="", encoding="utf-8-sig", errors="replace") as f:
        rows = list(_csv_module.reader(f, delimiter=sep))
    if not rows:
        return os.path.splitext(os.path.basename(chemin))[0], []
    # 3. Chercher un nom de parcours
    nom = os.path.splitext(os.path.basename(chemin))[0]
    _mots_cles_nom = {"nom", "name", "parcours", "course", "titre", "title"}
    _mots_cles_col = {
        "balise",
        "beacon",
        "station",
        "temps",
        "time",
        "heure",
        "passage",
        "départ",
        "arrivée",
        "start",
        "finish",
        "participant",
        "puce",
        "chip",
        "numéro",
        "numero",
    }
    header = [c.strip().lower() for c in rows[0]]
    nom_trouve = False
    # Cas 1 : format clé-valeur -> rows[0] = ["Nom", "Mon Parcours"]
    if not nom_trouve and len(rows[0]) >= 2:
        key = rows[0][0].strip().lower()
        if key in _mots_cles_nom:
            candidate = rows[0][1].strip()
            if candidate:
                nom = candidate
                nom_trouve = True
    # Cas 2 : format tabulaire -> en-têtes en ligne 0, valeurs en ligne 1
    if not nom_trouve:
        for i, h in enumerate(header):
            if h in _mots_cles_nom and len(rows) > 1 and i < len(rows[1]):
                candidate = rows[1][i].strip()
                if candidate:
                    nom = candidate
                    nom_trouve = True
                    break
    # Cas 3 : première cellule non-numérique et non-générique
    if not nom_trouve:
        first_cell = rows[0][0].strip() if rows[0] else ""
        if first_cell and first_cell.lower() not in _mots_cles_col:
            try:
                int(first_cell)
            except ValueError:
                nom = first_cell
    # 4. Collecter toutes les valeurs entières valides dans l'ordre de lecture
    balises_vues = []
    balises_set = set()
    for row in rows:
        for cell in row:
            cell = cell.strip()
            if not cell:
                continue
            try:
                val = int(float(cell)) if "." in cell else int(cell)
                if BALISE_MIN <= val <= BALISE_MAX and val not in balises_set:
                    balises_set.add(val)
                    balises_vues.append(val)
            except (ValueError, OverflowError):
                pass
    return nom, balises_vues


def parser_ocad_xml(chemin):
    """
    Parse un fichier IOF XML OCAD (v2.0.3 ou v3.0).
    Gère l'absence de namespace (exports OCAD classiques) et la structure
    <CourseVariation> de certaines versions.
    Retourne une liste de dicts {nom, balises, ordre}.
    """
    tree = ET.parse(chemin)
    root = tree.getroot()
    # Extraire le namespace depuis le tag racine ({uri}LocalName)
    m = re.match(r"\{(.+?)\}", root.tag)
    ns_uri = m.group(1) if m else ""

    def tag(name):
        """Préfixe un nom de balise XML par le namespace détecté, si besoin."""
        return f"{{{ns_uri}}}{name}" if ns_uri else name
    if "3.0" in ns_uri:
        version = 3
    elif "2.0" in ns_uri:
        version = 2
    else:
        # Pas de namespace : lire <IOFVersion version="..."/>
        iof_el = root.find(tag("IOFVersion"))
        if iof_el is not None:
            v = iof_el.get("version", "")
            version = 3 if v.startswith("3") else 2
        elif root.find(".//CourseControl") is not None:
            version = 3
        else:
            version = 2
    lots = []
    if version == 3:
        for course in root.iter(tag("Course")):
            name_el = course.find(tag("Name"))
            nom = (
                name_el.text.strip()
                if name_el is not None and name_el.text
                else "Parcours"
            )
            balises = []
            for cc in course.findall(tag("CourseControl")):
                if cc.get("type", "Control") in ("Start", "Finish", "MapIssue"):
                    continue
                ctrl = cc.find(tag("Control"))
                if ctrl is None:
                    continue
                id_el = ctrl.find(tag("Id"))
                if id_el is None or not id_el.text:
                    continue
                try:
                    num = int(id_el.text.strip())
                    if BALISE_MIN <= num <= BALISE_MAX:
                        balises.append(num)
                except ValueError:
                    pass
            if balises:
                lots.append({"nom": nom, "balises": balises, "ordre": True})
    else:
        # IOF XML v2 (format OCAD classique) :
        # Chaque <Course> contient un ou plusieurs <CourseVariation> avec des
        # <CourseControl> (<Sequence> + <ControlCode>).
        # L'ordre OCAD est toujours obligatoire.
        for course in root.iter(tag("Course")):
            name_el = course.find(tag("CourseName"))
            nom = (
                name_el.text.strip()
                if name_el is not None and name_el.text
                else "Parcours"
            )
            pairs = []  # liste de (sequence, code)
            for cc in course.iter(tag("CourseControl")):
                code_el = cc.find(tag("ControlCode"))
                seq_el = cc.find(tag("Sequence"))
                if code_el is None or not code_el.text:
                    continue
                try:
                    num = int(code_el.text.strip())
                    if not (BALISE_MIN <= num <= BALISE_MAX):
                        continue
                    seq = (
                        int(seq_el.text.strip())
                        if seq_el is not None and seq_el.text
                        else 0
                    )
                    pairs.append((seq, num))
                except ValueError:
                    pass
            if pairs:
                pairs.sort(key=lambda x: x[0])
                balises = [num for _, num in pairs]
                lots.append({"nom": nom, "balises": balises, "ordre": True})
    # (fichier contenant uniquement la liste des balises disponibles sur le terrain)
    if not lots:
        balises, seen = [], set()
        for ctrl in root.iter(tag("Control")):
            code_el = ctrl.find(tag("ControlCode"))
            if code_el is None or not code_el.text:
                continue
            try:
                num = int(code_el.text.strip())
                if BALISE_MIN <= num <= BALISE_MAX and num not in seen:
                    seen.add(num)
                    balises.append(num)
            except ValueError:
                pass
        if balises:
            nom_f = os.path.splitext(os.path.basename(chemin))[0]
            lots.append(
                {
                    "nom": nom_f,
                    "balises": balises,
                    "ordre": False,
                    "_fallback": True,
                }
            )
    return lots


def parser_ocad_txt(chemin):
    """
    Parse un fichier 'Export Courses Text' OCAD.
    Format : Nom\\tLongueur\\tDéniv\\tNbCtrl\\tS1-31-42-53-...-F1
    Retourne une liste de dicts {nom, balises, ordre}.
    """
    lines = []
    for encoding in ("utf-8-sig", "latin-1", "cp1252"):
        try:
            with open(chemin, encoding=encoding) as f:
                lines = f.readlines()
            break
        except UnicodeDecodeError:
            continue
    lots = []
    for line in lines:
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split("\t")
        if len(parts) < 2:
            continue
        nom = parts[0].strip()
        # La séquence de balises est toujours dans la dernière colonne
        seq_str = parts[-1].strip()
        balises = []
        for token in seq_str.split("-"):
            token = token.strip()
            try:
                num = int(token)
                if BALISE_MIN <= num <= BALISE_MAX:
                    balises.append(num)
            except ValueError:
                pass  # Ignorer S1, F1, et distances
        if balises:
            lots.append({"nom": nom, "balises": balises, "ordre": True})
    return lots


def parser_lot_tsv(chemin):
    """Lit un TSV multi-parcours. Retourne list[dict{nom, balises, ordre}]."""
    lots = []
    current = None
    with open(chemin, newline="", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            if line.startswith("#"):
                content = line[1:].strip()
                if content.lower().startswith("ordre:"):
                    if current:
                        val = content.split(":", 1)[1].strip().lower()
                        current["ordre"] = val in ("oui", "yes", "true", "1")
                else:
                    current = {"nom": content, "balises": [], "ordre": False}
                    lots.append(current)
            elif line.isdigit():
                if current is None:
                    current = {
                        "nom": os.path.splitext(os.path.basename(chemin))[0],
                        "balises": [],
                        "ordre": False,
                    }
                    lots.append(current)
                current["balises"].append(int(line))
    for p in lots:
        seen, uniq = set(), []
        for b in p["balises"]:
            if b not in seen:
                seen.add(b)
                uniq.append(b)
        p["balises"] = uniq
    return lots


def parser_lot_csv(chemin):
    """Lit un CSV multi-parcours (format : Nom;Ordre;Balise 1;...). Retourne list[dict]."""
    with open(chemin, encoding="utf-8-sig", errors="replace") as f:
        sample = f.read(4096)
    sep_counts = {sep: sample.count(sep) for sep in (";", ",", "\t", "|")}
    sep = (
        max(sep_counts, key=sep_counts.get) if max(sep_counts.values()) > 0 else ","
    )
    with open(chemin, newline="", encoding="utf-8-sig", errors="replace") as f:
        rows = list(_csv_module.reader(f, delimiter=sep))
    if not rows:
        return []
    header = [c.strip().lower() for c in rows[0]]
    has_header = header and header[0] in ("nom", "name", "parcours", "course")
    data_rows = rows[1:] if has_header else rows
    lots = []
    for row in data_rows:
        if not row or not row[0].strip():
            continue
        nom = row[0].strip()
        ordre = len(row) > 1 and row[1].strip().lower() in (
            "oui",
            "yes",
            "true",
            "1",
        )
        balises = []
        for cell in row[2:]:
            cell = cell.strip()
            if not cell:
                continue
            try:
                val = int(cell)
                if BALISE_MIN <= val <= BALISE_MAX:
                    balises.append(val)
            except ValueError:
                pass
        if balises:
            lots.append({"nom": nom, "balises": balises, "ordre": ordre})
    return lots
