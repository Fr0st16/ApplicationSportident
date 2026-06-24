#!/usr/bin/env python3
"""
Interface visuelle pour la construction d'un parcours SportIdent.
Génère un fichier .tsv avec le nom du parcours et la liste des balises.
"""
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import os
import csv as _csv_module
from datetime import datetime
#  Constantes
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


class AppParcours(tk.Frame):

    def __init__(self, parent, on_done=None, on_cancel=None, initial_lot=None):
        super().__init__(parent, bg="white")
        self.pack(fill="both", expand=True)
        self._on_done = on_done
        self._on_cancel = on_cancel
        self._balises_sel = set()  # set d'ints -> lookup rapide
        self._balises_ordre = []  # liste ordonnée -> préserve l'ordre de sélection
        self._toggle_btns = {}  # balise (int) - Button
        self._max_balises = None  # limite fixée par un preset (None = libre)
        self._var_ordre = tk.BooleanVar(value=False)  # ordre obligatoire ?
        self._est_sauvegarde = False  # True si l'état courant a été enregistré
        self._lot = []  # list[dict] pour le lot multi-parcours
        self._lot_edit_idx = (
            None  # index de l'item en cours de modification (None = mode ajout)
        )
        self._drag_active = False  # True pendant un drag de sélection sur la grille
        self._drag_action = None
        # "add" ou "remove"
        self._build_ui()
        # Si un lot initial est fourni (édition d'un lot déjà chargé), l'utiliser
        if initial_lot:
            try:
                # Faire une copie superficielle pour éviter altérations externes
                self._lot = [dict(p) for p in initial_lot]
                self._rafraichir_lot()
                if hasattr(self, "_lbl_status"):
                    self._lbl_status.config(
                        text=f"Lot chargé : {len(self._lot)} parcours"
                    )
            except Exception:
                pass

    def _build_ui(self):
        entete = tk.Frame(self, bg="#1e1e2e")
        entete.pack(fill="x")
        tk.Label(
            entete,
            text="Construction de Parcours",
            font=("Segoe UI", 12, "bold"),
            bg="#1e1e2e",
            fg="white",
        ).pack(side="left", padx=14, pady=10)
        barre = tk.Frame(self, bg="#f5f5f5", pady=6)
        barre.pack(fill="x", side="bottom")
        grp_imp = tk.Frame(barre, bg="#f5f5f5")
        grp_imp.pack(side="left", padx=(8, 0))
        tk.Label(
            grp_imp, text="Importer", font=("Segoe UI", 7), bg="#f5f5f5", fg="#999"
        ).pack(anchor="w", padx=2)
        frm_imp = tk.Frame(grp_imp, bg="#f5f5f5")
        frm_imp.pack()
        tk.Button(
            frm_imp,
            text="Ouvrir (.tsv)",
            font=("Segoe UI", 9),
            bg="#7f8c8d",
            fg="white",
            relief="flat",
            cursor="hand2",
            activebackground="#636e72",
            activeforeground="white",
            command=self._charger_fichier,
        ).pack(side="left", ipadx=8, ipady=4)
        tk.Button(
            frm_imp,
            text="Importer (.csv)",
            font=("Segoe UI", 9),
            bg="#16a085",
            fg="white",
            relief="flat",
            cursor="hand2",
            activebackground="#1a8a72",
            activeforeground="white",
            command=self._importer_csv,
        ).pack(side="left", padx=(4, 0), ipadx=8, ipady=4)
        tk.Button(
            frm_imp,
            text="OCAD (.xml/.txt)",
            font=("Segoe UI", 9),
            bg="#e67e22",
            fg="white",
            relief="flat",
            cursor="hand2",
            activebackground="#ca6f1e",
            activeforeground="white",
            command=self._importer_ocad,
        ).pack(side="left", padx=(4, 0), ipadx=8, ipady=4)
        tk.Frame(barre, bg="#d0d0d0", width=1).pack(
            side="left", fill="y", padx=10, pady=4
        )
        grp_sav = tk.Frame(barre, bg="#f5f5f5")
        grp_sav.pack(side="left")
        tk.Label(
            grp_sav, text="Enregistrer", font=("Segoe UI", 7), bg="#f5f5f5", fg="#999"
        ).pack(anchor="w", padx=2)
        frm_sav = tk.Frame(grp_sav, bg="#f5f5f5")
        frm_sav.pack()
        tk.Button(
            frm_sav,
            text="Enregistrer (.tsv)",
            font=("Segoe UI", 9),
            bg="#27ae60",
            fg="white",
            relief="flat",
            cursor="hand2",
            activebackground="#1e8449",
            activeforeground="white",
            command=self._enregistrer,
        ).pack(side="left", ipadx=8, ipady=4)
        tk.Button(
            frm_sav,
            text="Enregistrer (.csv)",
            font=("Segoe UI", 9),
            bg="#229954",
            fg="white",
            relief="flat",
            cursor="hand2",
            activebackground="#1a7a42",
            activeforeground="white",
            command=self._enregistrer_csv,
        ).pack(side="left", padx=(4, 0), ipadx=8, ipady=4)
        if self._on_done:
            tk.Button(
                barre,
                text="Lancer la lecture",
                font=("Segoe UI", 11, "bold"),
                bg="#1a73e8",
                fg="white",
                relief="flat",
                cursor="hand2",
                activebackground="#1558b0",
                activeforeground="white",
                command=self._lancer_lecture,
            ).pack(side="right", padx=12, ipadx=14, ipady=8)
        self._lbl_status = tk.Label(
            barre, text="", font=("Segoe UI", 8), bg="#f5f5f5", fg="#555"
        )
        self._lbl_status.pack(side="left", padx=8)
        corps = tk.Frame(self, bg="white")
        corps.pack(fill="both", expand=True, padx=16, pady=12)
        # Nom du parcours
        frame_nom = tk.Frame(corps, bg="white")
        frame_nom.pack(fill="x", pady=(0, 8))
        tk.Label(
            frame_nom, text="Nom du parcours :", font=("Segoe UI", 9), bg="white"
        ).pack(side="left")
        self._entry_nom = tk.Entry(frame_nom, font=("Segoe UI", 9))
        self._entry_nom.pack(side="left", fill="x", expand=True, padx=(8, 0))
        # Presets rapides
        frame_preset = tk.Frame(corps, bg="white")
        frame_preset.pack(fill="x", pady=(0, 10))
        tk.Label(frame_preset, text="Preset :", font=("Segoe UI", 9), bg="white").pack(
            side="left"
        )
        self._preset_btns = {}
        for nb in (10, 24, 26):
            btn = tk.Button(
                frame_preset,
                text=f"{nb} balises",
                font=("Segoe UI", 8, "bold"),
                relief="flat",
                cursor="hand2",
                bg="#1a73e8",
                fg="white",
                activebackground="#1558b0",
                activeforeground="white",
                command=lambda n=nb: self._appliquer_preset(n),
            )
            btn.pack(side="left", padx=4, ipady=3, ipadx=6)
            self._preset_btns[nb] = btn
        tk.Button(
            frame_preset,
            text="Tout effacer",
            font=("Segoe UI", 8),
            relief="flat",
            cursor="hand2",
            bg="#e0e0e0",
            fg="#333",
            activebackground="#ccc",
            command=self._tout_effacer,
        ).pack(side="left", padx=(12, 0), ipady=3, ipadx=6)
        ttk.Separator(corps, orient="horizontal").pack(fill="x", pady=(0, 8))
        # Grille de balises
        tk.Label(
            corps,
            text="Sélectionnez les balises du parcours :",
            font=("Segoe UI", 9),
            fg="#555",
            bg="white",
        ).pack(anchor="w", pady=(0, 6))
        # Conteneur scrollable pour la grille (226 balises)
        frame_grille_outer = tk.Frame(corps, bg="white")
        frame_grille_outer.pack(fill="x")
        self._grille_canvas = tk.Canvas(
            frame_grille_outer, bg="white", highlightthickness=0, height=160
        )
        _grille_scroll = tk.Scrollbar(
            frame_grille_outer, orient="vertical", command=self._grille_canvas.yview
        )
        self._grille_canvas.configure(yscrollcommand=_grille_scroll.set)
        _grille_scroll.pack(side="right", fill="y")
        self._grille_canvas.pack(side="left", fill="x", expand=True)
        self._frame_grille = tk.Frame(self._grille_canvas, bg="white")
        self._grille_canvas_win_id = self._grille_canvas.create_window(
            (0, 0), window=self._frame_grille, anchor="nw"
        )
        self._frame_grille.bind(
            "<Configure>",
            lambda e: self._grille_canvas.configure(
                scrollregion=self._grille_canvas.bbox("all")
            ),
        )

        def _on_grille_scroll(ev):
            if getattr(ev, "num", None) == 4:
                self._grille_canvas.yview_scroll(-1, "units")
            elif getattr(ev, "num", None) == 5:
                self._grille_canvas.yview_scroll(1, "units")
            else:
                self._grille_canvas.yview_scroll(int(-1 * (ev.delta / 120)), "units")
        self._grille_canvas.bind(
            "<Enter>",
            lambda e: (
                self._grille_canvas.bind("<MouseWheel>", _on_grille_scroll),
                self._grille_canvas.bind("<Button-4>", _on_grille_scroll),
                self._grille_canvas.bind("<Button-5>", _on_grille_scroll),
            ),
        )
        self._grille_canvas.bind(
            "<Leave>",
            lambda e: (
                self._grille_canvas.unbind("<MouseWheel>"),
                self._grille_canvas.unbind("<Button-4>"),
                self._grille_canvas.unbind("<Button-5>"),
            ),
        )
        # Responsive : la frame interne suit la largeur exacte du canvas

        def _on_canvas_configure(e):
            self._grille_canvas.itemconfig(self._grille_canvas_win_id, width=e.width)
            self._adapter_grille_cols(e.width)
        self._grille_canvas.bind("<Configure>", _on_canvas_configure)
        self._grille_ncols = GRID_COLS
        for i, b in enumerate(BALISES_TOUTES):
            row, col = divmod(i, self._grille_ncols)
            btn = tk.Button(
                self._frame_grille,
                text=str(b),
                font=("Segoe UI", 8),
                relief="flat",
                cursor="hand2",
            )
            btn.bind("<ButtonPress-1>", lambda e, n=b: self._drag_start(n))
            btn.bind("<B1-Motion>", self._on_drag_motion)
            btn.bind("<ButtonRelease-1>", lambda e: self._drag_end())
            btn.grid(row=row, column=col, sticky="ew", padx=2, pady=2, ipady=3)
            self._toggle_btns[b] = btn
        # Toutes les colonnes initiales s'étirent équitablement
        for c in range(self._grille_ncols):
            self._frame_grille.columnconfigure(c, weight=1, uniform="balise")
        # Compteur (créé AVANT _rafraichir_grille qui y accède)
        self._lbl_compteur = tk.Label(
            corps,
            text="0 balise(s) sélectionnée(s)",
            font=("Segoe UI", 8),
            fg="#777",
            bg="white",
        )
        self._lbl_compteur.pack(anchor="e", pady=(6, 0))
        # Case à cocher "Ordre obligatoire"
        frame_ordre = tk.Frame(corps, bg="white")
        frame_ordre.pack(anchor="w", pady=(6, 0))
        tk.Checkbutton(
            frame_ordre,
            text="Ordre obligatoire",
            variable=self._var_ordre,
            font=("Segoe UI", 9),
            bg="white",
            cursor="hand2",
            activebackground="white",
            command=self._on_toggle_ordre,
        ).pack(side="left")
        tk.Label(
            frame_ordre,
            text="(les balises devront être pointées dans cet ordre précis)",
            font=("Segoe UI", 8),
            fg="#888",
            bg="white",
        ).pack(side="left", padx=(4, 0))
        self._frame_apercu = tk.Frame(corps, bg="white")
        # packé ou non selon la case : _rafraichir_grille s'en charge
        ttk.Separator(self._frame_apercu, orient="horizontal").pack(
            fill="x", pady=(10, 6)
        )
        tk.Label(
            self._frame_apercu,
            text="Aperçu de l'ordre des balises :",
            font=("Segoe UI", 8, "bold"),
            fg="#555",
            bg="white",
        ).pack(anchor="w")
        frame_preview_outer = tk.Frame(
            self._frame_apercu, bg="#f0f4ff", relief="solid", bd=1
        )
        frame_preview_outer.pack(fill="x", pady=(4, 0))
        self._preview_canvas = tk.Canvas(
            frame_preview_outer, bg="#f0f4ff", height=58, highlightthickness=0
        )
        self._preview_scroll = tk.Scrollbar(
            frame_preview_outer, orient="horizontal", command=self._preview_canvas.xview
        )
        self._preview_canvas.configure(xscrollcommand=self._preview_scroll.set)
        self._preview_canvas.pack(fill="x", expand=True)
        self._preview_scroll.pack(fill="x")
        self._preview_inner = tk.Frame(self._preview_canvas, bg="#f0f4ff")
        self._preview_canvas_win = self._preview_canvas.create_window(
            (0, 0), window=self._preview_inner, anchor="nw"
        )
        self._preview_inner.bind(
            "<Configure>",
            lambda e: self._preview_canvas.configure(
                scrollregion=self._preview_canvas.bbox("all")
            ),
        )
        # Pas de pack() ici : c'est _rafraichir_grille qui décide de l'afficher
        self._sep_lot = ttk.Separator(corps, orient="horizontal")
        self._sep_lot.pack(fill="x", pady=(10, 4))
        frm_lot_hdr = tk.Frame(corps, bg="white")
        frm_lot_hdr.pack(fill="x")
        tk.Label(
            frm_lot_hdr,
            text="Lot de parcours :",
            font=("Segoe UI", 9, "bold"),
            bg="white",
        ).pack(side="left")
        self._btn_lot_ajouter = tk.Button(
            frm_lot_hdr,
            text="+ Ajouter",
            font=("Segoe UI", 8),
            relief="flat",
            cursor="hand2",
            bg="#1a73e8",
            fg="white",
            activebackground="#1558b0",
            activeforeground="white",
            command=self._ajouter_au_lot,
        )
        self._btn_lot_ajouter.pack(side="left", padx=(8, 2), ipady=2, ipadx=4)
        tk.Button(
            frm_lot_hdr,
            text="Modifier",
            font=("Segoe UI", 8),
            relief="flat",
            cursor="hand2",
            bg="#e67e22",
            fg="white",
            activebackground="#ca6f1e",
            activeforeground="white",
            command=self._modifier_lot_item,
        ).pack(side="left", padx=2, ipady=2, ipadx=4)
        self._btn_lot_annuler = tk.Button(
            frm_lot_hdr,
            text="Annuler",
            font=("Segoe UI", 8),
            relief="flat",
            cursor="hand2",
            bg="#7f8c8d",
            fg="white",
            activebackground="#636e72",
            activeforeground="white",
            command=self._annuler_edition_lot,
        )
        # Caché par défaut, affiché uniquement en mode modification
        tk.Button(
            frm_lot_hdr,
            text="Retirer",
            font=("Segoe UI", 8),
            relief="flat",
            cursor="hand2",
            bg="#e74c3c",
            fg="white",
            activebackground="#c0392b",
            activeforeground="white",
            command=self._retirer_du_lot,
        ).pack(side="left", padx=2, ipady=2, ipadx=4)
        frm_lot_list = tk.Frame(corps, bg="white")
        frm_lot_list.pack(fill="both", expand=True, pady=(4, 0))
        self._lot_listbox = tk.Listbox(
            frm_lot_list,
            height=10,
            font=("Segoe UI", 10),
            selectmode="single",
            bg="#f8f8f8",
            relief="solid",
            bd=1,
            activestyle="none",
            xscrollcommand=lambda *a: _lot_sb_x.set(*a),
        )
        _lot_sb = tk.Scrollbar(
            frm_lot_list, orient="vertical", command=self._lot_listbox.yview
        )
        _lot_sb_x = tk.Scrollbar(
            frm_lot_list, orient="horizontal", command=self._lot_listbox.xview
        )
        self._lot_listbox.configure(yscrollcommand=_lot_sb.set)
        _lot_sb.pack(side="right", fill="y")
        _lot_sb_x.pack(side="bottom", fill="x")
        self._lot_listbox.pack(fill="both", expand=True)
        self._rafraichir_grille()
        self._rafraichir_lot()
    # Balises : sélection / grille

    def _appliquer_preset(self, nb):
        """Applique un preset de N balises."""
        self._est_sauvegarde = False
        self._max_balises = nb
        self._balises_sel = set(PRESETS[nb])
        self._balises_ordre = list(PRESETS[nb])
        self._rafraichir_grille()

    def _tout_effacer(self):
        self._est_sauvegarde = False
        self._balises_sel.clear()
        self._balises_ordre.clear()
        self._max_balises = None
        self._rafraichir_grille()

    def _toggle_balise(self, n):
        self._est_sauvegarde = False
        if n in self._balises_sel:
            self._balises_sel.discard(n)
            self._balises_ordre.remove(n)
        else:
            if (
                self._max_balises is not None
                and len(self._balises_sel) >= self._max_balises
            ):
                return  # limite atteinte, on bloque silencieusement
            self._balises_sel.add(n)
            self._balises_ordre.append(n)
        self._rafraichir_grille()

    def _drag_start(self, n):
        """Démarre la sélection par drag : détermine l'action et toggle la première balise."""
        self._drag_action = "remove" if n in self._balises_sel else "add"
        self._drag_active = True
        self._toggle_balise(n)

    def _on_drag_motion(self, event):
        """Applique l'action de drag sur la balise sous le curseur (bouton maintenu)."""
        if not self._drag_active:
            return
        widget = self.winfo_containing(event.x_root, event.y_root)
        if widget is None:
            return
        for b, btn in self._toggle_btns.items():
            if btn is widget:
                if self._drag_action == "add" and b not in self._balises_sel:
                    self._toggle_balise(b)
                elif self._drag_action == "remove" and b in self._balises_sel:
                    self._toggle_balise(b)
                return

    def _drag_end(self):
        """Termine le drag de sélection."""
        self._drag_active = False
        self._drag_action = None

    def _rafraichir_grille(self):
        """Met à jour les couleurs des boutons, le compteur et les boutons preset."""
        n = len(self._balises_sel)
        limite_atteinte = self._max_balises is not None and n >= self._max_balises
        ordre_mode = self._var_ordre.get()
        for b, btn in self._toggle_btns.items():
            if b in self._balises_sel:
                # En mode ordre : affiche le numéro de position à la place du numéro de balise
                if ordre_mode:
                    pos = self._balises_ordre.index(b) + 1
                    label = str(pos)
                else:
                    label = str(b)
                btn.config(
                    text=label,
                    bg="#1a73e8",
                    fg="white",
                    activebackground="#1558b0",
                    activeforeground="white",
                )
            elif limite_atteinte:
                btn.config(
                    text=str(b),
                    bg="#c8c8c8",
                    fg="#888",
                    activebackground="#c8c8c8",
                    activeforeground="#888",
                )
            else:
                btn.config(
                    text=str(b),
                    bg="#e8e8e8",
                    fg="#333",
                    activebackground="#d0d0d0",
                    activeforeground="#333",
                )
        # Mise en évidence du preset actif
        for nb, pbtn in self._preset_btns.items():
            if self._max_balises == nb:
                pbtn.config(bg="#0d47a1")  # bleu foncé = preset actif
            else:
                pbtn.config(bg="#1a73e8")
        if self._max_balises is not None:
            self._lbl_compteur.config(
                text=f"{n} / {self._max_balises} balise(s) sélectionnée(s)"
            )
        else:
            self._lbl_compteur.config(text=f"{n} balise(s) sélectionnée(s)")
        # Afficher ou masquer la zone d'aperçu selon la case "Ordre obligatoire"
        if ordre_mode:
            self._grille_canvas.config(height=95)
            self._frame_apercu.pack(fill="x", before=self._sep_lot)
        else:
            self._grille_canvas.config(height=160)
            self._frame_apercu.pack_forget()
        self._rafraichir_preview()

    def _rafraichir_preview(self):
        """Reconstruit les chips de prévisualisation du parcours."""
        for w in self._preview_inner.winfo_children():
            w.destroy()
        if not self._balises_ordre:
            tk.Label(
                self._preview_inner,
                text="Aucune balise sélectionnée",
                font=("Segoe UI", 8),
                fg="#aaa",
                bg="#f0f4ff",
            ).pack(side="left", padx=14, pady=14)
        else:
            for i, b in enumerate(self._balises_ordre):
                chip = tk.Frame(self._preview_inner, bg="#1a73e8", padx=8, pady=4)
                chip.pack(side="left", padx=4, pady=7)
                # Numéro d'ordre (petit, clair)
                tk.Label(
                    chip,
                    text=str(i + 1),
                    font=("Segoe UI", 7),
                    bg="#1a73e8",
                    fg="#c9d9f7",
                ).pack()
                # Numéro de balise (gras, blanc)
                tk.Label(
                    chip,
                    text=str(b),
                    font=("Segoe UI", 9, "bold"),
                    bg="#1a73e8",
                    fg="white",
                ).pack()
        self._preview_inner.update_idletasks()
        self._preview_canvas.configure(scrollregion=self._preview_canvas.bbox("all"))
    # TSV : enregistrement

    def _valider(self):
        """Vérifie que le parcours est non vide avant toute action."""
        if not self._balises_sel:
            messagebox.showwarning(
                "Aucune balise",
                "Sélectionnez au moins une balise avant de continuer.",
                parent=self,
            )
            return False
        return True

    def _get_data(self):
        return {
            "nom": self._entry_nom.get().strip() or "parcours",
            "balises": list(self._balises_ordre),  # ordre de sélection préservé
            "ordre": self._var_ordre.get(),
        }

    def _choisir_chemin(self, data):
        nom_fichier = f"{data['nom']}_{datetime.now().strftime('%d-%m-%Y')}.tsv"
        return filedialog.asksaveasfilename(
            defaultextension=".tsv",
            filetypes=[("Fichier TSV", "*.tsv")],
            initialfile=nom_fichier,
            title="Enregistrer le parcours",
            parent=self,
        )

    def _sauvegarder(self, chemin, data):
        with open(chemin, "w", encoding="utf-8", newline="") as f:
            f.write(f"# {data['nom']}\n")
            if data.get("ordre"):
                f.write("# ordre: oui\n")
            for b in data["balises"]:
                f.write(f"{b}\n")

    def _enregistrer(self):
        if self._lot:
            self._enregistrer_lot_tsv()
            return
        if not self._valider():
            return
        data = self._get_data()
        chemin = self._choisir_chemin(data)
        if not chemin:
            return
        try:
            self._sauvegarder(chemin, data)
        except Exception as e:
            messagebox.showerror(
                "Erreur", f"Impossible d'enregistrer :\n{e}", parent=self
            )
            return
        self._est_sauvegarde = True

    def _enregistrer_csv(self):
        if self._lot:
            self._enregistrer_lot_csv()
            return
        if not self._valider():
            return
        data = self._get_data()
        nom_fichier = f"{data['nom']}_{datetime.now().strftime('%d-%m-%Y')}.csv"
        chemin = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("Fichier CSV", "*.csv")],
            initialfile=nom_fichier,
            title="Enregistrer le parcours en CSV",
            parent=self,
        )
        if not chemin:
            return
        try:
            with open(chemin, "w", newline="", encoding="utf-8-sig") as f:
                writer = _csv_module.writer(f, delimiter=";")
                writer.writerow(["Nom", data["nom"]])
                if data.get("ordre"):
                    writer.writerow(["Ordre", "oui"])
                writer.writerow(["Balise"])
                for b in data["balises"]:
                    writer.writerow([b])
        except Exception as e:
            messagebox.showerror(
                "Erreur", f"Impossible d'enregistrer :\n{e}", parent=self
            )
            return
        self._est_sauvegarde = True
    # TSV : chargement

    @staticmethod
    def _parser_tsv(chemin):
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

    def _charger_fichier(self):
        """Ouvre un .tsv (simple ou multi-parcours) et peuple l'interface."""
        chemin = filedialog.askopenfilename(
            filetypes=[("Fichier TSV", "*.tsv"), ("Tous les fichiers", "*.*")],
            title="Ouvrir un parcours",
            parent=self,
        )
        if not chemin:
            return
        try:
            lots = self._parser_lot_tsv(chemin)
        except Exception as e:
            messagebox.showerror(
                "Erreur", f"Impossible de lire le fichier :\n{e}", parent=self
            )
            return
        if not lots:
            messagebox.showwarning(
                "Fichier vide", "Aucune balise trouvée dans ce fichier.", parent=self
            )
            return
        if len(lots) == 1:
            # Parcours unique - peupler l'éditeur
            data = lots[0]
            self._balises_sel.clear()
            self._balises_ordre.clear()
            self._max_balises = None
            self._entry_nom.delete(0, "end")
            self._entry_nom.insert(0, data["nom"])
            for b in data["balises"]:
                if BALISE_MIN <= b <= BALISE_MAX:
                    self._balises_sel.add(b)
                    self._balises_ordre.append(b)
            self._var_ordre.set(data["ordre"])
            self._est_sauvegarde = True
            self._rafraichir_grille()
            self._lbl_status.config(text=f"Ouvert : {os.path.basename(chemin)}")
        else:
            # Multi-parcours - charger dans le lot
            self._lot = lots
            self._rafraichir_lot()
            self._lbl_status.config(
                text=f"Lot chargé : {len(lots)} parcours - {os.path.basename(chemin)}"
            )
    # CSV : import intelligent

    def _importer_csv(self):
        """
        importe un CSV quelconque et en extrait les balises pour créer un parcours."""
        chemin = filedialog.askopenfilename(
            filetypes=[("Fichier CSV", "*.csv"), ("Tous les fichiers", "*.*")],
            title="Importer un parcours depuis un fichier CSV",
            parent=self,
        )
        if not chemin:
            return
        try:
            nom, balises = self._parser_csv_intelligent(chemin)
        except Exception as e:
            messagebox.showerror(
                "Erreur", f"Impossible de lire le fichier :\n{e}", parent=self
            )
            return
        if not balises:
            messagebox.showwarning(
                "Aucune balise trouvée",
                f"Aucune balise valide (entre {BALISE_MIN} et {BALISE_MAX})\n"
                "n'a été détectée dans ce fichier CSV.",
                parent=self,
            )
            return
        result = self._dialogue_import_csv(nom, balises)
        if result is None:
            return
        nom_final, balises_final, ordre_final = result
        self._balises_sel.clear()
        self._balises_ordre.clear()
        self._max_balises = None
        self._entry_nom.delete(0, "end")
        self._entry_nom.insert(0, nom_final)
        for b in balises_final:
            self._balises_sel.add(b)
            self._balises_ordre.append(b)
        self._var_ordre.set(ordre_final)
        self._est_sauvegarde = False
        self._rafraichir_grille()
        self._lbl_status.config(
            text=f"Import CSV : {len(self._balises_sel)} balise(s) chargée(s)"
        )

    @staticmethod
    def _parser_csv_intelligent(chemin):
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

    def _dialogue_import_csv(self, nom_defaut, balises):
        """
        Dialogue de confirmation avant import CSV.
        Retourne (nom, balises, ordre) ou None si annulé.
        """
        dlg = tk.Toplevel(self)
        dlg.title("Importer un parcours - aperçu")
        dlg.configure(bg="white")
        dlg.resizable(False, False)
        dlg.grab_set()
        # Centrer sur la fenêtre parente
        self.update_idletasks()
        px = self.winfo_rootx() + self.winfo_width() // 2 - 210
        py = self.winfo_rooty() + self.winfo_height() // 2 - 170
        dlg.geometry(f"420x340+{px}+{py}")
        result = [None]
        # En-tête
        hdr = tk.Frame(dlg, bg="#1e1e2e")
        hdr.pack(fill="x")
        tk.Label(
            hdr,
            text="Importer depuis CSV",
            font=("Segoe UI", 11, "bold"),
            bg="#1e1e2e",
            fg="white",
        ).pack(side="left", padx=14, pady=8)
        body = tk.Frame(dlg, bg="white")
        body.pack(fill="both", expand=True, padx=16, pady=12)
        # Nom du parcours
        frm_nom = tk.Frame(body, bg="white")
        frm_nom.pack(fill="x", pady=(0, 8))
        tk.Label(
            frm_nom, text="Nom du parcours :", font=("Segoe UI", 9, "bold"), bg="white"
        ).pack(side="left")
        var_nom = tk.StringVar(value=nom_defaut)
        tk.Entry(frm_nom, textvariable=var_nom, font=("Segoe UI", 9), width=24).pack(
            side="left", padx=(8, 0), fill="x", expand=True
        )
        ttk.Separator(body, orient="horizontal").pack(fill="x", pady=(0, 8))
        # Résumé
        frm_info = tk.Frame(body, bg="#e8f4fd", relief="solid", bd=1)
        frm_info.pack(fill="x", pady=(0, 8))
        tk.Label(
            frm_info,
            text=f"  {len(balises)} balise(s) détectée(s) - "
            f"de {min(balises)} à {max(balises)}",
            font=("Segoe UI", 9),
            bg="#e8f4fd",
            fg="#1a5276",
            anchor="w",
        ).pack(fill="x", padx=4, pady=6)
        # Aperçu scrollable des balises
        tk.Label(
            body,
            text="Aperçu des balises :",
            font=("Segoe UI", 9, "bold"),
            bg="white",
            anchor="w",
        ).pack(fill="x")
        frm_preview = tk.Frame(body, bg="#f8f8f8", relief="solid", bd=1)
        frm_preview.pack(fill="x", pady=(4, 8))
        txt = tk.Text(
            frm_preview,
            height=3,
            font=("Segoe UI", 9),
            bg="#f8f8f8",
            fg="#222",
            relief="flat",
            wrap="word",
        )
        sb = tk.Scrollbar(frm_preview, orient="vertical", command=txt.yview)
        txt.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        txt.pack(fill="x", padx=4, pady=4)
        txt.insert("1.0", " - ".join(str(b) for b in balises))
        txt.config(state="disabled")
        # Ordre obligatoire
        var_ordre = tk.BooleanVar(value=False)
        frm_ord = tk.Frame(body, bg="white")
        frm_ord.pack(anchor="w")
        tk.Checkbutton(
            frm_ord,
            text="Ordre obligatoire",
            variable=var_ordre,
            font=("Segoe UI", 9),
            bg="white",
            cursor="hand2",
            activebackground="white",
        ).pack(side="left")
        # Barre de boutons
        barre = tk.Frame(dlg, bg="#f5f5f5", pady=8)
        barre.pack(fill="x", side="bottom")

        def _ok():
            result[0] = (
                var_nom.get().strip() or nom_defaut,
                list(balises),
                var_ordre.get(),
            )
            dlg.destroy()

        def _annuler():
            dlg.destroy()
        tk.Button(
            barre,
            text="Annuler",
            font=("Segoe UI", 9),
            bg="#e0e0e0",
            fg="#333",
            relief="flat",
            cursor="hand2",
            activebackground="#ccc",
            command=_annuler,
        ).pack(side="right", padx=8, ipadx=8, ipady=4)
        tk.Button(
            barre,
            text="Importer",
            font=("Segoe UI", 9),
            bg="#16a085",
            fg="white",
            relief="flat",
            cursor="hand2",
            activebackground="#1a8a72",
            activeforeground="white",
            command=_ok,
        ).pack(side="right", ipadx=8, ipady=4)
        dlg.wait_window()
        return result[0]
    # OCAD : import IOF XML / texte

    def _importer_ocad(self):
        """
        importe un fichier OCAD : IOF XML (v2/v3) ou Export Courses Text (.txt)."""
        chemin = filedialog.askopenfilename(
            filetypes=[
                ("Fichiers OCAD", "*.xml *.txt"),
                ("IOF XML", "*.xml"),
                ("OCAD Courses Text", "*.txt"),
                ("Tous les fichiers", "*.*"),
            ],
            title="Importer depuis OCAD",
            parent=self,
        )
        if not chemin:
            return
        try:
            ext = os.path.splitext(chemin)[1].lower()
            lots = (
                self._parser_ocad_xml(chemin)
                if ext == ".xml"
                else self._parser_ocad_txt(chemin)
            )
        except Exception as e:
            messagebox.showerror(
                "Erreur", f"Impossible de lire le fichier OCAD :\n{e}", parent=self
            )
            return
        if not lots:
            messagebox.showwarning(
                "Aucun parcours",
                "Aucun parcours avec balises valides (entre "
                f"{BALISE_MIN} et {BALISE_MAX}) trouvé dans ce fichier.",
                parent=self,
            )
            return
        # Si le fallback a été utilisé (fichier = liste de contrôles sans parcours définis)
        if len(lots) == 1 and lots[0].pop("_fallback", False):
            nb = len(lots[0]["balises"])
            rep = messagebox.askyesno(
                "Aucun parcours défini",
                f"Ce fichier ne contient pas de parcours définis,\n"
                f"mais liste {nb} balise(s) disponible(s) sur le terrain.\n\n"
                f"Voulez-vous les importer comme sélection de balises\n"
                f"(vous pourrez ensuite désélectionner celles inutilisées) ?",
                parent=self,
            )
            if not rep:
                return
        if len(lots) == 1:
            data = lots[0]
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
            self._est_sauvegarde = True
            self._rafraichir_grille()
            self._lbl_status.config(
                text=f"OCAD importé : {len(self._balises_sel)} balise(s) - {os.path.basename(chemin)}"
            )
        else:
            self._lot = lots
            self._rafraichir_lot()
            self._lbl_status.config(
                text=f"Lot OCAD importé : {len(lots)} parcours - {os.path.basename(chemin)}"
            )

    @staticmethod
    def _parser_ocad_xml(chemin):
        """
        Parse un fichier IOF XML OCAD (v2.0.3 ou v3.0).
        Gère l'absence de namespace (exports OCAD classiques) et la structure
        <CourseVariation> de certaines versions.
        Retourne une liste de dicts {nom, balises, ordre}.
        """
        import xml.etree.ElementTree as ET
        import re
        tree = ET.parse(chemin)
        root = tree.getroot()
        # Extraire le namespace depuis le tag racine ({uri}LocalName)
        m = re.match(r"\{(.+?)\}", root.tag)
        ns_uri = m.group(1) if m else ""

        def tag(name):
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

    @staticmethod
    def _parser_ocad_txt(chemin):
        """
        Parse un fichier 'Export Courses Text' OCAD.
        Format : Nom\tLongueur\tDéniv\tNbCtrl\tS1-31-42-53-...-F1
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

    def _adapter_grille_cols(self, largeur):
        """Recalcule et applique le nombre de colonnes selon la largeur du canvas."""
        if largeur <= 1:
            return
        # Largeur minimale par colonne ~44px (les colonnes s'étirent pour remplir)
        ncols = max(5, largeur // 44)
        if ncols == self._grille_ncols:
            return
        old_ncols = self._grille_ncols
        self._grille_ncols = ncols
        # Réinitialiser les anciennes colonnes puis configurer les nouvelles
        for c in range(old_ncols):
            self._frame_grille.columnconfigure(c, weight=0, uniform="")
        for c in range(ncols):
            self._frame_grille.columnconfigure(c, weight=1, uniform="balise")
        for i, b in enumerate(BALISES_TOUTES):
            row, col = divmod(i, ncols)
            self._toggle_btns[b].grid(
                row=row, column=col, sticky="ew", padx=2, pady=2, ipady=3
            )
        self._frame_grille.update_idletasks()
        self._grille_canvas.configure(scrollregion=self._grille_canvas.bbox("all"))

    def _on_toggle_ordre(self):
        """Appelé lors du changement de la case 'Ordre obligatoire'."""
        self._est_sauvegarde = False
        self._rafraichir_grille()
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

    @staticmethod
    def _parser_lot_tsv(chemin):
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

    @staticmethod
    def _parser_lot_csv(chemin):
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

    def _lancer_lecture(self):
        """Lance la lecture du parcours (ou du lot si des parcours y ont été ajoutés)."""
        if self._lot:
            self._lancer_lot()
            return
        if not self._valider():
            return
        data = self._get_data()
        if not self._est_sauvegarde:
            rep = messagebox.askyesnocancel(
                "Parcours non enregistré",
                "Le parcours n'a pas encore été enregistré.\n\n"
                "- Oui  - Enregistrer puis lancer la lecture\n"
                "- Non  - Lancer directement (session uniquement)\n"
                "- Annuler - Retour",
                parent=self,
            )
            if rep is None:  # Annuler
                return
            if rep:  # Oui - enregistrer d'abord
                chemin = self._choisir_chemin(data)
                if not chemin:
                    return
                try:
                    self._sauvegarder(chemin, data)
                except Exception as e:
                    messagebox.showerror(
                        "Erreur", f"Impossible d'enregistrer :\n{e}", parent=self
                    )
                    return
                self._est_sauvegarde = True
            # rep is False - lancer directement sans enregistrer
        if self._on_done:
            self._on_done(data)

    def _annuler(self):
        if self._on_cancel:
            self._on_cancel()


if __name__ == "__main__":
    root = tk.Tk()
    root.title("Construction de Parcours - SportIdent")
    root.geometry("520x460")
    root.resizable(False, False)
    AppParcours(root, on_cancel=root.destroy)
    root.mainloop()