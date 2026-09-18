#!/usr/bin/env python3
"""HubViewMixin : construction des widgets du hub (mixin de HubMixin).

Regroupe la construction de l'onglet "Lecture en cours" : structure
nav/contenu (_build_lecture_hub) et le panneau global "Attendre une puce"
(_build_hub_panel_lecture). Pure construction de widgets Tkinter ; la
logique de routage/validation reste dans HubMixin (ui/hub.py) et
HubValidationMixin (ui/hub_validation.py).

Extrait de main.py sans changement de comportement.
"""

import tkinter as tk
from tkinter import ttk


class HubViewMixin:
    """Mixin de HubMixin : construction des widgets du hub (nav, panneau
    global "Attendre une puce"). Pure construction Tkinter, aucune logique
    de routage."""

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
