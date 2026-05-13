#!/usr/bin/env python3
"""
Interface graphique pour la lecture des puces SI.
Affiche les informations complètes d'une puce après lecture sur la station mini-reader.
Chaque puce lue crée un onglet consultable à tout moment.
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from sireader2 import SIReaderReadout, SIReaderException
from datetime import datetime
from time import sleep
import threading
import csv


# ─────────────────────────────────────────
#  Constantes
# ─────────────────────────────────────────
BALISE_MIN = 31
BALISE_MAX = 65


class AppLecturePuce(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Lecture Puce SportIdent")
        self.geometry("720x600")
        self.resizable(False, False)

        self.si = None
        self._frames = {}       # card_number -> Frame de contenu
        self._current = None    # frame actuellement affichée
        self._lire_en_cours = False
        self._closing = False       # True dès que _on_close est déclenché
        self._card_event = threading.Event()  # synchronise thread lecture ↔ thread principal
        self._noms = {}         # card_number -> nom du participant
        self._card_data = {}    # card_number -> card_data brut (pour export)
        self._lbl_participant = {}  # card_number -> Label "Participant" dans le panneau

        self._build_ui()
        self._connect_station()
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    # ─────────────────────────────────────
    #  Construction de l'interface
    # ─────────────────────────────────────
    def _build_ui(self):
        # ── Barre de statut connexion ──
        frame_status = tk.Frame(self, bg="#2c2c2c")
        frame_status.pack(fill="x")
        self.lbl_status = tk.Label(
            frame_status, text="Connexion en cours...",
            bg="#2c2c2c", fg="white", font=("Segoe UI", 9), anchor="w"
        )
        self.lbl_status.pack(side="left", padx=10, pady=4)
        self.btn_reconnecter = tk.Button(
            frame_status, text="Reconnecter",
            bg="#e67e22", fg="white", relief="flat",
            font=("Segoe UI", 8, "bold"), cursor="hand2",
            activebackground="#d35400", activeforeground="white",
            command=self._connect_station
        )
        # Caché par défaut, affiché en cas de déconnexion

        # ── Corps principal : sidebar gauche + zone de contenu droite ──
        frame_body = tk.Frame(self)
        frame_body.pack(fill="both", expand=True)

        # ── Sidebar (scrollable) ──
        sidebar_outer = tk.Frame(frame_body, bg="#1e1e2e", width=160)
        sidebar_outer.pack(side="left", fill="y")
        sidebar_outer.pack_propagate(False)

        self._sidebar_canvas = tk.Canvas(sidebar_outer, bg="#1e1e2e", highlightthickness=0)
        sidebar_scroll = tk.Scrollbar(sidebar_outer, orient="vertical", command=self._sidebar_canvas.yview)
        self._sidebar_canvas.configure(yscrollcommand=sidebar_scroll.set)
        sidebar_scroll.pack(side="right", fill="y")
        self._sidebar_canvas.pack(side="left", fill="both", expand=True)

        self.sidebar = tk.Frame(self._sidebar_canvas, bg="#1e1e2e")
        self._sidebar_window = self._sidebar_canvas.create_window((0, 0), window=self.sidebar, anchor="nw")
        self.sidebar.bind("<Configure>", lambda e: self._sidebar_canvas.configure(
            scrollregion=self._sidebar_canvas.bbox("all")))
        self._sidebar_canvas.bind("<Configure>", lambda e: self._sidebar_canvas.itemconfig(
            self._sidebar_window, width=e.width))
        self._sidebar_canvas.bind("<Enter>", self._sidebar_bind_scroll)
        self._sidebar_canvas.bind("<Leave>", self._sidebar_unbind_scroll)

        self.lbl_sidebar = tk.Label(
            self.sidebar, text="Puces lues : 0",
            bg="#1e1e2e", fg="#aaa", font=("Segoe UI", 9, "bold")
        )
        self.lbl_sidebar.pack(pady=(10, 4))

        # Bouton "Lecture" dans la sidebar
        self._container_lecture = tk.Frame(self.sidebar, bg="#1e1e2e", padx=2, pady=2)
        self._container_lecture.pack(fill="x", padx=6, pady=2)
        self.btn_sidebar_lecture = tk.Button(
            self._container_lecture, text="Lecture",
            bg="#1a73e8", fg="white", relief="flat",
            font=("Segoe UI", 9, "bold"), cursor="hand2",
            activebackground="#1558b0", activeforeground="white",
            command=self._afficher_tab_lecture
        )
        self.btn_sidebar_lecture.pack(fill="x", ipady=6)

        self._sidebar_btns = {}   # card_number -> Frame conteneur (bordure)
        self._sidebar_inner = {}   # card_number -> Button intérieur
        self._active_btn = None    # Frame conteneur actuellement actif

        # ── Zone de contenu ──
        self.frame_content = tk.Frame(frame_body, bg="white")
        self.frame_content.pack(side="left", fill="both", expand=True)

        # ── Frame "Lecture" ──
        self.tab_lecture = tk.Frame(self.frame_content, bg="white")
        self._build_tab_lecture()
        self._afficher_frame(self.tab_lecture)

    def _build_tab_lecture(self):
        """Construit le panneau principal de lecture."""
        lbl_info = tk.Label(
            self.tab_lecture,
            text="Cliquez sur le bouton puis posez la puce sur la station.",
            font=("Segoe UI", 9), fg="#555", bg="white"
        )
        lbl_info.pack(padx=10, pady=10)

        self.btn_lire = tk.Button(
            self.tab_lecture, text="Attendre une puce",
            font=("Segoe UI", 11, "bold"),
            bg="#1a73e8", fg="white",
            activebackground="#1558b0", activeforeground="white",
            relief="flat", cursor="hand2",
            command=self._demarrer_lecture
        )
        self.btn_lire.pack(fill="x", padx=10, pady=10, ipady=10)

        self.btn_annuler = tk.Button(
            self.tab_lecture, text="Annuler la lecture",
            font=("Segoe UI", 10),
            bg="#e74c3c", fg="white",
            activebackground="#c0392b", activeforeground="white",
            relief="flat", cursor="hand2",
            command=self._annuler_lecture
        )
        # Caché par défaut, affiché uniquement pendant la lecture

        ttk.Separator(self.tab_lecture, orient="horizontal").pack(fill="x", padx=10, pady=16)

        self.btn_exporter = tk.Button(
            self.tab_lecture, text="Exporter en CSV",
            font=("Segoe UI", 10),
            bg="#27ae60", fg="white",
            activebackground="#1e8449", activeforeground="white",
            relief="flat", cursor="hand2",
            command=self._exporter_csv
        )
        # Caché par défaut, affiché dès qu'une puce est lue

        self.btn_reset = tk.Button(
            self.tab_lecture, text="Effacer toutes les puces",
            font=("Segoe UI", 10),
            bg="#7f8c8d", fg="white",
            activebackground="#636e72", activeforeground="white",
            relief="flat", cursor="hand2",
            command=self._effacer_toutes_puces
        )
        self.btn_reset.pack(fill="x", padx=10, ipady=6)

    def _afficher_tab_lecture(self):
        self._afficher_frame(self.tab_lecture)
        self._set_active_btn(self._container_lecture)

    def _afficher_frame(self, frame):
        """Affiche un frame dans la zone de contenu, cache le précédent."""
        if self._current is not None:
            self._current.pack_forget()
        frame.pack(fill="both", expand=True)
        self._current = frame

    def _set_active_btn(self, container):
        """Met en évidence le conteneur actif dans la sidebar via sa couleur de fond."""
        if self._active_btn is not None:
            self._active_btn.config(bg="#1e1e2e")  # retire le contour
        self._active_btn = container
        if container is not None:
            container.config(bg="white")  # contour blanc visible

    def _build_tab_puce(self, parent, card_number, card_data, nom=""):
        """Construit le contenu d'un panneau pour une puce donnée."""
        pad = {"padx": 10, "pady": 4}

        now = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        punches_terrain = [
            p for p in card_data.get("punches", [])
            if BALISE_MIN <= p[0] <= BALISE_MAX
        ]

        # ── Infos puce ──
        frame_info = tk.LabelFrame(parent, text="Informations puce", font=("Segoe UI", 10, "bold"))
        frame_info.pack(fill="x", **pad)

        infos = [
            ("Participant :",              nom if nom else "—"),
            ("Numéro puce :",             str(card_number)),
            ("Date de lecture :",         now),
            ("Balises pointées :", f"{len(punches_terrain)} / {BALISE_MAX - BALISE_MIN + 1}"),
        ]
        lbl_participant = None
        for row, (label, valeur) in enumerate(infos):
            tk.Label(frame_info, text=label, font=("Segoe UI", 9, "bold"), anchor="w").grid(
                row=row, column=0, sticky="w", padx=8, pady=2)
            lbl = tk.Label(frame_info, text=valeur, font=("Segoe UI", 9), anchor="w", fg="#222")
            lbl.grid(row=row, column=1, sticky="w", padx=8, pady=2)
            if row == 0:
                lbl_participant = lbl
        self._lbl_participant[card_number] = lbl_participant

        # ── Temps clés ──
        frame_temps = tk.LabelFrame(parent, text="Temps", font=("Segoe UI", 10, "bold"))
        frame_temps.pack(fill="x", **pad)

        temps = [
            ("Check :",   card_data.get("check")),
            ("Clear :",   card_data.get("clear")),
            ("Départ :",  card_data.get("start")),
            ("Arrivée :", card_data.get("finish")),
        ]
        for row, (label, valeur) in enumerate(temps):
            tk.Label(frame_temps, text=label, font=("Segoe UI", 9, "bold"), anchor="w").grid(
                row=row, column=0, sticky="w", padx=8, pady=2)
            tk.Label(frame_temps, text=self._fmt_time(valeur), font=("Segoe UI", 9), anchor="w", fg="#222").grid(
                row=row, column=1, sticky="w", padx=8, pady=2)

        # ── Pointages ──
        frame_punches = tk.LabelFrame(parent, text="Pointages balises", font=("Segoe UI", 10, "bold"))
        frame_punches.pack(fill="both", expand=True, **pad)

        cols = ("Balise", "Heure")
        tree = ttk.Treeview(frame_punches, columns=cols, show="headings", height=8)
        for col in cols:
            tree.heading(col, text=col)
            tree.column(col, width=180, anchor="center")

        scrollbar = ttk.Scrollbar(frame_punches, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)
        tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        for p in punches_terrain:
            heure = p[1].strftime("%H:%M:%S") if p[1] else "—"
            tree.insert("", "end", values=(p[0], heure))

    # ─────────────────────────────────────
    #  Connexion à la station
    # ─────────────────────────────────────
    def _connect_station(self):
        self.btn_lire.config(state="disabled")
        # Nettoyer l'ancienne connexion si elle existe
        if self.si is not None:
            try:
                self.si.disconnect()
            except Exception:
                pass
            self.si = None
        self._set_status("Connexion en cours...", ok=True)
        self.btn_reconnecter.pack_forget()

        def _try_connect():
            try:
                si_nouveau = SIReaderReadout()
                # Garde-fou : si la fermeture a eu lieu pendant la connexion
                if self._closing:
                    try:
                        si_nouveau.disconnect()
                    except Exception:
                        pass
                    return
                # Configurer la station si nécessaire (extended protocol + mode READOUT)
                try:
                    if not si_nouveau.proto_config.get('ext_proto'):
                        si_nouveau.set_extended_protocol(True)
                    if si_nouveau.proto_config.get('mode') != si_nouveau.M_READOUT:
                        si_nouveau.set_operating_mode(si_nouveau.M_READOUT)
                except SIReaderException as e:
                    try:
                        si_nouveau.disconnect()
                    except Exception:
                        pass
                    self._safe_after(0, lambda: self._set_status(
                        f"Station mal configurée : {e}", ok=False))
                    self._safe_after(0, lambda: self.btn_lire.config(state="disabled"))
                    self._safe_after(0, lambda: self.btn_reconnecter.pack(side="right", padx=6, pady=2))
                    return
                self.si = si_nouveau
                port = si_nouveau.port  # capture locale : self.si peut changer après
                self._safe_after(0, lambda: self._set_status(f"Connecté sur {port}", ok=True))
                self._safe_after(0, lambda: self.btn_lire.config(state="normal"))
            except Exception as e:
                self._safe_after(0, lambda: self._set_status(f"Erreur connexion : {e}", ok=False))
                self._safe_after(0, lambda: self.btn_lire.config(state="disabled"))
                self._safe_after(0, lambda: self.btn_reconnecter.pack(side="right", padx=6, pady=2))
        threading.Thread(target=_try_connect, daemon=True).start()

    def _set_status(self, msg, ok=True):
        color = "#27ae60" if ok else "#e74c3c"
        self.lbl_status.config(text=msg, fg=color)

    # ─────────────────────────────────────
    #  Lecture puce
    # ─────────────────────────────────────
    def _demarrer_lecture(self):
        if self.si is None:
            messagebox.showerror("Erreur", "Aucune station connectée.")
            return
        self._lire_en_cours = True
        self._card_event.clear()
        self.btn_lire.config(state="disabled", text="Lecture en cours...")
        self.btn_annuler.pack(fill="x", padx=10, pady=(0, 10), ipady=6)
        self._set_status("Posez la puce sur la station...", ok=True)
        threading.Thread(target=self._lire_puce, daemon=True).start()

    def _lire_puce(self):
        try:
            self.si.flush()
            self.si.sicard = None

            while self._lire_en_cours:
                # Attendre qu'une puce soit posée
                while self._lire_en_cours and not self.si.poll_sicard():
                    sleep(0.5)

                if not self._lire_en_cours:
                    break

                card_number = self.si.sicard
                card_data   = self.si.read_sicard()
                self.si.ack_sicard()

                # Demander au thread principal de traiter la puce, puis attendre
                self._card_event.clear()
                self._safe_after(0, lambda cn=card_number, cd=card_data: self._creer_onglet_puce(cn, cd))
                self._card_event.wait(timeout=30)  # timeout de sécurité en cas d'exception UI

                if self._lire_en_cours:
                    # Préparer la prochaine lecture
                    self.si.sicard = None
                    self.si.flush()
                    self._safe_after(0, lambda: self._set_status("Posez la prochaine puce sur la station...", ok=True))

        except SIReaderException as e:
            self.si = None
            self._safe_after(0, lambda: self._set_status(f"Erreur lecture : {e}", ok=False))
            self._safe_after(0, lambda: self.btn_reconnecter.pack(side="right", padx=6, pady=2))
            self._safe_after(0, lambda: self._reset_bouton(erreur=True))
            return
        except Exception as e:
            # SerialException (débranchement USB) ou autre erreur inattendue
            self.si = None
            self._safe_after(0, lambda: self._set_status(f"Connexion perdue : {e}", ok=False))
            self._safe_after(0, lambda: self.btn_reconnecter.pack(side="right", padx=6, pady=2))
            self._safe_after(0, lambda: self._reset_bouton(erreur=True))
            return

        # Boucle terminée proprement (annulation)
        self._safe_after(0, self._reset_bouton)

    def _creer_onglet_puce(self, card_number, card_data):
        """Demande un nom puis crée un panneau et un bouton sidebar pour la puce lue."""
        # ── Gestion des doublons ──
        if card_number in self._frames:
            remplacer = messagebox.askyesno(
                "Puce déjà lue",
                f"La puce n°{card_number} a déjà été lue.\n\nVoulez-vous remplacer l'entrée existante ?",
                icon="warning"
            )
            if remplacer:
                old_frame = self._frames[card_number]
                if self._current is old_frame:
                    self._current = None
                old_frame.destroy()
                self._sidebar_btns[card_number].destroy()   # détruit le conteneur Frame
                if self._active_btn is self._sidebar_btns[card_number]:
                    self._active_btn = None
                del self._frames[card_number]
                del self._sidebar_btns[card_number]
                del self._sidebar_inner[card_number]
            else:
                self._afficher_frame(self._frames[card_number])
                self._set_active_btn(self._sidebar_btns[card_number])
                self._set_status(f"Puce {card_number} déjà enregistrée — entrée existante affichée.", ok=True)
                self._card_event.set()  # continuer la boucle
                return

        nom = self._demander_nom(card_number)
        if nom is None:  # app fermée ou lecture annulée via le dialogue
            self._lire_en_cours = False
            self._card_event.set()
            self._safe_after(0, lambda: self._reset_bouton())
            return

        frame = tk.Frame(self.frame_content, bg="white")
        self._build_tab_puce(frame, card_number, card_data, nom)
        self._frames[card_number] = frame
        self._noms[card_number] = nom
        self._card_data[card_number] = card_data

        # Conteneur Frame (sert de bordure) + bouton intérieur
        label_sidebar = nom if nom else str(card_number)
        container = tk.Frame(self.sidebar, bg="#1e1e2e", padx=2, pady=2)
        container.pack(fill="x", padx=6, pady=2)
        btn = tk.Button(
            container, text=label_sidebar,
            bg="#2d2d44", fg="white", relief="flat",
            font=("Segoe UI", 9), cursor="hand2",
            activebackground="#3d3d5c", activeforeground="white",
            command=lambda n=card_number: [
                self._afficher_frame(self._frames[n]),
                self._set_active_btn(self._sidebar_btns[n])
            ]
        )
        btn.pack(fill="x", ipady=4)
        self._sidebar_btns[card_number] = container
        self._sidebar_inner[card_number] = btn

        # Menu clic droit → Renommer
        menu = tk.Menu(self, tearoff=0)
        menu.add_command(label="Renommer", command=lambda n=card_number: self._renommer_puce(n))

        def _popup(e, m=menu):
            try:
                m.tk_popup(e.x_root, e.y_root)
            finally:
                m.grab_release()
        btn.bind("<Button-3>", _popup)

        # Afficher le bouton export dès la première puce
        if len(self._frames) == 1:
            self.btn_exporter.pack(fill="x", padx=10, pady=(0, 6), ipady=6)

        self.lbl_sidebar.config(text=f"Puces lues : {len(self._frames)}")

        self._afficher_frame(frame)
        self._set_active_btn(container)
        self._set_status(f"Puce {card_number} lue avec succès.", ok=True)
        self._card_event.set()  # signale au thread que le traitement est terminé

    def _creer_onglet_puce_finally(self):
        """Appelé en finally de _creer_onglet_puce pour garantir le déblocage du thread."""
        if not self._card_event.is_set():
            self._card_event.set()
        """Affiche une boîte de dialogue pour saisir le nom du participant (obligatoire)."""
        while True:
            dialog = tk.Toplevel(self)
            dialog.title("Nom du participant")
            dialog.geometry("320x175")
            dialog.resizable(False, False)
            dialog.grab_set()
            dialog.focus_set()

            tk.Label(dialog, text=f"Puce n°{card_number}", font=("Segoe UI", 9), fg="#555").pack(pady=(12, 2))
            tk.Label(dialog, text="Entrez le nom du participant :", font=("Segoe UI", 10)).pack()

            entry = tk.Entry(dialog, font=("Segoe UI", 11), justify="center")
            entry.pack(padx=20, pady=6, fill="x")
            entry.focus_set()

            self._lbl_erreur_nom = tk.Label(dialog, text="", fg="#e74c3c", font=("Segoe UI", 9))
            self._lbl_erreur_nom.pack()

            nom_result = [""]
            annule = [False]

            def valider(event=None):
                valeur = entry.get().strip()
                if not valeur:
                    self._lbl_erreur_nom.config(text="Le nom ne peut pas être vide.")
                    return
                nom_result[0] = valeur
                dialog.destroy()

            def annuler(event=None):
                annule[0] = True
                dialog.destroy()

            # La croix (X) et le bouton Annuler stoppent la lecture
            dialog.protocol("WM_DELETE_WINDOW", annuler)

            entry.bind("<Return>", valider)
            entry.bind("<Escape>", annuler)

            frame_btns = tk.Frame(dialog)
            frame_btns.pack(pady=4)
            tk.Button(
                frame_btns, text="Valider", command=valider,
                bg="#1a73e8", fg="white", relief="flat",
                font=("Segoe UI", 10, "bold"), cursor="hand2"
            ).pack(side="left", ipadx=16, ipady=4, padx=(0, 6))
            tk.Button(
                frame_btns, text="Annuler", command=annuler,
                bg="#888", fg="white", relief="flat",
                font=("Segoe UI", 10), cursor="hand2"
            ).pack(side="left", ipadx=10, ipady=4)

            self.wait_window(dialog)
            if self._closing or annule[0]:
                return None
            if nom_result[0]:
                return nom_result[0]

    def _annuler_lecture(self):
        """Annule l'attente d'une puce en cours."""
        self._lire_en_cours = False
        self._set_status("Lecture annulée.", ok=True)

    def _renommer_puce(self, card_number):
        """Affiche un dialogue pour renommer une puce existante."""
        dialog = tk.Toplevel(self)
        dialog.title("Renommer")
        dialog.geometry("300x120")
        dialog.resizable(False, False)
        dialog.grab_set()
        dialog.focus_set()
        dialog.protocol("WM_DELETE_WINDOW", dialog.destroy)

        tk.Label(dialog, text="Nouveau nom :", font=("Segoe UI", 10)).pack(pady=(16, 4))
        entry = tk.Entry(dialog, font=("Segoe UI", 11), justify="center")
        entry.insert(0, self._noms.get(card_number, ""))
        entry.select_range(0, "end")
        entry.pack(padx=20, fill="x")
        entry.focus_set()

        def valider(event=None):
            nouveau = entry.get().strip()
            if not nouveau:
                return
            self._noms[card_number] = nouveau
            self._sidebar_inner[card_number].config(text=nouveau)
            if card_number in self._lbl_participant and self._lbl_participant[card_number]:
                self._lbl_participant[card_number].config(text=nouveau)
            dialog.destroy()

        entry.bind("<Return>", valider)
        tk.Button(
            dialog, text="Valider", command=valider,
            bg="#1a73e8", fg="white", relief="flat",
            font=("Segoe UI", 10, "bold"), cursor="hand2"
        ).pack(pady=8, ipadx=16, ipady=4)

    def _exporter_csv(self):
        """Exporte toutes les puces lues dans un fichier CSV."""
        if not self._frames:
            return
        chemin = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("Fichier CSV", "*.csv")],
            initialfile=f"lecture_puces_{datetime.now().strftime('%d-%m-%Y')}.csv",
            title="Enregistrer l'export CSV"
        )
        if not chemin:
            return
        with open(chemin, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.writer(f, delimiter=";")
            writer.writerow(["Participant", "Numéro puce", "Départ", "Arrivée", "Balises pointées", "Balises détail"])
            for card_number, data in self._card_data.items():
                nom = self._noms.get(card_number, "")
                punches = [
                    p for p in data.get("punches", [])
                    if BALISE_MIN <= p[0] <= BALISE_MAX
                ]
                balises_detail = " | ".join(
                    f"{p[0]} ({p[1].strftime('%H:%M:%S') if p[1] else '—'})"
                    for p in punches
                )
                writer.writerow([
                    nom,
                    card_number,
                    self._fmt_time(data.get("start")),
                    self._fmt_time(data.get("finish")),
                    len(punches),
                    balises_detail
                ])
        self._set_status(f"Export CSV enregistré : {chemin}", ok=True)

    def _effacer_toutes_puces(self):
        """Supprime toutes les puces lues de la sidebar et remet l'interface à zéro."""
        if not self._frames:
            return
        if not messagebox.askyesno(
            "Effacer toutes les puces",
            f"Voulez-vous effacer les {len(self._frames)} puce(s) enregistrée(s) ?\n\nCette action est irréversible.",
            icon="warning"
        ):
            return

        # Supprimer tous les frames de contenu
        for frame in self._frames.values():
            frame.destroy()
        # Supprimer tous les conteneurs sidebar
        for container in self._sidebar_btns.values():
            container.destroy()

        self._frames.clear()
        self._sidebar_btns.clear()
        self._sidebar_inner.clear()
        self._noms.clear()
        self._card_data.clear()
        self._lbl_participant.clear()
        self._active_btn = None
        self._current = None

        # Cacher le bouton export
        self.btn_exporter.pack_forget()
        self.lbl_sidebar.config(text="Puces lues : 0")

        # Revenir à l'onglet lecture
        self._afficher_tab_lecture()
        self._set_status(f"Connecté sur {self.si.port}" if self.si else "Station non connectée.", ok=self.si is not None)

    def _on_close(self):
        """Ferme proprement l'application en libérant le port série."""
        self._closing = True
        self._lire_en_cours = False
        self._card_event.set()  # débloque le thread s'il attend le dialogue de nom
        if self.si is not None:
            try:
                self.si.disconnect()
            except Exception:
                pass
        self.destroy()

    # ─────────────────────────────────────
    #  Utilitaires
    # ─────────────────────────────────────
    def _fmt_time(self, val):
        if val is None:
            return "—"
        if isinstance(val, datetime):
            return val.strftime("%d/%m/%Y %H:%M:%S")
        return str(val)

    def _sidebar_bind_scroll(self, event):
        self._sidebar_canvas.bind("<MouseWheel>", self._on_sidebar_scroll)
        self._sidebar_canvas.bind("<Button-4>", self._on_sidebar_scroll)
        self._sidebar_canvas.bind("<Button-5>", self._on_sidebar_scroll)

    def _sidebar_unbind_scroll(self, event):
        self._sidebar_canvas.unbind("<MouseWheel>")
        self._sidebar_canvas.unbind("<Button-4>")
        self._sidebar_canvas.unbind("<Button-5>")

    def _on_sidebar_scroll(self, event):
        num = getattr(event, 'num', None)
        if num == 4:
            delta = -1          # Linux : molette haut
        elif num == 5:
            delta = 1           # Linux : molette bas
        else:
            delta = int(-1 * (event.delta / 120))  # Windows / macOS
        if delta < 0 and self._sidebar_canvas.yview()[0] <= 0:
            return
        self._sidebar_canvas.yview_scroll(delta, "units")

    def _safe_after(self, ms, func):
        """Appel after() sécurisé : ignoré si l'app est en cours de destruction."""
        if self._closing:
            return
        try:
            self.after(ms, func)
        except Exception:
            pass

    def _reset_bouton(self, erreur=False):
        self._lire_en_cours = False
        self.btn_annuler.pack_forget()
        etat = "disabled" if erreur else "normal"
        self.btn_lire.config(state=etat, text="Attendre une puce")


if __name__ == "__main__":
    app = AppLecturePuce()
    app.mainloop()
