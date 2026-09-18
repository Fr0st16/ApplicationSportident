#!/usr/bin/env python3
"""LotMixin : gestion du lot multi-parcours (mixin de AppParcours).

Un "lot" est une liste de plusieurs parcours geres ensemble dans le meme
editeur (ajout/modification/suppression d'un item, sauvegarde du lot entier
en TSV ou CSV, lancement de la lecture pour tous les parcours du lot).

Extrait de ui_parcours.py sans changement de comportement : LotMixin est
melange (mixin) dans AppParcours (ui/parcours.py), qui garde l'etat
(self._lot, self._lot_edit_idx, self._lot_listbox, ...) initialise dans
son __init__ ; les methodes ci-dessous continuent d'y acceder via `self`
exactement comme avant.
"""

from tkinter import filedialog, messagebox
import csv as _csv_module
from datetime import datetime

from core.constants import BALISE_MIN, BALISE_MAX


class LotMixin:
    """Mixin de AppParcours : gestion du lot multi-parcours (ajout,
    modification, suppression, sauvegarde et lancement de la lecture)."""

    #  Lot de parcours

    def _ajouter_au_lot(self):
        """Ajoute le parcours courant au lot, ou met à jour l'item en cours de modification."""
        if not self._valider():
            return
        data = self._get_data()
        if self._lot_edit_idx is not None:
            # Mode modification : remplace l'item existant
            self._lot[self._lot_edit_idx] = data
            self._annuler_edition_lot()  # remet le bouton en mode "Ajouter"
        else:
            self._lot.append(data)
        self._rafraichir_lot()

    def _modifier_lot_item(self):
        """Charge l'item sélectionné dans le formulaire pour modification."""
        sel = self._lot_listbox.curselection()
        if not sel:
            messagebox.showinfo(
                "Aucune sélection",
                "Sélectionnez un parcours dans la liste avant de cliquer sur Modifier.",
                parent=self,
            )
            return
        idx = sel[0]
        if idx >= len(self._lot):
            return
        data = self._lot[idx]
        # Charger les données dans le formulaire
        self._balises_sel.clear()
        self._balises_ordre.clear()
        self._max_balises = None
        self._entry_nom.delete(0, "end")
        self._entry_nom.insert(0, data["nom"])
        for b in data["balises"]:
            if BALISE_MIN <= b <= BALISE_MAX:
                self._balises_sel.add(b)
                self._balises_ordre.append(b)
        self._var_ordre.set(data.get("ordre", False))
        self._est_sauvegarde = False
        self._rafraichir_grille()
        # Passer en mode modification
        self._lot_edit_idx = idx
        self._btn_lot_ajouter.config(
            text="Mettre à jour", bg="#27ae60", activebackground="#1e8449"
        )
        self._btn_lot_annuler.pack(
            side="left", padx=2, ipady=2, ipadx=4, after=self._btn_lot_ajouter
        )
        self._lbl_status.config(text=f"Modification du parcours {idx + 1} en cours.")

    def _annuler_edition_lot(self):
        """Quitte le mode modification sans sauvegarder."""
        self._lot_edit_idx = None
        self._btn_lot_ajouter.config(
            text="+ Ajouter", bg="#1a73e8", activebackground="#1558b0"
        )
        self._btn_lot_annuler.pack_forget()
        self._lbl_status.config(text="")

    def _retirer_du_lot(self):
        """Retire le parcours sélectionné du lot."""
        sel = self._lot_listbox.curselection()
        if not sel:
            return
        idx = sel[0]
        del self._lot[idx]
        self._rafraichir_lot()

    def _rafraichir_lot(self):
        """Met à jour l'affichage de la listbox du lot."""
        self._lot_listbox.delete(0, "end")
        if not self._lot:
            self._lot_listbox.insert("end", "  Aucun parcours dans le lot.")
            self._lot_listbox.config(fg="#aaa")
        else:
            self._lot_listbox.config(fg="#222")
            for i, p in enumerate(self._lot, 1):
                nb = len(p["balises"])
                ordre_tag = "  [ordre]" if p.get("ordre") else ""
                balises_str = ", ".join(str(b) for b in p["balises"])
                self._lot_listbox.insert(
                    "end",
                    f"  {i}. {p['nom']}  ({nb} balises{ordre_tag})  :  {balises_str}",
                )

    def _enregistrer_lot_tsv(self):
        """Enregistre tous les parcours du lot dans un fichier TSV multi-parcours."""
        if not self._lot:
            messagebox.showwarning(
                "Lot vide", "Aucun parcours dans le lot.", parent=self
            )
            return
        chemin = filedialog.asksaveasfilename(
            defaultextension=".tsv",
            filetypes=[("Fichier TSV", "*.tsv")],
            initialfile=f"lot_parcours_{datetime.now().strftime('%d-%m-%Y')}.tsv",
            title="Enregistrer le lot en TSV",
            parent=self,
        )
        if not chemin:
            return
        try:
            with open(chemin, "w", encoding="utf-8", newline="") as f:
                for i, data in enumerate(self._lot):
                    if i > 0:
                        f.write("\n")
                    f.write(f"# {data['nom']}\n")
                    if data.get("ordre"):
                        f.write("# ordre: oui\n")
                    for b in data["balises"]:
                        f.write(f"{b}\n")
        except Exception as e:
            messagebox.showerror(
                "Erreur", f"Impossible d'enregistrer :\n{e}", parent=self
            )
            return

    def _enregistrer_lot_csv(self):
        """Enregistre tous les parcours du lot dans un fichier CSV multi-parcours."""
        if not self._lot:
            messagebox.showwarning(
                "Lot vide", "Aucun parcours dans le lot.", parent=self
            )
            return
        chemin = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("Fichier CSV", "*.csv")],
            initialfile=f"lot_parcours_{datetime.now().strftime('%d-%m-%Y')}.csv",
            title="Enregistrer le lot en CSV",
            parent=self,
        )
        if not chemin:
            return
        try:
            max_b = max(len(p["balises"]) for p in self._lot)
            with open(chemin, "w", newline="", encoding="utf-8-sig") as f:
                writer = _csv_module.writer(f, delimiter=";")
                writer.writerow(
                    ["Nom", "Ordre"] + [f"Balise {i}" for i in range(1, max_b + 1)]
                )
                for data in self._lot:
                    row = [data["nom"], "oui" if data.get("ordre") else ""]
                    row += data["balises"]
                    row += [""] * (max_b - len(data["balises"]))
                    writer.writerow(row)
        except Exception as e:
            messagebox.showerror(
                "Erreur", f"Impossible d'enregistrer :\n{e}", parent=self
            )
            return

    def _lancer_lot(self):
        """Lance la lecture de tous les parcours du lot (un onglet par parcours)."""
        if not self._lot:
            messagebox.showwarning(
                "Lot vide",
                "Aucun parcours dans le lot.\nAjoutez d'abord des parcours avec '+ Ajouter'.",
                parent=self,
            )
            return
        if self._on_done:
            self._on_done(self._lot)
