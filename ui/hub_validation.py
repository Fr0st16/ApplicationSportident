#!/usr/bin/env python3
"""HubValidationMixin : dialogue de validation en mode controlee (mixin de HubMixin).

Contient _hub_ouvrir_validation : la fenetre modale qui s'affiche a chaque
lecture de puce en mode "controlee", pour choisir/confirmer le parcours de
destination et voir la liste colorree des balises pointees avant
d'enregistrer.

Extrait de main.py sans changement de comportement.
"""

import tkinter as tk
from tkinter import ttk


class HubValidationMixin:
    """Mixin de HubMixin : fenêtre de validation d'une puce en mode contrôlée."""

    def _hub_ouvrir_validation(self, source_app, card_number, card_data, app_suggeree):
        """Mode contrôlée : ouvre une fenêtre de validation avant d'enregistrer la puce.

        L'utilisateur voit le numéro de puce, le nom (si candidat connu), un menu
        déroulant pour choisir/changer le parcours de destination (pré-sélectionné
        par score), et la liste des balises pointées. Valider enregistre la puce
        dans le parcours choisi ; Annuler ne fait rien (comme si non lue)."""
        from core.constants import BALISE_MIN, BALISE_MAX
        from core.validation import evaluer_ordre, statut_balise

        self._lecture_apps = [a for a in self._lecture_apps if a.winfo_exists()]
        parcours_apps = [a for a in self._lecture_apps if a._parcours]
        if not parcours_apps:
            parcours_apps = list(self._lecture_apps)

        # Chercher le nom du candidat (depuis n'importe quelle app, la liste est partagée)
        nom_candidat = None
        for a in self._lecture_apps:
            try:
                candidat = a._liste_candidats.get(card_number) or a._liste_candidats.get(int(card_number))
            except Exception:
                candidat = None
            if candidat:
                prenom = str(candidat.get("prenom", "")).strip()
                nom_fam = str(candidat.get("nom", "")).strip()
                nom_candidat = f"{prenom} {nom_fam}".strip()
                break

        punches = [
            p for p in card_data.get("punches", [])
            if isinstance(p[0], int) and BALISE_MIN <= p[0] <= BALISE_MAX
        ]
        nb_punches_bruts = len(card_data.get("punches", []))

        dlg = tk.Toplevel(self.root)
        dlg.title("Valider la puce")
        dlg.geometry("420x520")
        dlg.resizable(False, False)
        dlg.transient(self.root)
        dlg.grab_set()
        dlg.protocol("WM_DELETE_WINDOW", lambda: None)  # empêcher la fermeture par la croix
        dlg.bind("<Escape>", lambda e: "break")          # empêcher la fermeture par Échap

        tk.Label(
            dlg, text=f"Puce n° {card_number}",
            font=("Segoe UI", 13, "bold"),
        ).pack(pady=(16, 4))
        tk.Label(
            dlg, text=nom_candidat if nom_candidat else "(nom inconnu — sera demandé après validation)",
            font=("Segoe UI", 10), fg="#555" if nom_candidat else "#999",
        ).pack(pady=(0, 12))

        tk.Label(dlg, text="Parcours de destination :", font=("Segoe UI", 9, "bold")).pack(anchor="w", padx=20)
        noms_parcours = [a._parcours["nom"] if a._parcours else "Lecture libre" for a in parcours_apps]
        var_parcours = tk.StringVar()
        idx_defaut = parcours_apps.index(app_suggeree) if app_suggeree in parcours_apps else 0
        var_parcours.set(noms_parcours[idx_defaut] if noms_parcours else "")
        combo = ttk.Combobox(dlg, textvariable=var_parcours, values=noms_parcours, state="readonly")
        combo.pack(fill="x", padx=20, pady=(2, 12))

        tk.Label(dlg, text=f"Balises pointées ({len(punches)}) :", font=("Segoe UI", 9, "bold")).pack(anchor="w", padx=20)
        if nb_punches_bruts > len(punches):
            tk.Label(
                dlg,
                text=f"⚠  {nb_punches_bruts - len(punches)} pointage(s) hors plage "
                     f"({BALISE_MIN}-{BALISE_MAX}) ignoré(s) — vérifiez la lecture.",
                font=("Segoe UI", 8), fg="#e67e22",
            ).pack(anchor="w", padx=20, pady=(0, 2))
        frame_list = tk.Frame(dlg)
        frame_list.pack(fill="both", expand=True, padx=20, pady=(2, 12))
        tree = ttk.Treeview(frame_list, columns=("balise", "heure"), show="headings", height=8)
        tree.heading("balise", text="Balise")
        tree.heading("heure", text="Heure")
        tree.column("balise", width=120, anchor="center")
        tree.column("heure", width=140, anchor="center")
        sb = ttk.Scrollbar(frame_list, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        tree.pack(side="left", fill="both", expand=True)

        tree.tag_configure("ok",    foreground="white", background="#27ae60")
        tree.tag_configure("ordre", foreground="white", background="#e67e22")
        tree.tag_configure("hors",  foreground="white", background="#e74c3c")

        def _calculer_tag_par_balise(app_cible):
            """Calcule le tag couleur (ok/ordre/hors) pour chaque balise pointée,
            selon le parcours actuellement choisi dans le menu déroulant."""
            if app_cible is None or not app_cible._parcours:
                return {code: "hors" for code, _ in punches}
            ordre_valide = ordre_invalide = None
            if app_cible._parcours.get("ordre"):
                _, ordre_valide, ordre_invalide = evaluer_ordre(punches, app_cible._parcours["balises"])
            return {
                code: statut_balise(code, app_cible._parcours, ordre_valide, ordre_invalide)
                for code, _ in punches
            }

        def _remplir_tree():
            """Recalcule et réaffiche la liste colorée des balises pointées,
            selon le parcours actuellement choisi dans le menu déroulant."""
            tree.delete(*tree.get_children())
            sel_nom = var_parcours.get()
            try:
                idx = noms_parcours.index(sel_nom)
                app_cible = parcours_apps[idx]
            except ValueError:
                app_cible = app_suggeree
            tags_par_balise = _calculer_tag_par_balise(app_cible)
            for code, tim in punches:
                try:
                    heure = tim.strftime("%H:%M:%S")
                except Exception:
                    heure = str(tim)
                tag = tags_par_balise.get(code, "hors")
                tree.insert("", "end", values=(code, heure), tags=(tag,))

        _remplir_tree()
        combo.bind("<<ComboboxSelected>>", lambda e: _remplir_tree())

        resultat = {"valide": False, "app": None}

        def on_valider():
            """Enregistre le choix de parcours de destination et ferme le dialogue."""
            sel_nom = var_parcours.get()
            try:
                idx = noms_parcours.index(sel_nom)
                resultat["app"] = parcours_apps[idx]
            except ValueError:
                resultat["app"] = app_suggeree
            resultat["valide"] = True
            dlg.destroy()

        def on_annuler():
            """Rejette la lecture en cours : la puce ne sera pas enregistrée."""
            resultat["valide"] = False
            dlg.destroy()

        btnf = tk.Frame(dlg)
        btnf.pack(fill="x", padx=20, pady=(0, 16))
        tk.Button(
            btnf, text="Annuler", command=on_annuler,
            bg="#e74c3c", fg="white", relief="flat", cursor="hand2",
            activebackground="#c0392b", activeforeground="white",
        ).pack(side="left", fill="x", expand=True, padx=(0, 6), ipady=8)
        tk.Button(
            btnf, text="Valider", command=on_valider,
            bg="#27ae60", fg="white", relief="flat", cursor="hand2",
            activebackground="#1e8449", activeforeground="white",
        ).pack(side="right", fill="x", expand=True, padx=(6, 0), ipady=8)

        self.root.wait_window(dlg)

        if resultat["valide"] and resultat["app"] is not None:
            cible = resultat["app"]
            nom_existant = self._trouver_nom_puce(card_number)
            if nom_existant and card_number not in cible._noms:
                cible._noms[card_number] = nom_existant
            event_to_set = None if cible is source_app else source_app._card_event
            deja_present_avant = card_number in cible._frames
            cible._creer_onglet_puce(card_number, card_data, event_to_set=event_to_set, broadcast=False)
            # Si la puce n'a pas été ajoutée (nom annulé dans le dialogue qui suit),
            # ne pas naviguer vers le parcours cible — traiter comme une annulation.
            enregistree = card_number in cible._frames
            if not enregistree and not deja_present_avant:
                return
            try:
                if self._lecture_hub_tab is not None:
                    self.notebook.select(self._lecture_hub_tab)
                self._hub_show_app(cible)
                self._hub_refresh_list()
            except Exception:
                pass
        else:
            # Annulé : la puce n'est pas enregistrée, on débloque simplement le thread de lecture
            source_app._card_event.set()
