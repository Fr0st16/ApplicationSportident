#!/usr/bin/env python3
"""Hub de lecture multi-parcours (mixin de MainApp).

Regroupe toute la logique de l'onglet "Lecture en cours" : construction du
panneau de navigation/lecture, routage automatique d'une puce lue vers le
bon parcours (score d'intersection de balises), validation en mode
contrôlée, export CSV agrégé de tous les parcours ouverts.

Extrait de main.py (~1100 des ~1380 lignes d'origine) sans changement de
comportement : HubMixin est mélangé (mixin) dans MainApp (ui/app_main.py),
qui garde l'état (self._hub_*, self._lecture_apps, ...) initialisé dans
son __init__ ; les méthodes ci-dessous continuent d'y accéder via `self`
exactement comme avant.
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import os
from datetime import datetime


class HubMixin:
    """Mixin de MainApp : gère l'onglet unique "Lecture en cours" regroupant
    tous les parcours ouverts (navigation, connexion partagée au lecteur SI,
    routage automatique d'une puce vers le bon parcours, validation en mode
    contrôlée, export CSV agrégé). Toutes les méthodes ci-dessous accèdent à
    l'état défini dans MainApp.__init__ (self._hub_*, self._lecture_apps, ...)."""

    def _ouvrir_lecture(self, parcours, shared=True):
        """Crée un AppLecturePuce pour ce parcours (ou None = lecture libre)
        et l'ajoute au hub. `shared=True` (le cas normal) branche les callbacks
        de routage/connexion partagée : une seule connexion physique au lecteur
        SI est utilisée pour tous les parcours ouverts."""
        from ui.lecture_puce import AppLecturePuce
        self._ensure_lecture_hub()
        self.notebook.select(self._lecture_hub_tab)

        app_ref = [None]
        app_lecture = AppLecturePuce(
            self._hub_content,
            parcours=parcours,
            on_close=lambda: self._fermer_hub_app(app_ref[0]),
            on_broadcast=self._on_card_broadcast,
            on_request_reader=self._on_reader_claimed if shared else None,
            on_route_puce=self._on_puce_routed if shared else None,
            on_request_move=self._on_request_move,
            on_export_all=self._exporter_tous,
            on_candidats_loaded=self._on_candidats_broadcast,
            images_balises=self._images_balises,
        )
        app_ref[0] = app_lecture
        if self._hub_candidats:
            app_lecture._appliquer_candidats(self._hub_candidats)
        app_lecture.pack_forget()
        app_lecture.place_forget()

        self._hub_apps.append(app_lecture)
        self._lecture_apps.append(app_lecture)
        self._hub_refresh_list()

        # Forcer l'affichage du panneau "Lecture" (pas le parcours qui vient d'être ouvert).
        # On annule un éventuel appel déjà programmé pour éviter les doubles déclenchements
        # lors d'un chargement par lot (plusieurs parcours d'un coup).
        if getattr(self, "_go_lecture_after_id", None):
            try:
                self.root.after_cancel(self._go_lecture_after_id)
            except Exception:
                pass
        self._go_lecture_after_id = self.root.after(50, self._hub_go_lecture)

    # ─────────────────────────────────────
    #  Hub de lecture (onglet unique multi-parcours)
    # ─────────────────────────────────────

    def _ensure_lecture_hub(self):
        """Crée l'onglet "Lecture en cours" s'il n'existe pas encore (idempotent :
        ne fait rien si l'onglet est déjà ouvert)."""
        if self._lecture_hub_tab is not None:
            try:
                if self._lecture_hub_tab.winfo_exists():
                    return
            except Exception:
                pass
        self._lecture_hub_tab = tk.Frame(self.notebook)
        self.notebook.add(self._lecture_hub_tab, text="  Lecture en cours  ×")
        self._tab_close_cbs[self._lecture_hub_tab] = self._fermer_hub_complet
        self._build_lecture_hub()

    def _build_lecture_hub(self):
        """Construit la structure de l'onglet hub : bandeau titre, navigation
        gauche (listbox des parcours ouverts) et zone de contenu droite."""
        tab = self._lecture_hub_tab

        hdr = tk.Frame(tab, bg="#1e1e2e")
        hdr.pack(fill="x")
        tk.Label(
            hdr, text="Lecture en cours",
            font=("Segoe UI", 11, "bold"), bg="#1e1e2e", fg="white",
        ).pack(side="left", padx=14, pady=8)

        body = tk.Frame(tab)
        body.pack(fill="both", expand=True)

        nav = tk.Frame(body, bg="#f4f4f4", width=210)
        nav.pack(side="left", fill="y")
        nav.pack_propagate(False)

        tk.Label(
            nav, text="Parcours ouverts",
            font=("Segoe UI", 9, "bold"), bg="#f4f4f4", fg="#333",
        ).pack(anchor="w", padx=10, pady=(10, 2))

        self._hub_btn_lecture = tk.Button(
            nav, text="▶  Menu",
            font=("Segoe UI", 9, "bold"), relief="flat", cursor="hand2",
            bg="#1a73e8", fg="white",
            activebackground="#1558b0", activeforeground="white",
            command=self._hub_go_lecture,
        )
        self._hub_btn_lecture.pack(fill="x", padx=8, pady=(2, 6), ipady=5)

        self._hub_count_lbl = tk.Label(
            nav, text="", font=("Segoe UI", 8), bg="#f4f4f4", fg="#888",
        )
        self._hub_count_lbl.pack(anchor="w", padx=10)

        lbf = tk.Frame(nav, bg="#f4f4f4")
        lbf.pack(fill="both", expand=True, padx=6, pady=6)
        sb = tk.Scrollbar(lbf, orient="vertical")
        sb.pack(side="right", fill="y")
        self._hub_listbox = tk.Listbox(
            lbf, font=("Segoe UI", 10), yscrollcommand=sb.set,
            selectmode="single", activestyle="none",
            bg="white", relief="flat", bd=1, highlightthickness=0,
            selectbackground="#1a73e8", selectforeground="white",
        )
        self._hub_listbox.pack(fill="both", expand=True)
        sb.config(command=self._hub_listbox.yview)
        self._hub_listbox.bind("<<ListboxSelect>>", self._on_hub_nav_select)

        tk.Button(
            nav, text="✕  Fermer ce parcours",
            font=("Segoe UI", 8), relief="flat", cursor="hand2",
            bg="#e74c3c", fg="white",
            activebackground="#c0392b", activeforeground="white",
            command=self._fermer_hub_app_selected,
        ).pack(fill="x", padx=8, pady=(8, 4), ipady=4)

        tk.Button(
            nav, text="✎  Modifier les parcours",
            font=("Segoe UI", 8), relief="flat", cursor="hand2",
            bg="#1a73e8", fg="white",
            activebackground="#1558b0", activeforeground="white",
            command=self._modifier_parcours_hub,
        ).pack(fill="x", padx=8, pady=(0, 8), ipady=4)

        ttk.Separator(body, orient="vertical").pack(side="left", fill="y")

        self._hub_content = tk.Frame(body)
        self._hub_content.pack(side="left", fill="both", expand=True)

        # Panneau global de lecture — un seul bouton pour tous les parcours ouverts
        self._hub_panel_lecture = tk.Frame(self._hub_content, bg="white")
        self._build_hub_panel_lecture()

    def _build_hub_panel_lecture(self):
        """Construit le panneau de lecture global — reprend tous les boutons d'origine
        de tab_lecture, mais appliqués à l'ensemble des parcours ouverts."""
        f = self._hub_panel_lecture

        tk.Label(
            f, text="Cliquez sur le bouton puis posez la puce sur la station.",
            font=("Segoe UI", 9), fg="#555", bg="white"
        ).pack(padx=10, pady=10)

        self._hub_mode = "libre"
        self._hub_btn_mode = tk.Button(
            f, text="Mode : Libre",
            font=("Segoe UI", 10, "bold"),
            bg="#34495e", fg="white",
            activebackground="#2c3e50", activeforeground="white",
            relief="flat", cursor="hand2",
            command=self._hub_toggle_mode,
        )
        self._hub_btn_mode.pack(fill="x", padx=10, pady=(0, 8), ipady=7)

        frame_liste = tk.Frame(f, bg="white")
        frame_liste.pack(fill="x", padx=10, pady=(0, 4))
        self._hub_btn_charger_liste = tk.Button(
            frame_liste, text="Charger liste candidats (CSV)",
            font=("Segoe UI", 9),
            bg="#8e44ad", fg="white",
            activebackground="#6c3483", activeforeground="white",
            relief="flat", cursor="hand2",
            command=self._hub_charger_liste_candidats,
        )
        self._hub_btn_charger_liste.pack(fill="x", ipady=5)
        self._hub_lbl_liste = tk.Label(
            frame_liste,
            text="Aucune liste chargée - les noms seront saisis manuellement.",
            font=("Segoe UI", 8), fg="#888", bg="white"
        )
        self._hub_lbl_liste.pack(anchor="w", pady=(2, 0))

        frame_images = tk.Frame(f, bg="white")
        frame_images.pack(fill="x", padx=10, pady=(4, 0))
        self._hub_btn_charger_images = tk.Button(
            frame_images, text="Charger images balises (dossier)",
            font=("Segoe UI", 9),
            bg="#2980b9", fg="white",
            activebackground="#2471a3", activeforeground="white",
            relief="flat", cursor="hand2",
            command=self._hub_charger_images,
        )
        self._hub_btn_charger_images.pack(fill="x", ipady=5)
        self._hub_lbl_images = tk.Label(
            frame_images,
            text="Aucune image chargée.",
            font=("Segoe UI", 8), fg="#888", bg="white"
        )
        self._hub_lbl_images.pack(anchor="w", pady=(2, 0))
        self._hub_lbl_status = tk.Label(
            f, text="", font=("Segoe UI", 9), fg="#888", bg="white"
        )
        self._hub_lbl_status.pack(padx=10, pady=(2, 0), anchor="w")

        self._hub_btn_attendre = tk.Button(
            f, text="Attendre une puce",
            font=("Segoe UI", 11, "bold"),
            bg="#1a73e8", fg="white",
            activebackground="#1558b0", activeforeground="white",
            relief="flat", cursor="hand2",
            command=self._hub_demarrer_lecture,
        )
        self._hub_btn_attendre.pack(fill="x", padx=10, pady=10, ipady=10)

        self._hub_btn_annuler = tk.Button(
            f, text="Annuler la lecture",
            font=("Segoe UI", 10),
            bg="#e74c3c", fg="white",
            activebackground="#c0392b", activeforeground="white",
            relief="flat", cursor="hand2",
            command=self._hub_annuler_lecture,
        )
        # Caché par défaut, affiché uniquement pendant la lecture

        ttk.Separator(f, orient="horizontal").pack(fill="x", padx=10, pady=16)

        tk.Button(
            f, text="↧  Exporter tous les parcours (CSV)",
            font=("Segoe UI", 10),
            bg="#16a085", fg="white",
            activebackground="#1a7a61", activeforeground="white",
            relief="flat", cursor="hand2",
            command=self._exporter_tous,
        ).pack(fill="x", padx=10, pady=(0, 6), ipady=6)

        tk.Button(
            f, text="Effacer toutes les puces",
            font=("Segoe UI", 10),
            bg="#7f8c8d", fg="white",
            activebackground="#636e72", activeforeground="white",
            relief="flat", cursor="hand2",
            command=self._hub_effacer_toutes,
        ).pack(fill="x", padx=10, ipady=6)

    def _hub_toggle_mode(self):
        """Bascule le mode libre/contrôlée sur tous les parcours ouverts du hub."""
        if self._hub_mode == "libre":
            self._hub_mode = "controlee"
            self._hub_btn_mode.config(text="Mode : Contrôlée", bg="#8e44ad", activebackground="#6c3483")
        else:
            self._hub_mode = "libre"
            self._hub_btn_mode.config(text="Mode : Libre", bg="#34495e", activebackground="#2c3e50")
        for app in self._hub_apps:
            try:
                app._mode_lecture = self._hub_mode
            except Exception:
                pass

    def _hub_charger_liste_candidats(self):
        """Charge une liste de candidats CSV et la propage à tous les parcours du hub."""
        chemin = filedialog.askopenfilename(
            filetypes=[("Fichier CSV", "*.csv"), ("Tous les fichiers", "*.*")],
            title="Charger liste candidats",
        )
        if not chemin:
            return
        try:
            from io_.candidats_csv import parse_candidate_csv
            candidats = parse_candidate_csv(chemin)
        except Exception as e:
            messagebox.showerror("Erreur", f"Impossible de charger le fichier :\n{e}", parent=self.root)
            return
        self._hub_candidats = candidats
        nb = len(candidats)
        self._hub_lbl_liste.config(text=f"✓  {nb} candidat(s) chargé(s)", fg="#27ae60")
        for app in self._hub_apps:
            try:
                app._appliquer_candidats(candidats)
            except Exception:
                pass

    def _hub_charger_images(self):
        """Charge un dossier d'images et associe chaque fichier à son numéro de balise."""
        dossier = filedialog.askdirectory(
            title="Choisir le dossier d'images des balises", parent=self.root
        )
        if not dossier:
            return
        extensions_valides = {'.png', '.gif', '.jpg', '.jpeg', '.bmp', '.webp'}
        images = {}
        for nom_fichier in os.listdir(dossier):
            nom, ext = os.path.splitext(nom_fichier)
            if ext.lower() not in extensions_valides:
                continue
            try:
                num = int(nom)
            except ValueError:
                continue
            images[num] = os.path.join(dossier, nom_fichier)
        self._images_balises = images
        nb = len(images)
        if self._hub_lbl_images:
            if nb > 0:
                self._hub_lbl_images.config(text=f"✓  {nb} image(s) chargée(s)", fg="#27ae60")
            else:
                self._hub_lbl_images.config(
                    text="Aucune image valide trouvée dans ce dossier.", fg="#e74c3c"
                )
        for app in self._hub_apps:
            try:
                app._appliquer_images(images)
            except Exception:
                pass

    def _hub_effacer_toutes(self):
        """Efface toutes les puces de tous les parcours ouverts."""
        nb_total = sum(len(a._frames) for a in self._hub_apps if hasattr(a, "_frames"))
        if nb_total == 0:
            return
        if not messagebox.askyesno(
            "Effacer toutes les puces",
            f"Voulez-vous effacer les {nb_total} puce(s) lue(s) sur tous les parcours ?",
            icon="warning", parent=self.root,
        ):
            return
        for app in self._hub_apps:
            try:
                if app.winfo_exists():
                    app._effacer_toutes_puces()
            except Exception:
                pass
        self._hub_refresh_list()

    def _hub_demarrer_lecture(self):
        """Démarre la lecture sur le hub : une seule app physique écoute,
        la puce est ensuite routée automatiquement vers le bon parcours."""
        self._hub_apps = [a for a in self._hub_apps if self._app_existe(a)]
        if not self._hub_apps:
            messagebox.showinfo("Lecture", "Aucun parcours ouvert.", parent=self.root)
            return

        # Choisir une app déjà connectée si possible, sinon la première
        app_lecteur = next((a for a in self._hub_apps if a.si is not None), self._hub_apps[0])
        self._hub_app_en_ecoute = app_lecteur
        try:
            app_lecteur._mode_lecture = self._hub_mode
        except Exception:
            pass

        self._hub_btn_attendre.config(state="disabled")
        if app_lecteur.si is not None:
            self._hub_btn_attendre.config(
                text="Lecture en cours...", bg="#1a73e8", activebackground="#1558b0",
            )
        else:
            self._hub_btn_attendre.config(
                text="Connexion...", bg="#888", activebackground="#636e72",
            )
        # Annuler disponible immédiatement (connexion peut être longue sur Bluetooth)
        self._hub_btn_annuler.pack(fill="x", padx=10, pady=(0, 10), ipady=6, after=self._hub_btn_attendre)

        try:
            app_lecteur._demarrer_lecture()
        except Exception as e:
            messagebox.showerror("Erreur", f"Impossible de démarrer la lecture :\n{e}", parent=self.root)
            self._hub_reset_btn_lecture()

    def _hub_annuler_lecture(self):
        """Annule la lecture en cours sur l'app physique active."""
        app = getattr(self, "_hub_app_en_ecoute", None)
        if app is not None:
            try:
                app._annuler_lecture()
            except Exception:
                pass
        self._hub_reset_btn_lecture()

    def _hub_reset_btn_lecture(self):
        """Remet le bouton "Attendre une puce" en état repos, en rouge
        "Relancer" si la dernière tentative de connexion a échoué."""
        try:
            self._hub_btn_annuler.pack_forget()
        except Exception:
            pass
        app = getattr(self, "_hub_app_en_ecoute", None)
        en_erreur = bool(getattr(app, "_erreur_connexion", False)) if app is not None else False
        try:
            if en_erreur:
                self._hub_btn_attendre.config(
                    state="normal", text="Relancer",
                    bg="#e74c3c", activebackground="#c0392b",
                )
            else:
                self._hub_btn_attendre.config(
                    state="normal", text="Attendre une puce",
                    bg="#1a73e8", activebackground="#1558b0",
                )
        except Exception:
            pass
        try:
            self._hub_lbl_status.config(text="")
        except Exception:
            pass

    def _hub_show_app(self, app):
        """Affiche le parcours `app` dans la zone de contenu du hub (masque
        les autres parcours et le panneau global), et sélectionne son entrée
        dans la listbox de navigation."""
        try:
            if not app.winfo_exists():
                return
        except Exception:
            return

        for a in self._hub_apps:
            try:
                if a is not app and a.winfo_exists():
                    a.place_forget()
            except Exception:
                pass

        self._hub_current = app
        # Cacher le panneau lecture global s'il est affiché
        try:
            if hasattr(self, '_hub_panel_lecture') and self._hub_panel_lecture:
                self._hub_panel_lecture.place_forget()
        except Exception:
            pass
        try:
            app.place(in_=self._hub_content, x=0, y=0, relwidth=1, relheight=1)
        except Exception:
            pass

        # Masquer tab_lecture si affiché — la zone blanche montre les puces
        try:
            if app.tab_lecture and app._current is app.tab_lecture:
                app.tab_lecture.pack_forget()
                app._current = None
        except Exception:
            pass

        # Remettre la sidebar visible
        try:
            app._set_sidebar_visible(True)
        except Exception:
            pass

        if app in self._hub_apps:
            idx = self._hub_apps.index(app)
            try:
                self._hub_listbox.selection_clear(0, "end")
                self._hub_listbox.selection_set(idx)
                self._hub_listbox.see(idx)
            except Exception:
                pass

    def _hub_refresh_list(self):
        """Reconstruit la listbox de navigation (nom + badge nombre de puces
        lues par parcours) et purge les apps dont le widget a été détruit."""
        if self._hub_listbox is None:
            return

        self._hub_apps = [a for a in self._hub_apps if self._app_existe(a)]
        self._lecture_apps = [a for a in self._lecture_apps if self._app_existe(a)]

        cur_sel = self._hub_listbox.curselection()
        cur_idx = cur_sel[0] if cur_sel else None

        self._hub_listbox.delete(0, "end")
        for app in self._hub_apps:
            nom = app._parcours["nom"] if app._parcours else "Lecture libre"
            nb = len(app._frames) if hasattr(app, "_frames") else 0
            badge = f"  [{nb}]"
            label = f"  {nom}{badge}"
            self._hub_listbox.insert("end", label)
            fg = "#27ae60" if nb > 0 else "#444"
            self._hub_listbox.itemconfig("end", fg=fg)

        nb_total = len(self._hub_apps)
        if self._hub_count_lbl:
            self._hub_count_lbl.config(
                text=f"{nb_total} parcours" if nb_total != 1 else "1 parcours"
            )
        if self._hub_current in self._hub_apps:
            idx = self._hub_apps.index(self._hub_current)
            try:
                self._hub_listbox.selection_clear(0, "end")
                self._hub_listbox.selection_set(idx)
                self._hub_listbox.see(idx)
            except Exception:
                pass
        elif cur_idx is not None and cur_idx < nb_total:
            self._hub_listbox.selection_set(cur_idx)

    def _modifier_parcours_hub(self):
        """Ouvre l'éditeur de parcours pré-rempli avec tous les parcours actuellement
        ouverts dans le hub, pour les modifier puis relancer la lecture. Propose
        d'exporter en CSV d'abord si des puces ont déjà été lues (elles seraient
        perdues, chaque parcours étant recréé à la relance)."""
        from ui.parcours import AppParcours

        nb_puces = sum(len(app._frames) for app in self._hub_apps if hasattr(app, "_frames"))
        if nb_puces > 0:
            rep = messagebox.askyesnocancel(
                "Données non sauvegardées",
                f"{nb_puces} puce(s) lue(s) seront perdues si vous relancez la lecture.\n\n"
                "Voulez-vous exporter les données en CSV avant de modifier les parcours ?",
                icon="warning",
                parent=self.root,
            )
            if rep is None:
                return
            if rep:
                self._exporter_tous()

        lot = [dict(app._parcours) for app in self._hub_apps if app._parcours]
        tab = tk.Frame(self.notebook)
        self.notebook.add(tab, text="  Modifier parcours  ×")
        self.notebook.select(tab)
        self._tab_close_cbs[tab] = lambda t=tab: self._fermer_tab(t)

        def on_done_modifier(data, t=tab):
            """Ferme le hub existant et le reconstruit avec les parcours modifiés."""
            for app in list(self._hub_apps):
                try:
                    if getattr(app, "si", None) is not None:
                        try:
                            app.si.disconnect()
                        except Exception:
                            pass
                except Exception:
                    pass
                try:
                    app._on_close()
                except Exception:
                    pass
            self._on_parcours_done(data, t)

        AppParcours(
            tab,
            on_done=on_done_modifier,
            on_cancel=lambda t=tab: self._fermer_tab(t),
            initial_lot=lot if lot else None,
        )

    def _hub_go_lecture(self):
        """Affiche le panneau global de lecture (un seul bouton pour tous les parcours)."""
        if self._hub_panel_lecture is None:
            return

        # Cacher toutes les apps
        for a in self._hub_apps:
            try:
                if a.winfo_exists():
                    a.place_forget()
            except Exception:
                pass
        self._hub_current = None

        # Désélectionner la listbox
        try:
            self._hub_listbox.selection_clear(0, "end")
        except Exception:
            pass

        # Mettre à jour le statut de la liste candidats (depuis la 1ère app)
        try:
            if self._hub_apps:
                nb = len(self._hub_apps[0]._liste_candidats)
                if nb > 0:
                    self._hub_lbl_liste.config(text=f"✓  {nb} candidat(s) chargé(s)", fg="#27ae60")
                else:
                    self._hub_lbl_liste.config(
                        text="Aucune liste chargée - les noms seront saisis manuellement.",
                        fg="#888"
                    )
        except Exception:
            pass

        # Mettre à jour le statut des images
        try:
            nb_img = len(self._images_balises)
            if self._hub_lbl_images:
                if nb_img > 0:
                    self._hub_lbl_images.config(text=f"✓  {nb_img} image(s) chargée(s)", fg="#27ae60")
                else:
                    self._hub_lbl_images.config(text="Aucune image chargée.", fg="#888")
        except Exception:
            pass

        # Afficher le panneau global (superposé exactement dans _hub_content)
        try:
            self._hub_panel_lecture.place(in_=self._hub_content, x=0, y=0, relwidth=1, relheight=1)
        except Exception:
            pass

    def _on_app_status(self, event):
        """Relaie le statut de l'app en train d'écouter vers le panneau global."""
        app = getattr(self, "_hub_app_en_ecoute", None)
        if app is None:
            return
        try:
            msg, ok = getattr(app, "_last_status_msg", ("", True))
            if msg and ok and "le port" in msg:
                # Connexion réussie : afficher le port et passer en état de lecture
                if getattr(self, "_hub_lbl_status", None):
                    self._hub_lbl_status.config(text=msg, fg="#27ae60")
                try:
                    if self._hub_btn_attendre.cget("text") == "Connexion...":
                        self._hub_btn_attendre.config(
                            text="Lecture en cours...", bg="#1a73e8", activebackground="#1558b0",
                        )
                except Exception:
                    pass
        except Exception:
            pass

    def _app_existe(self, app):
        """True si le widget Tkinter de cette app n'a pas été détruit."""
        try:
            return app.winfo_exists()
        except Exception:
            return False

    def _on_hub_nav_select(self, event):
        """Réaction au clic dans la liste — remet la sidebar visible."""
        sel = self._hub_listbox.curselection()
        if not sel:
            return
        idx = sel[0]
        if 0 <= idx < len(self._hub_apps):
            app = self._hub_apps[idx]
            self._hub_show_app(app)  # _hub_show_app remet sidebar + cache tab_lecture

    def _fermer_hub_app(self, app):
        """Retire un parcours du hub sans confirmation ni export (utilisé en
        callback `on_close` d'AppLecturePuce). Si c'était le dernier parcours
        ouvert, ferme l'onglet hub entier et réinitialise ses références."""
        if app is None:
            return
        try:
            app.place_forget()
        except Exception:
            pass
        idx = self._hub_apps.index(app) if app in self._hub_apps else 0
        self._hub_apps = [a for a in self._hub_apps if a is not app]
        self._lecture_apps = [a for a in self._lecture_apps if a is not app]

        if self._hub_current is app:
            self._hub_current = None
            if self._hub_apps:
                new_idx = min(idx, len(self._hub_apps) - 1)
                self._hub_show_app(self._hub_apps[new_idx])
            else:
                self._hub_go_lecture()

        self._hub_refresh_list()

        if not self._hub_apps:
            if self._lecture_hub_tab is not None:
                try:
                    self._fermer_tab(self._lecture_hub_tab)
                except Exception:
                    pass
                self._lecture_hub_tab = None
                self._hub_listbox = None
                self._hub_content = None
                self._hub_count_lbl = None
                self._hub_btn_lecture = None
                self._hub_panel_lecture = None
                self._hub_btn_attendre = None
                self._hub_btn_annuler = None
                self._hub_lbl_status = None
                self._hub_lbl_liste = None
                self._hub_btn_mode = None
                self._hub_btn_charger_liste = None
                self._hub_btn_charger_images = None
                self._hub_lbl_images = None

    def _fermer_hub_app_selected(self):
        """Ferme le parcours sélectionné dans la navigation (bouton "Fermer ce
        parcours"), avec confirmation d'export CSV si des puces y ont été lues."""
        sel = self._hub_listbox.curselection() if self._hub_listbox else ()
        if not sel:
            return
        idx = sel[0]
        if not (0 <= idx < len(self._hub_apps)):
            return
        app = self._hub_apps[idx]
        nb = len(app._frames) if hasattr(app, "_frames") else 0
        if nb > 0:
            nom = app._parcours["nom"] if app._parcours else "Lecture libre"
            rep = messagebox.askyesnocancel(
                "Fermer le parcours",
                f"Le parcours « {nom} » contient {nb} puce(s) lue(s).\n\n"
                "Voulez-vous exporter les résultats en CSV avant de fermer ?",
                icon="warning",
                parent=self.root,
            )
            if rep is None:
                return
            if rep:
                exported = app._exporter_csv()
                if not exported:
                    return
        # Déconnecter le port série de manière synchrone par sécurité
        try:
            if getattr(app, "si", None) is not None:
                try:
                    app.si.disconnect()
                except Exception:
                    pass
        except Exception:
            pass
        app._on_close()

    def _fermer_hub_complet(self):
        """Ferme tout le hub d'un coup (croix de l'onglet), avec confirmation
        d'export CSV global si des puces ont été lues sur au moins un parcours."""
        if not self._hub_apps:
            if self._lecture_hub_tab:
                self._fermer_tab(self._lecture_hub_tab)
            return

        nb_total = sum(len(app._frames) if hasattr(app, "_frames") else 0 for app in self._hub_apps)
        if nb_total > 0:
            rep = messagebox.askyesnocancel(
                "Fermer tous les parcours",
                f"Il y a {nb_total} puce(s) lue(s) au total.\n\n"
                "Voulez-vous exporter les résultats en CSV avant de fermer ?",
                icon="warning",
                parent=self.root,
            )
            if rep is None:
                return
            if rep:
                self._exporter_tous()

        apps_copy = list(self._hub_apps)
        for app in apps_copy:
            # Déconnecter le port série de manière synchrone AVANT de détruire les
            # widgets : _on_close() programme la déconnexion via after(100, ...),
            # mais si on détruit l'onglet immédiatement après, ce callback différé
            # n'a jamais l'occasion de s'exécuter et le port série reste verrouillé.
            try:
                if getattr(app, "si", None) is not None:
                    app._lire_en_cours = False
                    app._closing = True
                    try:
                        app._card_event.set()
                    except Exception:
                        pass
                    try:
                        app.si.disconnect()
                    except Exception:
                        pass
                    app.si = None
            except Exception:
                pass
            try:
                app._on_close()
            except Exception:
                pass

        self._hub_apps.clear()
        self._lecture_apps.clear()
        self._hub_current = None
        if self._lecture_hub_tab:
            try:
                self._fermer_tab(self._lecture_hub_tab)
            except Exception:
                pass
            self._lecture_hub_tab = None
            self._hub_listbox = None
            self._hub_content = None
            self._hub_count_lbl = None

    def _on_candidats_broadcast(self, source_app, candidats):
        """Propage une liste de candidats chargée dans un parcours vers tous
        les autres parcours ouverts du hub."""
        self._lecture_apps = [a for a in self._lecture_apps if a.winfo_exists()]
        for app in self._lecture_apps:
            if app is not source_app:
                app._appliquer_candidats(candidats)

    def _on_reader_claimed(self, requester_app):
        """Un parcours vient de prendre la main sur le lecteur SI physique
        (une seule connexion à la fois) : force les autres à la relâcher."""
        self._lecture_apps = [a for a in self._lecture_apps if a.winfo_exists()]
        for app in self._lecture_apps:
            if app is not requester_app:
                app._release_reader()

    def _on_request_move(self, source_app, card_number):
        """Ouvre une boîte de dialogue pour déplacer manuellement une puce
        déjà enregistrée vers un autre parcours ouvert du hub."""
        self._lecture_apps = [a for a in self._lecture_apps if a.winfo_exists()]
        targets = [a for a in self._lecture_apps if a is not source_app]
        if not targets:
            messagebox.showinfo("Déplacer", "Aucun autre parcours ouvert pour déplacer la puce.", parent=self.root)
            return

        dlg = tk.Toplevel(self.root)
        dlg.title("Déplacer la puce vers...")
        dlg.geometry("360x300")
        dlg.transient(self.root)
        dlg.grab_set()
        tk.Label(dlg, text="Choisir le parcours de destination :", font=("Segoe UI", 10)).pack(pady=8)
        lb = tk.Listbox(dlg)
        for t in targets:
            name = t._parcours["nom"] if t._parcours else "Lecture libre"
            lb.insert("end", name)
        lb.pack(fill="both", expand=True, padx=12, pady=8)
        sel = {"idx": None}

        def on_ok():
            """Valide la sélection dans la listbox et ferme la boîte de dialogue."""
            s = lb.curselection()
            if not s:
                return
            sel["idx"] = s[0]
            dlg.destroy()

        btnf = tk.Frame(dlg)
        btnf.pack(pady=8)
        tk.Button(btnf, text="Annuler", command=dlg.destroy, bg="#888", fg="white", relief="flat").pack(side="left", padx=6)
        tk.Button(btnf, text="Déplacer", command=on_ok, bg="#1a73e8", fg="white", relief="flat").pack(side="left")
        self.root.wait_window(dlg)
        if sel["idx"] is None:
            return

        target = targets[sel["idx"]]
        try:
            self._card_assignments[card_number] = target
        except Exception:
            pass
        passages = list(source_app._card_data.get(card_number, []))
        nom = source_app._noms.get(card_number, "")
        for passage in passages:
            target.recevoir_puce(card_number, passage, nom)
        target_name = target._parcours["nom"] if target._parcours else "Lecture libre"
        try:
            source_app.remove_card(card_number, moved_to=target_name)
        except Exception:
            if card_number in source_app._frames:
                try:
                    source_app._frames[card_number].destroy()
                except Exception:
                    pass
                for d in ("_frames", "_frame_inners", "_frame_canvases", "_sidebar_btns", "_sidebar_inner"):
                    getattr(source_app, d, {}).pop(card_number, None)
                source_app._card_data.pop(card_number, None)
                source_app._noms.pop(card_number, None)
        self._hub_refresh_list()

    def _exporter_tous(self):
        """Exporte dans un seul fichier CSV toutes les puces lues sur tous les
        parcours ouverts du hub, avec un en-tête harmonisé sur le nombre
        maximal de balises pointées parmi tous les parcours."""
        self._lecture_apps = [a for a in self._lecture_apps if a.winfo_exists()]
        apps_avec_data = [a for a in self._lecture_apps if a._card_data]
        if not apps_avec_data:
            messagebox.showinfo("Export multi-parcours", "Aucune puce lue pour le moment.", parent=self.root)
            return
        chemin = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("Fichier CSV", "*.csv")],
            initialfile=f"tous_parcours_{datetime.now().strftime('%d-%m-%Y')}.csv",
            title="Exporter tous les parcours",
        )
        if not chemin:
            return

        from io_.export_csv import count_max_punches, build_csv_rows, write_csv

        max_punches = max((count_max_punches(app._card_data) for app in apps_avec_data), default=0)
        rows = []
        for app in apps_avec_data:
            rows.extend(build_csv_rows(app._card_data, app._noms, app._parcours, max_punches))
        write_csv(chemin, max_punches, rows)

        messagebox.showinfo("Export réussi", f"Tous les parcours ont été exportés vers :\n{chemin}", parent=self.root)

    def _trouver_nom_puce(self, card_number):
        """Retourne le nom connu d'une puce en cherchant dans toutes les apps ouvertes."""
        for app in self._lecture_apps:
            try:
                nom = app._noms.get(card_number)
                if nom:
                    return nom
            except Exception:
                pass
        return None

    def _hub_trouver_app_existante(self, card_number):
        """Retourne l'app qui contient déjà cette puce (1er passage), ou None."""
        for app in self._lecture_apps:
            try:
                if card_number in app._frames:
                    return app
            except Exception:
                continue
        return None

    def _on_puce_routed(self, source_app, card_number, card_data):
        """Callback appelé quand une puce vient d'être lue physiquement : détermine
        le parcours de destination par score d'intersection entre les balises
        pointées et les balises de chaque parcours ouvert, puis soit ouvre la
        fenêtre de validation (mode contrôlée), soit enregistre directement la
        puce dans le meilleur parcours trouvé (mode libre)."""
        self._lecture_apps = [a for a in self._lecture_apps if a.winfo_exists()]

        from core.constants import BALISE_MIN, BALISE_MAX
        punches = {
            p[0] for p in card_data.get("punches", [])
            if isinstance(p[0], int) and BALISE_MIN <= p[0] <= BALISE_MAX
        }

        scores = {}
        for app in self._lecture_apps:
            if app._parcours and app._parcours.get("balises"):
                scores[app] = len(punches & set(app._parcours["balises"]))

        max_score = max(scores.values()) if scores else 0
        suggested = max(scores, key=scores.get) if max_score > 0 else None

        if self._hub_mode == "controlee":
            # Mode contrôlée : toujours ouvrir la validation à chaque lecture,
            # même pour une puce déjà enregistrée, pour permettre de changer de parcours.
            self._hub_ouvrir_validation(source_app, card_number, card_data, suggested)
            return

        # Mode libre : re-évaluer le meilleur parcours à chaque lecture,
        # sans mémoriser l'affectation précédente.
        if suggested is None:
            if not self._hub_apps:
                messagebox.showwarning(
                    "Aucun parcours reconnu",
                    "Aucun parcours ne peut être relié aux balises trouvées sur cette puce.\n\n"
                    f"{len(punches)} balise(s) pointée(s), aucune ne correspond à un parcours connu.",
                    parent=self.root,
                )
                source_app._card_event.set()
                return
            primary = self._hub_apps[0]
        else:
            primary = suggested

        nom_existant = self._trouver_nom_puce(card_number)
        if nom_existant and card_number not in primary._noms:
            primary._noms[card_number] = nom_existant
        event_to_set = None if primary is source_app else source_app._card_event
        deja_present_avant = card_number in primary._frames
        primary._creer_onglet_puce(card_number, card_data, event_to_set=event_to_set, broadcast=False)
        enregistree = card_number in primary._frames
        if not enregistree and not deja_present_avant:
            return

        try:
            if self._lecture_hub_tab is not None:
                self.notebook.select(self._lecture_hub_tab)
            self._hub_show_app(primary)
            self._hub_refresh_list()
        except Exception:
            pass

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

    def _on_card_broadcast(self, source_app, card_number, card_data, nom):
        """Diffuse une puce enregistrée sur un parcours vers les autres parcours
        ouverts (utile quand la même puce doit apparaître sur plusieurs
        parcours, ou a été explicitement déplacée via _on_request_move)."""
        self._lecture_apps = [a for a in self._lecture_apps if a.winfo_exists()]
        assigned = self._card_assignments.get(card_number)
        if assigned:
            if not getattr(assigned, 'winfo_exists', lambda: False)() or not assigned.winfo_exists():
                self._card_assignments.pop(card_number, None)
            else:
                if assigned is not source_app:
                    assigned.recevoir_puce(card_number, card_data, nom)
                self._hub_refresh_list()
                return

        for app in self._lecture_apps:
            if app is not source_app:
                app.recevoir_puce(card_number, card_data, nom)
        self._hub_refresh_list()
