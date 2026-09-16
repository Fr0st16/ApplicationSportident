#!/usr/bin/env python3
"""
Algorithme de validation d'un parcours (mode "ordre" ou mode "libre").

Auparavant réimplémenté indépendamment à 3 endroits (ui_lecture_puce.py:
_build_passage_section et _get_punch_statuses, main.py:
_calculer_tag_par_balise), avec le risque que les copies divergent au fil
des correctifs. Toute la logique métier vit ici ; l'affichage (Tkinter,
CSV, ...) reste dans les modules appelants.
"""


def evaluer_ordre(punches_terrain, balises_attendues):
    """Calcule la progression valide dans un parcours en mode "ordre".

    @param punches_terrain: liste de tuples dont le premier élément est le
                             numéro de balise pointée, dans l'ordre de lecture
                             (déjà filtrée sur la plage de balises valides).
    @param balises_attendues: liste ordonnée des numéros de balise du parcours.
    @return: (nb_valides, ordre_valide, ordre_invalide)
             - nb_valides: nombre de balises pointées dans le bon ordre depuis le début
             - ordre_valide: set des codes balise valides (bon ordre, sans rupture)
             - ordre_invalide: set des codes balise du parcours pointés après
               la première rupture d'ordre
    """
    balises_set = set(balises_attendues)
    seen, sequence_pointee = set(), []
    for p in punches_terrain:
        code = p[0]
        if code in balises_set and code not in seen:
            seen.add(code)
            sequence_pointee.append(code)

    nb_valides = 0
    for i, bal in enumerate(sequence_pointee):
        if i < len(balises_attendues) and bal == balises_attendues[i]:
            nb_valides += 1
        else:
            break

    ordre_valide = set(sequence_pointee[:nb_valides])
    ordre_invalide = set(sequence_pointee[nb_valides:])
    return nb_valides, ordre_valide, ordre_invalide


def statut_balise(code, parcours, ordre_valide=None, ordre_invalide=None):
    """Statut d'une balise pointée par rapport à un parcours.

    En mode "ordre", ordre_valide/ordre_invalide doivent venir de evaluer_ordre()
    (calculés sur la même liste de pointages que celle contenant `code`).
    @return: 'ok' / 'ordre' / 'hors', ou None si aucun parcours n'est défini.
    """
    if not parcours:
        return None
    if parcours.get("ordre"):
        if code in (ordre_valide or ()):
            return "ok"
        if code in (ordre_invalide or ()):
            return "ordre"
        return "hors"
    balises_set = set(parcours["balises"])
    return "ok" if code in balises_set else "hors"


def resultat_parcours(nb_valides_ou_pointes, total_attendu, mode_ordre):
    """Détermine si le parcours est réussi ou échoué, pour l'affichage.
    @return: (res_bg, res_txt) couleur hexadécimale et texte à afficher
    """
    if nb_valides_ou_pointes >= total_attendu:
        return "#27ae60", "Parcours réussi"
    if mode_ordre and nb_valides_ou_pointes > 0:
        return "#e67e22", "Parcours échoué"
    return "#e74c3c", "Parcours échoué"
