#!/usr/bin/env python3
"""Fenêtre principale — SportIdent.

Fenêtre principale avec onglets :
  • Onglet "Accueil" (permanent) : 3 boutons de démarrage
  • Onglet "Nouveau parcours"    : création de parcours (ui/parcours.py)
  • Onglet "Lecture — …"         : lecture de puces   (ui/lecture_puce.py)

MainApp délègue tout ce qui touche au hub de lecture multi-parcours
(~1100 lignes) à HubMixin (ui/hub.py) : navigation, panneau global,
routage/validation des puces, export CSV agrégé. Ce fichier ne garde
que l'onglet Accueil et la gestion générique des onglets.
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import os

from ui.hub import HubMixin


class MainApp(HubMixin):
    def __init__(self):
        """Construit la fenêtre principale : notebook + onglet Accueil, et
        initialise tout l'état du hub multi-parcours (utilisé par HubMixin)."""
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
        self._hub_btn_charger_images = None
        self._hub_lbl_images = None
        self._images_balises = {}         # beacon_number (int) -> chemin fichier image
        self._hub_candidats = {}          # candidats chargés (persistant entre modifications)
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
        """Construit l'onglet Accueil : titre + les 3 boutons de démarrage
        (créer un parcours, charger un parcours, lecture libre)."""
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
        """Molette de souris globale : fait défiler le premier widget scrollable
        (Canvas/Listbox/Treeview) trouvé sous le curseur, même s'il n'a pas le focus."""
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
        """Retire un onglet du notebook et détruit son widget."""
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
        """Ouvre un nouvel onglet avec l'éditeur de parcours (AppParcours)."""
        from ui.parcours import AppParcours
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
        """Callback appelé quand l'éditeur de parcours valide (un parcours ou un lot) :
        ferme l'onglet d'édition et ouvre la lecture dans le hub."""
        self._fermer_tab(tab_parcours)
        if isinstance(data, list):
            for parcours in data:
                self._ouvrir_lecture(parcours, shared=True)
        else:
            # Toujours partagé : le panneau global de lecture gère une seule
            # connexion physique pour tous les parcours, même s'il n'y en a qu'un.
            self._ouvrir_lecture(data, shared=True)

    def _charger_parcours(self):
        """Ouvre un fichier parcours existant (.tsv/.csv/.xml/.txt), détecte le
        format d'après l'extension (avec repli en essayant les autres parseurs
        si l'extension est inconnue ou le format ne correspond pas), puis
        ouvre chaque parcours trouvé dans le hub de lecture."""
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
            from io_.parcours_parsers import (
                parser_lot_tsv, parser_lot_csv, parser_csv_intelligent,
                parser_ocad_xml, parser_ocad_txt,
            )
            ext = os.path.splitext(chemin)[1].lower()
            lots = []
            if ext == ".tsv":
                lots = parser_lot_tsv(chemin)
            elif ext == ".csv":
                try:
                    lots = parser_lot_csv(chemin)
                except Exception:
                    lots = []
                if not lots:
                    nom, bal = parser_csv_intelligent(chemin)
                    if bal:
                        lots = [{"nom": nom, "balises": bal, "ordre": False}]
            elif ext == ".xml":
                lots = parser_ocad_xml(chemin)
            elif ext == ".txt":
                lots = parser_ocad_txt(chemin)
            else:
                try:
                    lots = parser_lot_tsv(chemin)
                except Exception:
                    lots = []
                if not lots:
                    try:
                        lots = parser_lot_csv(chemin)
                    except Exception:
                        lots = []
                if not lots:
                    try:
                        lots = parser_ocad_xml(chemin)
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
        """Ouvre le hub sans parcours défini : toute balise pointée est acceptée."""
        self._ouvrir_lecture(None, shared=True)

