#!/usr/bin/env python3
"""Point d'entrée — SportIdent.

Fenêtre principale avec onglets :
  • Onglet "Accueil" (permanent) : 3 boutons de démarrage
  • Onglet "Nouveau parcours"    : création de parcours (ui_parcours.py)
  • Onglet "Lecture — …"         : lecture de puces   (ui_lecture_puce.py)
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import os
import csv
from datetime import datetime


class MainApp:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Gestionnaire de course")
        self.root.geometry("740x600")
        self.root.state("zoomed")
        self.root.resizable(True, True)
        self.root.protocol("WM_DELETE_WINDOW", self.root.destroy)

        # Binder un événement personnalisé pour rafraîchir la liste du hub depuis les apps
        self.root.bind("<<HubRefresh>>", lambda e: self._hub_refresh_list())
        self.root.bind("<<AppStatus>>", self._on_app_status)
        self.root.bind("<<AppReadingStopped>>", lambda e: self._hub_reset_btn_lecture())

        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill="both", expand=True)

        self._tab_close_cbs = {}           # tab Frame → callable de fermeture propre
        self._lecture_apps = []            # AppLecturePuce actives (pour diffusion multi-onglets)
        self._card_assignments = {}        # card_number -> AppLecturePuce (force routing après déplacement)

        # Hub de lecture (onglet unique regroupant tous les parcours)
        self._lecture_hub_tab = None       # Frame de l'onglet hub (None si non créé)
        self._hub_apps = []               # AppLecturePuce dans le hub, dans l'ordre
        self._hub_current = None          # AppLecturePuce actuellement visible
        self._hub_listbox = None          # Listbox de navigation gauche
        self._hub_content = None          # Frame contenu droit
        self._hub_count_lbl = None        # Label "N parcours"
        self._hub_btn_lecture = None      # Bouton "Lecture" en haut du nav
        self._go_lecture_after_id = None  # ID du after() programmé pour _hub_go_lecture
        self._hub_panel_lecture = None    # Panneau global "Attendre une puce"
        self._hub_btn_attendre = None
        self._hub_btn_annuler = None
        self._hub_lbl_status = None
        self._hub_lbl_liste = None
        self._hub_btn_mode = None
        self._hub_btn_charger_liste = None
        self._hub_mode = "libre"
        self._hub_app_en_ecoute = None    # App physiquement en train de lire

        # Onglet Accueil (permanent, jamais fermé)
        self._tab_accueil = tk.Frame(self.notebook, bg="white")
        self.notebook.add(self._tab_accueil, text="  Accueil  ")
        self._build_accueil(self._tab_accueil)
        self.notebook.bind("<ButtonPress-1>", self._on_tab_press)
        # Scroll molette universel : fonctionne même si le curseur est sur un widget enfant
        self.root.bind_all("<MouseWheel>", self._on_global_scroll)

    # ─────────────────────────────────────
    #  Onglet Accueil
    # ─────────────────────────────────────
    def _build_accueil(self, parent):
        entete = tk.Frame(parent, bg="#1e1e2e")
        entete.pack(fill="x")
        tk.Label(
            entete, text="Gestionnaire de course",
            font=("Segoe UI", 12, "bold"), bg="#1e1e2e", fg="white"
        ).pack(pady=16, padx=16)

        corps = tk.Frame(parent, bg="white")
        corps.pack(fill="both", expand=True, padx=30, pady=20)

        boutons = [
            (
                "Créer un parcours",
                "Définir les balises et enregistrer en .tsv",
                "#1a73e8",
                self._creer_parcours,
            ),
            (
                "Charger un parcours enregistré",
                "Ouvrir un fichier parcours existant et démarrer la lecture",
                "#e67e22",
                self._charger_parcours,
            ),
            (
                "Lecture libre ",
                "Lire des puces sans parcours défini",
                "#7f8c8d",
                self._lecture_libre,
            ),
        ]

        for texte, desc, couleur, cmd in boutons:
            f = tk.Frame(corps, bg="white")
            f.pack(fill="x", pady=6)
            tk.Button(
                f, text=texte, font=("Segoe UI", 10, "bold"),
                bg=couleur, fg="white", relief="flat", cursor="hand2",
                activebackground=couleur, activeforeground="white",
                command=cmd,
            ).pack(fill="x", ipady=10)
            tk.Label(f, text=desc, font=("Segoe UI", 8), fg="#888", bg="white").pack()

    # ─────────────────────────────────────
    #  Gestion des onglets
    # ─────────────────────────────────────
    def _on_tab_press(self, event):
        """Ferme l'onglet si le clic est dans la zone × (22 derniers px du tab)."""
        try:
            idx = self.notebook.index(f"@{event.x},{event.y}")
        except tk.TclError:
            return
        if idx == 0:  # Accueil non fermable
            return

        CLOSE_ZONE = 22
        W = self.notebook.winfo_width()
        tab_ends_soon = False
        for delta in range(1, CLOSE_ZONE + 1):
            nx = event.x + delta
            if nx >= W:
                tab_ends_soon = True
                break
            try:
                if self.notebook.index(f"@{nx},{event.y}") != idx:
                    tab_ends_soon = True
                    break
            except tk.TclError:
                tab_ends_soon = True
                break

        if not tab_ends_soon:
            return

        tab_widget = self.notebook.nametowidget(self.notebook.tabs()[idx])
        close_cb = self._tab_close_cbs.get(tab_widget)
        if close_cb:
            close_cb()
        else:
            self._fermer_tab(tab_widget)
        return "break"

    def _on_global_scroll(self, event):
        delta = int(-1 * (event.delta / 120))
        widget = event.widget
        while widget is not None:
            if isinstance(widget, (tk.Canvas, tk.Listbox)):
                widget.yview_scroll(delta, "units")
                return
            if isinstance(widget, ttk.Treeview):
                widget.yview_scroll(delta, "units")
                return
            widget = getattr(widget, "master", None)

    def _fermer_tab(self, tab):
        self._tab_close_cbs.pop(tab, None)
        try:
            self.notebook.forget(tab)
            tab.destroy()
        except Exception:
            pass

    # ─────────────────────────────────────
    #  Actions des boutons Accueil
    # ─────────────────────────────────────
    def _creer_parcours(self):
        from ui_parcours import AppParcours
        tab = tk.Frame(self.notebook)
        self.notebook.add(tab, text="  Nouveau parcours  ×")
        self.notebook.select(tab)
        self._tab_close_cbs[tab] = lambda t=tab: self._fermer_tab(t)
        AppParcours(
            tab,
            on_done=lambda data, t=tab: self._on_parcours_done(data, t),
            on_cancel=lambda t=tab: self._fermer_tab(t),
        )

    def _on_parcours_done(self, data, tab_parcours):
        self._fermer_tab(tab_parcours)
        if isinstance(data, list):
            for parcours in data:
                self._ouvrir_lecture(parcours, shared=True)
        else:
            # Toujours partagé : le panneau global de lecture gère une seule
            # connexion physique pour tous les parcours, même s'il n'y en a qu'un.
            self._ouvrir_lecture(data, shared=True)

    def _charger_parcours(self):
        chemin = filedialog.askopenfilename(
            filetypes=[
                ("Fichiers parcours", "*.tsv *.csv *.xml *.txt"),
                ("Fichier TSV", "*.tsv"),
                ("Fichier CSV", "*.csv"),
                ("OCAD XML / TXT", "*.xml *.txt"),
                ("Tous les fichiers", "*.*"),
            ],
            title="Charger un parcours",
        )
        if not chemin:
            return
        try:
            from ui_parcours import AppParcours
            ext = os.path.splitext(chemin)[1].lower()
            lots = []
            if ext == ".tsv":
                lots = AppParcours._parser_lot_tsv(chemin)
            elif ext == ".csv":
                try:
                    lots = AppParcours._parser_lot_csv(chemin)
                except Exception:
                    lots = []
                if not lots:
                    nom, bal = AppParcours._parser_csv_intelligent(chemin)
                    if bal:
                        lots = [{"nom": nom, "balises": bal, "ordre": False}]
            elif ext == ".xml":
                lots = AppParcours._parser_ocad_xml(chemin)
            elif ext == ".txt":
                lots = AppParcours._parser_ocad_txt(chemin)
            else:
                try:
                    lots = AppParcours._parser_lot_tsv(chemin)
                except Exception:
                    lots = []
                if not lots:
                    try:
                        lots = AppParcours._parser_lot_csv(chemin)
                    except Exception:
                        lots = []
                if not lots:
                    try:
                        lots = AppParcours._parser_ocad_xml(chemin)
                    except Exception:
                        lots = []
            valides = [p for p in lots if p.get("balises")]
            if not valides:
                messagebox.showwarning("Fichier vide", "Aucune balise trouvée dans ce fichier.")
                return
            # Toujours partagé : le panneau global de lecture gère une seule
            # connexion physique, même pour un seul parcours chargé.
            for p in valides:
                self._ouvrir_lecture(p, shared=True)
        except Exception as e:
            messagebox.showerror("Erreur", f"Impossible de charger le fichier :\n{e}")

    def _lecture_libre(self):
        self._ouvrir_lecture(None, shared=True)

    def _ouvrir_lecture(self, parcours, shared=True):
        from ui_lecture_puce import AppLecturePuce
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
        )
        app_ref[0] = app_lecture
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
            nav, text="▶  Lecture",
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
            from ui_lecture_puce import parse_candidate_csv
            candidats = parse_candidate_csv(chemin)
        except Exception as e:
            messagebox.showerror("Erreur", f"Impossible de charger le fichier :\n{e}", parent=self.root)
            return
        nb = len(candidats)
        self._hub_lbl_liste.config(text=f"✓  {nb} candidat(s) chargé(s)", fg="#27ae60")
        for app in self._hub_apps:
            try:
                app._appliquer_candidats(candidats)
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

        self._hub_btn_attendre.config(
            state="disabled", text="Lecture en cours...",
            bg="#1a73e8", activebackground="#1558b0",
        )
        self._hub_btn_annuler.pack(fill="x", padx=10, pady=(0, 10), ipady=6, after=self._hub_btn_attendre)
        self._hub_lbl_status.config(text="Posez la puce sur la station...", fg="#1a73e8")

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
            if en_erreur and app is not None:
                msg, ok = getattr(app, "_last_status_msg", ("Connexion perdue. Cliquez sur 'Relancer'.", False))
                self._hub_lbl_status.config(text=msg, fg="#e74c3c")
            elif not en_erreur:
                self._hub_lbl_status.config(text="")
        except Exception:
            pass

    def _hub_show_app(self, app):
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
        from ui_parcours import AppParcours

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
            if msg and getattr(self, "_hub_lbl_status", None):
                self._hub_lbl_status.config(text=msg, fg="#27ae60" if ok else "#e74c3c")
        except Exception:
            pass

    def _app_existe(self, app):
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

    def _fermer_hub_app_selected(self):
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
        self._lecture_apps = [a for a in self._lecture_apps if a.winfo_exists()]
        for app in self._lecture_apps:
            if app is not source_app:
                app._appliquer_candidats(candidats)

    def _on_reader_claimed(self, requester_app):
        self._lecture_apps = [a for a in self._lecture_apps if a.winfo_exists()]
        for app in self._lecture_apps:
            if app is not requester_app:
                app._release_reader()

    def _on_request_move(self, source_app, card_number):
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

        max_punches = max((app._count_max_punches() for app in apps_avec_data), default=0)

        with open(chemin, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.writer(f, delimiter=";")
            header = ["Numéro puce", "Participant", "Parcours", "Nb postes", "Passage",
                      "Départ", "Arrivée", "Temps course"]
            for i in range(1, max_punches + 1):
                header += [f"Balise {i}", f"Temps {i}"]
            writer.writerow(header)
            for app in self._lecture_apps:
                if not app._card_data:
                    continue
                for row in app._build_csv_rows(max_punches):
                    writer.writerow(row)

        messagebox.showinfo("Export réussi", f"Tous les parcours ont été exportés vers :\n{chemin}", parent=self.root)

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
        self._lecture_apps = [a for a in self._lecture_apps if a.winfo_exists()]

        # Relecture d'une puce déjà enregistrée (même en mode contrôlée) :
        # on ajoute simplement le passage suivant là où elle se trouve déjà,
        # sans repasser par la fenêtre de validation.
        app_existante = self._hub_trouver_app_existante(card_number)
        if app_existante is not None:
            event_to_set = None if app_existante is source_app else source_app._card_event
            app_existante._creer_onglet_puce(card_number, card_data, event_to_set=event_to_set, broadcast=False)
            try:
                if self._lecture_hub_tab is not None:
                    self.notebook.select(self._lecture_hub_tab)
                self._hub_show_app(app_existante)
                self._hub_refresh_list()
            except Exception:
                pass
            try:
                if getattr(self, "_hub_lbl_status", None):
                    self._hub_lbl_status.config(text="Passage supplémentaire enregistré.", fg="#27ae60")
            except Exception:
                pass
            try:
                if source_app is not app_existante:
                    source_app._card_event.set()
            except Exception:
                pass
            return

        assigned = self._card_assignments.get(card_number)
        if assigned:
            if not getattr(assigned, 'winfo_exists', lambda: False)() or not assigned.winfo_exists():
                self._card_assignments.pop(card_number, None)
            else:
                if self._hub_mode == "controlee":
                    self._hub_ouvrir_validation(source_app, card_number, card_data, assigned)
                    return
                event_to_set = None if assigned is source_app else source_app._card_event
                deja_present_avant = card_number in assigned._frames
                assigned._creer_onglet_puce(card_number, card_data, event_to_set=event_to_set, broadcast=False)
                enregistree = card_number in assigned._frames
                if not enregistree and not deja_present_avant:
                    try:
                        if source_app is not assigned:
                            source_app._card_event.set()
                    except Exception:
                        pass
                    return
                try:
                    if self._lecture_hub_tab is not None:
                        self.notebook.select(self._lecture_hub_tab)
                    self._hub_show_app(assigned)
                    self._hub_refresh_list()
                except Exception:
                    pass
                try:
                    if getattr(self, "_hub_lbl_status", None):
                        self._hub_lbl_status.config(text="Puce enregistrée. Posez la prochaine puce...", fg="#27ae60")
                except Exception:
                    pass
                try:
                    if source_app is not assigned:
                        source_app._card_event.set()
                except Exception:
                    pass
                return

        from ui_lecture_puce import BALISE_MIN, BALISE_MAX
        punches = {
            p[0] for p in card_data.get("punches", [])
            if isinstance(p[0], int) and BALISE_MIN <= p[0] <= BALISE_MAX
        }

        scores = {}
        for app in self._lecture_apps:
            if app._parcours and app._parcours.get("balises"):
                scores[app] = len(punches & set(app._parcours["balises"]))

        max_score = max(scores.values()) if scores else 0

        if max_score == 0:
            if self._hub_mode == "controlee":
                # En mode contrôlée, on laisse l'utilisateur choisir le parcours
                # même si aucun ne correspond automatiquement.
                self._hub_ouvrir_validation(source_app, card_number, card_data, None)
                return
            # Mode libre : aucune balise ne correspond à aucun parcours →
            # on assigne automatiquement au premier parcours ouvert plutôt que rejeter.
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
            winners = [app for app, s in scores.items() if s == max_score]
            primary = winners[0]

            if self._hub_mode == "controlee":
                self._hub_ouvrir_validation(source_app, card_number, card_data, primary)
                return

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
        try:
            if getattr(self, "_hub_lbl_status", None):
                self._hub_lbl_status.config(text="Puce enregistrée. Posez la prochaine puce...", fg="#27ae60")
        except Exception:
            pass

    def _hub_ouvrir_validation(self, source_app, card_number, card_data, app_suggeree):
        """Mode contrôlée : ouvre une fenêtre de validation avant d'enregistrer la puce.

        L'utilisateur voit le numéro de puce, le nom (si candidat connu), un menu
        déroulant pour choisir/changer le parcours de destination (pré-sélectionné
        par score), et la liste des balises pointées. Valider enregistre la puce
        dans le parcours choisi ; Annuler ne fait rien (comme si non lue)."""
        from ui_lecture_puce import BALISE_MIN, BALISE_MAX

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
            balises_attendues = app_cible._parcours.get("balises", [])
            balises_set = set(balises_attendues)
            if app_cible._parcours.get("ordre"):
                seen_ord = set()
                sequence_pointee = []
                for code, _ in punches:
                    if code in balises_set and code not in seen_ord:
                        seen_ord.add(code)
                        sequence_pointee.append(code)
                nb_valides = 0
                for i, bal in enumerate(sequence_pointee):
                    if i < len(balises_attendues) and bal == balises_attendues[i]:
                        nb_valides += 1
                    else:
                        break
                ordre_valide = set(sequence_pointee[:nb_valides])
                ordre_invalide = set(sequence_pointee[nb_valides:])
                tags = {}
                for code, _ in punches:
                    if code in ordre_valide:
                        tags[code] = "ok"
                    elif code in ordre_invalide:
                        tags[code] = "ordre"
                    else:
                        tags[code] = "hors"
                return tags
            else:
                return {code: ("ok" if code in balises_set else "hors") for code, _ in punches}

        def _remplir_tree():
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
            sel_nom = var_parcours.get()
            try:
                idx = noms_parcours.index(sel_nom)
                resultat["app"] = parcours_apps[idx]
            except ValueError:
                resultat["app"] = app_suggeree
            resultat["valide"] = True
            dlg.destroy()

        def on_annuler():
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
            event_to_set = None if cible is source_app else source_app._card_event
            deja_present_avant = card_number in cible._frames
            cible._creer_onglet_puce(card_number, card_data, event_to_set=event_to_set, broadcast=False)
            # Si la puce n'a pas été ajoutée (nom annulé dans le dialogue qui suit),
            # ne pas naviguer vers le parcours cible — traiter comme une annulation.
            enregistree = card_number in cible._frames
            if not enregistree and not deja_present_avant:
                try:
                    if getattr(self, "_hub_lbl_status", None):
                        self._hub_lbl_status.config(text="Puce annulée. Posez la prochaine puce...", fg="#e67e22")
                except Exception:
                    pass
                return
            try:
                if self._lecture_hub_tab is not None:
                    self.notebook.select(self._lecture_hub_tab)
                self._hub_show_app(cible)
                self._hub_refresh_list()
            except Exception:
                pass
            try:
                if getattr(self, "_hub_lbl_status", None):
                    self._hub_lbl_status.config(text="Puce enregistrée. Posez la prochaine puce...", fg="#27ae60")
            except Exception:
                pass
        else:
            # Annulé : la puce n'est pas enregistrée, on débloque simplement le thread de lecture
            try:
                if getattr(self, "_hub_lbl_status", None):
                    self._hub_lbl_status.config(text="Puce annulée. Posez la prochaine puce...", fg="#e67e22")
            except Exception:
                pass
            source_app._card_event.set()

    def _on_card_broadcast(self, source_app, card_number, card_data, nom):
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


def main():
    app = MainApp()
    app.root.mainloop()


if __name__ == "__main__":
    main()