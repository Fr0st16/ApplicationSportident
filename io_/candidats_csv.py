#!/usr/bin/env python3
"""
Parseur du fichier CSV liste de candidats (num puce -> nom/prénom/catégorie).

Déplacé depuis ui_lecture_puce.py, où cette fonction ne dépendait déjà pas
de Tkinter ni de l'état de la classe AppLecturePuce.
"""
import csv
import unicodedata


def parse_candidate_csv(chemin):
    """Parse a candidate CSV file (semicolon-delimited) and return dict[num] = {...}.

    Tries common encodings and normalizes header names to detect columns.
    """

    def _normaliser(s):
        """Minuscule, sans accents ni espaces, pour comparer des noms de colonnes."""
        return unicodedata.normalize("NFD", s).encode("ascii", "ignore").decode().lower().strip()

    candidats = {}
    succes = False
    erreur = "Encodage du fichier non reconnu."

    for encoding in ("utf-8-sig", "latin-1", "cp1252"):
        try:
            with open(chemin, newline="", encoding=encoding) as f:
                reader = csv.DictReader(f, delimiter=";")
                rows = list(reader)
            fieldnames = reader.fieldnames or []

            def find_col(noms_cibles, fns=fieldnames):
                """Retourne le nom de colonne réel correspondant au premier alias trouvé."""
                for cible in noms_cibles:
                    for fn in fns:
                        if _normaliser(fn) == cible:
                            return fn
                return None

            col_puce   = find_col(["puces", "puce", "chip", "card", "numero", "numero puce"])
            col_prenom = find_col(["prenom", "firstname", "first name"])
            col_nom    = find_col(["nom", "name", "lastname", "last name"])
            col_cat    = find_col(["categorie", "category"])
            col_infos  = find_col(["infos", "info", "groupe", "group"])

            if col_puce is None:
                erreur = "Colonne 'Puces' introuvable dans le fichier CSV."
                succes = False
                break

            for row in rows:
                try:
                    num = int(str(row.get(col_puce, "")).strip())
                except (ValueError, TypeError):
                    continue
                prenom    = str(row.get(col_prenom, "") or "").strip() if col_prenom else ""
                nom_fam   = str(row.get(col_nom,    "") or "").strip() if col_nom    else ""
                categorie = str(row.get(col_cat,    "") or "").strip() if col_cat    else ""
                infos_val = str(row.get(col_infos,  "") or "").strip() if col_infos  else ""
                candidats[num] = {
                    "prenom":    prenom,
                    "nom":       nom_fam,
                    "categorie": categorie,
                    "infos":     infos_val,
                }
            succes = True
            break
        except UnicodeDecodeError:
            continue
        except Exception as e:
            erreur = str(e)
            break

    if not succes:
        raise ValueError(erreur)
    return candidats
