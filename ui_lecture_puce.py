#!/usr/bin/env python3
"""
Interface graphique pour la lecture des puces SI.
Affiche les informations complètes d'une puce après lecture sur la station mini-reader.
Chaque puce lue crée un onglet consultable à tout moment.
"""


import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from datetime import datetime
from time import sleep
import threading
import csv
import unicodedata

from sireader2 import SIReaderReadout, SIReaderException

# Constants
BALISE_MIN = 31
BALISE_MAX = 256


def parse_candidate_csv(chemin):
    """Parse a candidate CSV file (semicolon-delimited) and return dict[num] = {...}.

    Tries common encodings and normalizes header names to detect columns.
    """

    def _normaliser(s):
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


class AppLecturePuce(tk.Frame):
    def __init__(self, parent, parcours=None, on_close=None, on_broadcast=None, on_request_reader=None, on_route_puce=None, on_request_move=None, on_export_all=None, on_candidats_loaded=None, read_controls=True):
        super().__init__(parent)
        self.pack(fill="both", expand=True)
        self._on_close_cb = on_close
        self._on_broadcast = on_broadcast
        self._on_request_reader = on_request_reader
        self._on_route_puce = on_route_puce
        self._on_request_move = on_request_move
        self._on_export_all = on_export_all
        self._on_candidats_loaded = on_candidats_loaded
        self._parcours = parcours
        self._read_controls = bool(read_controls)
        self.si = None
        self._moves = []
        self._frames = {}            # card_number - Frame outer scrollable
        self._frame_inners = {}      # card_number - Frame inner (où s'empilent les passages)
        self._frame_canvases = {}    # card_number - Canvas (pour le scroll vertical)
        self._current = None         # frame actuellement affichée
        self._lire_en_cours = False
        self._closing = False        # True dès que _on_close est déclenché
        self._card_event = threading.Event()  # synchronise le thread de lecture avec le thread principal
        self._noms = {}              # card_number - nom du participant
        self._card_data = {}         # card_number - list[card_data] (un par passage)
        self._lbl_participant = {}   # card_number - Label "Participant" (passage 1)
        self._card_passages = {}     # card_number - nombre de passages
        self._liste_candidats = {}   # card_number - dict candidat pré-chargé (CSV)
        self._name_dialog = None     # référence au Toplevel de saisie nom si ouvert
        self._mode_lecture = "libre"  # "libre" | "controlee"
        self._erreur_connexion = False  # True quand la lecture s'est arrêtée sur erreur
        self._last_status_msg = ("", True)

        self._build_ui()
        # Comportement de connexion automatique seulement si le widget expose les contrôles
        if self._read_controls:
            if self._on_request_reader is None:
                # Mode simple : connexion automatique
                self._connect_station()
            else:
                # Mode partagé : pas de connexion auto, l'utilisateur choisit quel onglet lit
                self._set_status(
                    "Cliquez sur 'Attendre une puce' pour démarrer la lecture sur cet onglet.",
                    ok=True
                )
                if getattr(self, 'btn_lire', None):
                    try:
                        self.btn_lire.config(state="normal")
                    except Exception:
                        pass
        else:
            # Assurer l'existence des attributs potentiellement utilisés ailleurs
            self.btn_lire = None
            self.btn_exporter = None
            self.btn_exporter_tous = None
            self.btn_reconnecter = None

    #  Construction de l'interface
    def _build_ui(self):
        # Barre de statut uniquement en mode autonome (pas dans le hub)
        if self._read_controls and self._on_request_reader is None:
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

            tk.Button(
                frame_status, text="Fermer",
                bg="#7f8c8d", fg="white", relief="flat",
                font=("Segoe UI", 8), cursor="hand2",
                activebackground="#636e72", activeforeground="white",
                command=self._on_close
            ).pack(side="right", padx=8, pady=3, ipadx=6, ipady=1)
        else:
            self.lbl_status = None
            self.btn_reconnecter = None

        frame_body = tk.Frame(self)
        frame_body.pack(fill="both", expand=True)

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

        self.lbl_sidebar = tk.Label(
            self.sidebar, text="Lectures : 0",
            bg="#1e1e2e", fg="#aaa", font=("Segoe UI", 9, "bold")
        )
        self.lbl_sidebar.pack(pady=(10, 4))

        # Pas de bouton "Lecture" dans la sidebar : on ne garde que les puces lues
        self._container_lecture = None
        self.btn_sidebar_lecture = None

        self._sidebar_btns = {}   # read_id -> Frame conteneur (bordure)
        self._sidebar_inner = {}  # read_id -> Button intérieur
        self._active_btn = None    # Frame conteneur actuellement actif

        self.frame_content = tk.Frame(frame_body, bg="white")
        self.frame_content.pack(side="left", fill="both", expand=True)

        self.tab_lecture = None
        if self._read_controls:
            self.tab_lecture = tk.Frame(self.frame_content, bg="white")
            self._build_tab_lecture()
            # En mode hub, la zone blanche reste vide — le bouton Lecture l'affiche
            if self._on_request_reader is None:
                self._afficher_frame(self.tab_lecture)

    def _build_tab_lecture(self):
        """Construit le panneau principal de lecture."""
        lbl_info = tk.Label(
            self.tab_lecture,
            text="Cliquez sur le bouton puis posez la puce sur la station.",
            font=("Segoe UI", 9), fg="#555", bg="white"
        )
        lbl_info.pack(padx=10, pady=10)

        self.btn_mode_lecture = tk.Button(
            self.tab_lecture,
            text="Mode : Libre",
            font=("Segoe UI", 10, "bold"),
            bg="#34495e", fg="white",
            activebackground="#2c3e50", activeforeground="white",
            relief="flat", cursor="hand2",
            command=self._toggle_mode_lecture
        )
        self.btn_mode_lecture.pack(fill="x", padx=10, pady=(0, 8), ipady=7)

        if self._parcours:
            frame_p = tk.Frame(self.tab_lecture, bg="#e8f4fd", relief="solid", bd=1)
            frame_p.pack(fill="x", padx=10, pady=(0, 6))
            tk.Label(
                frame_p, text=f"\u25cf  Parcours : {self._parcours['nom']}",
                font=("Segoe UI", 9, "bold"), bg="#e8f4fd", fg="#1a73e8"
            ).pack(anchor="w", padx=8, pady=(4, 1))
            tk.Label(
                frame_p, text=f"{len(self._parcours['balises'])} balises attendues",
                font=("Segoe UI", 8), bg="#e8f4fd", fg="#555"
            ).pack(anchor="w", padx=8, pady=(0, 4))

        frame_liste = tk.Frame(self.tab_lecture, bg="white")
        frame_liste.pack(fill="x", padx=10, pady=(0, 4))
        self.btn_charger_liste = tk.Button(
            frame_liste, text="Charger liste candidats (CSV)",
            font=("Segoe UI", 9),
            bg="#8e44ad", fg="white",
            activebackground="#6c3483", activeforeground="white",
            relief="flat", cursor="hand2",
            command=self._charger_liste_candidats
        )
        self.btn_charger_liste.pack(fill="x", ipady=5)
        self.lbl_liste_chargee = tk.Label(
            frame_liste,
            text="Aucune liste chargée - les noms seront saisis manuellement.",
            font=("Segoe UI", 8), fg="#888", bg="white"
        )
        self.lbl_liste_chargee.pack(anchor="w", pady=(2, 0))

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

        if self._on_export_all:
            self.btn_exporter_tous = tk.Button(
                self.tab_lecture, text="\u21a7  Exporter tous les parcours (CSV)",
                font=("Segoe UI", 10),
                bg="#16a085", fg="white",
                activebackground="#1a7a61", activeforeground="white",
                relief="flat", cursor="hand2",
                command=self._exporter_tous_parcours
            )
            # Visible directement dans l'onglet Lecture global
            self.btn_exporter_tous.pack(fill="x", padx=10, pady=(0, 6), ipady=6)

        self.btn_reset = tk.Button(
            self.tab_lecture, text="Effacer toutes les puces",
            font=("Segoe UI", 10),
            bg="#7f8c8d", fg="white",
            activebackground="#636e72", activeforeground="white",
            relief="flat", cursor="hand2",
            command=self._effacer_toutes_puces
        )
        self.btn_reset.pack(fill="x", padx=10, ipady=6)

    def _set_sidebar_visible(self, visible):
        """Affiche ou cache la sidebar noire sans perturber le reste du layout."""
        try:
            sidebar_outer = self._sidebar_canvas.master
            if visible:
                if not sidebar_outer.winfo_ismapped():
                    sidebar_outer.pack(side="left", fill="y", before=self.frame_content)
            else:
                if sidebar_outer.winfo_ismapped():
                    sidebar_outer.pack_forget()
        except Exception:
            pass

    def _afficher_tab_lecture(self):
        if self.tab_lecture is None:
            return
        self._afficher_frame(self.tab_lecture)
        if self._container_lecture is not None:
            self._set_active_btn(self._container_lecture)

    def _toggle_mode_lecture(self):
        """Bascule entre mode libre et mode contrôlée."""
        if self._mode_lecture == "libre":
            self._mode_lecture = "controlee"
            self.btn_mode_lecture.config(text="Mode : Contrôlée", bg="#8e44ad", activebackground="#6c3483")
            self._set_status("Mode contrôlée activé.", ok=True)
        else:
            self._mode_lecture = "libre"
            self.btn_mode_lecture.config(text="Mode : Libre", bg="#34495e", activebackground="#2c3e50")
            self._set_status("Mode libre activé.", ok=True)

    def is_mode_controlee(self):
        """Retourne True si le mode courant est 'contrôlée'."""
        return self._mode_lecture == "controlee"

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

    def _build_passage_section(self, parent, card_number, card_data, passage_num, nom=""):
        """Construit une section de passage dans le cadre scrollable de la carte."""
        pad = {"padx": 10, "pady": 4}

        if passage_num > 1:
            tk.Label(
                parent, text=f"━━━  Passage {passage_num}  ━━━",
                font=("Segoe UI", 9, "bold"), bg="white", fg="#1a73e8"
            ).pack(anchor="w", padx=10, pady=(8, 0))

        now = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        if self._parcours:
            balises_set = set(self._parcours["balises"])
            punches_terrain = [
                p for p in card_data.get("punches", [])
                if BALISE_MIN <= p[0] <= BALISE_MAX
            ]
            balises_pointees = {p[0] for p in punches_terrain if p[0] in balises_set}
            total_attendu = len(self._parcours["balises"])

            if self._parcours.get("ordre"):
                seen_ord, sequence_pointee = set(), []
                for p in punches_terrain:
                    if p[0] in balises_set and p[0] not in seen_ord:
                        seen_ord.add(p[0])
                        sequence_pointee.append(p[0])
                balises_attendues = self._parcours["balises"]
                nb_valides = 0
                for i, bal in enumerate(sequence_pointee):
                    if i < len(balises_attendues) and bal == balises_attendues[i]:
                        nb_valides += 1
                    else:
                        break
                ordre_valide   = set(sequence_pointee[:nb_valides])
                ordre_invalide = set(sequence_pointee[nb_valides:])
                nb_pointes     = nb_valides
            else:
                ordre_valide   = None
                ordre_invalide = None
                nb_pointes     = len(balises_pointees)
        else:
            punches_terrain = [
                p for p in card_data.get("punches", [])
                if BALISE_MIN <= p[0] <= BALISE_MAX
            ]
            balises_pointees = {p[0] for p in punches_terrain}
            total_attendu    = BALISE_MAX - BALISE_MIN + 1
            nb_pointes       = len(balises_pointees)
            ordre_valide     = None
            ordre_invalide   = None

        if passage_num == 1:
            frame_info = tk.LabelFrame(parent, text="Informations puce", font=("Segoe UI", 10, "bold"))
            frame_info.pack(fill="x", **pad)

            infos = [
                ("Participant :",              nom if nom else ""),
                ("Numéro puce :",             str(card_number)),
                ("Date de lecture :",         now),
                ("Balises (ordre) :" if self._parcours and self._parcours.get("ordre")
                 else "Balises pointées :",   f"{nb_pointes} / {total_attendu}"),
            ]
            candidat_info = self._liste_candidats.get(card_number)
            if candidat_info:
                if candidat_info.get("categorie"):
                    infos.append(("Catégorie :", candidat_info["categorie"]))
                if candidat_info.get("infos"):
                    infos.append(("Groupe :", candidat_info["infos"]))
            lbl_participant = None
            for row, (label, valeur) in enumerate(infos):
                tk.Label(frame_info, text=label, font=("Segoe UI", 9, "bold"), anchor="w").grid(
                    row=row, column=0, sticky="w", padx=8, pady=2)
                lbl = tk.Label(frame_info, text=valeur, font=("Segoe UI", 9), anchor="w", fg="#222")
                lbl.grid(row=row, column=1, sticky="w", padx=8, pady=2)
                if row == 0:
                    lbl_participant = lbl
            self._lbl_participant[card_number] = lbl_participant

        frame_temps = tk.LabelFrame(parent, text="Temps", font=("Segoe UI", 10, "bold"))
        frame_temps.pack(fill="x", **pad)

        # Calculer la durée course
        start = card_data.get("start")
        finish = card_data.get("finish")
        if isinstance(start, datetime) and isinstance(finish, datetime):
            delta = finish - start
            total_s = int(delta.total_seconds())
            h, rem = divmod(abs(total_s), 3600)
            m, s = divmod(rem, 60)
            duree_str = f"{h:02d}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"
        else:
            duree_str = ""

        # Parcours et durée en grand, affichés horizontalement
        parcours_nom = self._parcours["nom"] if self._parcours else "Lecture libre"

        inner = tk.Frame(frame_temps, bg=frame_temps.cget("bg"))
        inner.pack(fill="x", padx=8, pady=6)

        # Left column  vertical (Check / Départ / Arrivée)
        left_col = tk.Frame(inner, bg=inner.cget("bg"))
        left_col.grid(row=0, column=0, rowspan=3, sticky="nsew")
        for txt, val in (("Check", card_data.get("check")), ("Départ", start), ("Arrivée", finish)):
            f = tk.Frame(left_col, bg=left_col.cget("bg"))
            f.pack(anchor="w", pady=2)
            tk.Label(f, text=f"{txt} :", font=("Segoe UI", 9, "bold"), fg="#000").pack(side="left")
            tk.Label(f, text=self._fmt_time(val), font=("Segoe UI", 10), fg="#000").pack(side="left", padx=(8,0))       

        # Vertical separator
        sep1 = ttk.Separator(inner, orient="vertical")
        sep1.grid(row=0, column=1, rowspan=3, sticky="ns", padx=6)

        # Center column  parcours (middle row)
        lbl_parcours = tk.Label(inner, text=parcours_nom, font=("Segoe UI", 14, "bold"), fg="#000")
        lbl_parcours.grid(row=1, column=2, sticky="nsew", padx=6)

        # Vertical separator
        sep2 = ttk.Separator(inner, orient="vertical")
        sep2.grid(row=0, column=3, rowspan=3, sticky="ns", padx=6)

        # Right column  temps total (middle row)
        right_col = tk.Frame(inner, bg=inner.cget("bg"))
        right_col.grid(row=1, column=4, sticky="nsew")
        # Centrer horizontalement le contenu du bloc temps
        inner_time = tk.Frame(right_col, bg=right_col.cget("bg"))
        inner_time.pack(expand=True)
        tk.Label(inner_time, text="Temps :", font=("Segoe UI", 11, "bold"), fg="#000").pack(side="left")
        tk.Label(inner_time, text=duree_str, font=("Segoe UI", 16, "bold"), fg="#000").pack(side="left", padx=(8,0))    

        # Make columns 0,2,4 take equal space
        inner.grid_columnconfigure(0, weight=1)
        inner.grid_columnconfigure(1, weight=0)
        inner.grid_columnconfigure(2, weight=1)
        inner.grid_columnconfigure(3, weight=0)
        inner.grid_columnconfigure(4, weight=1)
        inner.grid_rowconfigure(0, weight=1)
        inner.grid_rowconfigure(1, weight=0)
        inner.grid_rowconfigure(2, weight=1)

        if self._parcours:
            if self._parcours.get("ordre"):
                if nb_valides == total_attendu:
                    res_bg  = "#27ae60"
                    res_txt = f"- Parcours réussi - toutes les {total_attendu} balises pointées dans le bon ordre !"
                elif nb_valides > 0:
                    res_bg  = "#e67e22"
                    res_txt = (f"-  Parcours correct jusqu'a  la balise {nb_valides}/{total_attendu}"
           f" - mauvais ordre a  partir de la balise {nb_valides + 1}")
                else:
                    res_bg  = "#e74c3c"
                    res_txt = "- Parcours invalide - la première balise n'est pas dans le bon ordre"
            else:
                if nb_pointes == total_attendu:
                    res_bg  = "#27ae60"
                    res_txt = f"- Parcours réussi - toutes les {total_attendu} balises pointées !"
                else:
                    res_bg  = "#e74c3c"
                    manquantes = total_attendu - nb_pointes
                    res_txt = f"- Parcours incomplet - {nb_pointes}/{total_attendu} balises pointées ({manquantes} manquante(s))"
            res_frame = tk.Frame(parent, bg=res_bg)
            res_frame.pack(fill="x", padx=10, pady=(4, 0))
            tk.Label(
                res_frame, text=res_txt,
                font=("Segoe UI", 9, "bold"), bg=res_bg, fg="white"
            ).pack(pady=6, padx=10, anchor="w")

        frame_punches = tk.LabelFrame(parent, text="Pointages balises", font=("Segoe UI", 10, "bold"))
        frame_punches.pack(fill="x", **pad)

        cols = ("Balise", "Heure")
        tree = ttk.Treeview(frame_punches, columns=cols, show="headings", height=8)
        for col in cols:
            tree.heading(col, text=col)
            tree.column(col, width=180, anchor="center")

        scrollbar = ttk.Scrollbar(frame_punches, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)
        tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # Dédupliquer : si une balise apparaît plusieurs fois, on garde le dernier pointage
        last_punch: dict = {}
        for p in punches_terrain:
            last_punch[p[0]] = p
        punches_uniques = list(last_punch.values())

        if self._parcours:
            tree.tag_configure("ok",    foreground="white", background="#27ae60")
            tree.tag_configure("ordre", foreground="white", background="#e67e22")
            tree.tag_configure("hors",  foreground="white", background="#e74c3c")
            for p in punches_uniques:
                heure = p[1].strftime("%H:%M:%S") if p[1] else ""
                if ordre_valide is not None:
                    if p[0] in ordre_valide:
                        tag = "ok"
                    elif p[0] in ordre_invalide:
                        tag = "ordre"
                    else:
                        tag = "hors"
                else:
                    tag = "ok" if p[0] in balises_set else "hors"
                tree.insert("", "end", values=(p[0], heure), tags=(tag,))
        else:
            for p in punches_uniques:
                heure = p[1].strftime("%H:%M:%S") if p[1] else ""
                tree.insert("", "end", values=(p[0], heure))

    #  Connexion a  la station
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
                    self._safe_after(0, lambda: self._pack_reconnecter())
                    return
                self.si = si_nouveau
                port = si_nouveau.port  # capture locale : self.si peut changer après
                self._safe_after(0, lambda: self._set_status(f"Connecté sur {port}", ok=True))
                self._safe_after(0, lambda: self.btn_lire.config(state="normal"))
            except Exception as e:
                self._safe_after(0, lambda: self._set_status(f"Erreur connexion : {e}", ok=False))
                self._safe_after(0, lambda: self.btn_lire.config(state="disabled"))
                self._safe_after(0, lambda: self._pack_reconnecter())
        threading.Thread(target=_try_connect, daemon=True).start()

    def _set_status(self, msg, ok=True):
        if self._closing:
            return
        try:
            color = "#27ae60" if ok else "#e74c3c"
            if self.lbl_status is not None:
                self.lbl_status.config(text=msg, fg=color)
        except Exception:
            pass  # Widget détruit, ignorer
        # En mode hub (lbl_status=None), transmettre le message via événement
        # pour que main.py puisse l'afficher dans le panneau global.
        try:
            self._last_status_msg = (msg, ok)
            root = self.winfo_toplevel()
            root.event_generate("<<AppStatus>>", when="tail")
        except Exception:
            pass

    def _pack_reconnecter(self):
        """Affiche le bouton 'Reconnecter' s'il existe (absent en mode hub)."""
        if self.btn_reconnecter is not None:
            try:
                self.btn_reconnecter.pack(side="right", padx=6, pady=2)
            except Exception:
                pass

    def _config_btn_lire(self, **kwargs):
        """Configure btn_lire s'il existe (absent en mode hub)."""
        if self.btn_lire is not None:
            try:
                self.btn_lire.config(**kwargs)
            except Exception:
                pass

    #  Lecture puce
    def _demarrer_lecture(self):
        if self._on_request_reader:
            # Mode partagé : libérer les autres onglets avant de prendre le lecteur
            self._on_request_reader(self)

        # Demander a  la fenêtre principale d'afficher l'onglet Lecture
        try:
            root = self.winfo_toplevel()
            root.event_generate("<<ShowLecture>>")
        except Exception:
            pass

        if self.si is None and self._on_request_reader is None:
            messagebox.showerror("Erreur", "Aucune station connectée.")
            return

        self._lire_en_cours = True
        self._erreur_connexion = False
        self._card_event.clear()
        self.btn_lire.config(state="disabled", text="Lecture en cours...")
        self.btn_annuler.pack(fill="x", padx=10, pady=(0, 10), ipady=6, after=self.btn_lire)

        if self.si is None:
            # Mode partagé sans connexion active : connecter puis lire
            self._set_status("Connexion a  la station...", ok=True)
            threading.Thread(target=self._connecter_puis_lire, daemon=True).start()
        else:
            self._set_status("Posez la puce sur la station...", ok=True)
            threading.Thread(target=self._lire_puce, daemon=True).start()

    def _connecter_puis_lire(self):
        """Connexion + lecture en un seul thread (mode partagé)."""
        try:
            si_nouveau = SIReaderReadout()
            if self._closing or not self._lire_en_cours:
                try:
                    si_nouveau.disconnect()
                except Exception:
                    pass
                return
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
                self._erreur_connexion = True
                self._safe_after(0, lambda: self._set_status(
                    f"Station mal configurée : {e}. Cliquez sur 'Relancer'.", ok=False))
                self._safe_after(0, lambda: self._reset_bouton(erreur=True))
                return
            self.si = si_nouveau
            port = si_nouveau.port
            self._safe_after(0, lambda: self._set_status(
                f"Connecté sur {port} posez la puce...", ok=True))
            self._lire_puce()
        except Exception as e:
            self._erreur_connexion = True
            self._safe_after(0, lambda: self._set_status(
                f"Erreur connexion : {e}. Cliquez sur 'Relancer'.", ok=False))
            self._safe_after(0, lambda: self._reset_bouton(erreur=True))

    def _release_reader(self):
        """Libère la connexion SI (appelé quand un autre onglet prend le contrôle)."""
        self._lire_en_cours = False
        if self.si is not None:
            try:
                self.si.disconnect()
            except Exception:
                pass
            self.si = None
        self._safe_after(0, lambda: self._set_status(
            "Lecture active dans un autre onglet  les puces lues apparaîtront ici automatiquement.",
            ok=True
        ))
        self._safe_after(0, lambda: self.btn_annuler.pack_forget())
        self._safe_after(0, lambda: self.btn_lire.config(
            state="normal", text="Attendre une puce"
        ))

    def _lire_puce(self):
        """Thread de lecture. En cas de perte de connexion, on s'arrête immédiatement
        et on signale l'échec de façon explicite (pas de reconnexion automatique
        silencieuse) — l'utilisateur reclique consciemment pour relancer."""
        while self._lire_en_cours and not self._closing:
            try:
                self.si.flush()
                self.si.sicard = None

                while self._lire_en_cours and not self._closing:
                    # Attendre qu'une puce soit posée
                    while self._lire_en_cours and not self._closing and not self.si.poll_sicard():
                        sleep(0.5)

                    if not self._lire_en_cours or self._closing:
                        break

                    card_number = self.si.sicard
                    card_data   = self.si.read_sicard()
                    self.si.ack_sicard()

                    # Demander au thread principal de traiter la puce, puis attendre
                    self._card_event.clear()
                    if self._on_route_puce:
                        self._safe_after(0, lambda cn=card_number, cd=card_data: self._on_route_puce(self, cn, cd))
                    else:
                        self._safe_after(0, lambda cn=card_number, cd=card_data: self._creer_onglet_puce(cn, cd))
                    self._card_event.wait(timeout=120)  # timeout de sécurité

                    if self._lire_en_cours and not self._closing:
                        # Préparer la prochaine lecture
                        self.si.sicard = None
                        self.si.flush()
                        self._safe_after(0, lambda: self._set_status("Posez la prochaine puce sur la station...", ok=True))

                break  # boucle terminée proprement (annulation utilisateur)

            except Exception as e:
                if self._closing or not self._lire_en_cours:
                    break
                # Échec immédiat et explicite : pas de tentative de reconnexion
                # automatique. On coupe la connexion et on signale l'erreur ;
                # l'utilisateur doit recliquer sur "Relancer" pour reprendre.
                if self.si is not None:
                    try:
                        self.si.disconnect()
                    except Exception:
                        pass
                    self.si = None
                err = str(e)
                self._erreur_connexion = True
                self._safe_after(0, lambda er=err: self._set_status(
                    f"Connexion perdue : {er}. Cliquez sur 'Relancer'.", ok=False))
                self._safe_after(0, lambda: self._pack_reconnecter())
                self._safe_after(0, lambda: self._reset_bouton(erreur=True))
                return

        # Boucle terminée proprement (annulation utilisateur)
        self._safe_after(0, self._reset_bouton)

    def _creer_onglet_puce(self, card_number, card_data, event_to_set=None, broadcast=True):
        """Demande un nom (1ère lecture) puis crée ou complète le panneau de la carte."""
        is_new = card_number not in self._card_passages
        if is_new:
            # Recherche robuste du candidat dans la table (différents types de clé possibles)
            candidat = None
            try:
                candidat = self._liste_candidats.get(card_number)
            except Exception:
                candidat = None
            if candidat is None:
                try:
                    candidat = self._liste_candidats.get(int(card_number))
                except Exception:
                    pass
            if candidat is None:
                try:
                    candidat = self._liste_candidats.get(str(card_number))
                except Exception:
                    pass

            if candidat:
                prenom  = str(candidat.get("prenom", "")).strip()
                nom_fam = str(candidat.get("nom", "")).strip()
                nom = f"{prenom} {nom_fam}".strip() or str(card_number)
                nom_base, i = nom, 1
                while nom in self._noms.values():
                    i += 1
                    nom = f"{nom_base} ({i})"
            else:
                nom = self._demander_nom(card_number)
                if nom is None:  # app fermée ou lecture annulée
                    self._lire_en_cours = False
                    (event_to_set or self._card_event).set()
                    self._safe_after(0, lambda: self._reset_bouton())
                    return
            self._noms[card_number] = nom
        else:
            nom = self._noms[card_number]

        passage = self._card_passages.get(card_number, 0) + 1
        self._card_passages[card_number] = passage
        if card_number not in self._card_data:
            self._card_data[card_number] = []
        self._card_data[card_number].append(card_data)

        self._ajouter_puce_dans_ui(card_number, card_data, nom, passage, is_new)
        msg_passage = f" (passage {passage})" if passage > 1 else ""
        self._set_status(f"Puce {card_number} lue avec succès{msg_passage}.", ok=True)
        (event_to_set or self._card_event).set()  # signale au thread que le traitement est terminé
        if broadcast and self._on_broadcast and not self._closing:
            self._on_broadcast(self, card_number, card_data, nom)
        # Rafraîchir le hub (compteurs) si présent
        try:
            root = self.winfo_toplevel()
            root.event_generate("<<HubRefresh>>")
        except Exception:
            pass

    def _ajouter_puce_dans_ui(self, card_number, card_data, nom, passage, is_new):
        """Crée le frame scrollable (1ère lecture) ou ajoute un passage (relecture)."""
        if is_new:
            frame_outer = tk.Frame(self.frame_content, bg="white")
            canvas = tk.Canvas(frame_outer, bg="white", highlightthickness=0)
            scroll = tk.Scrollbar(frame_outer, orient="vertical", command=canvas.yview)
            canvas.configure(yscrollcommand=scroll.set)
            scroll.pack(side="right", fill="y")
            canvas.pack(side="left", fill="both", expand=True)

            frame_inner = tk.Frame(canvas, bg="white")
            canvas_win = canvas.create_window((0, 0), window=frame_inner, anchor="nw")
            frame_inner.bind(
                "<Configure>",
                lambda e, c=canvas: c.configure(scrollregion=c.bbox("all"))
            )
            canvas.bind(
                "<Configure>",
                lambda e, c=canvas, w=canvas_win: c.itemconfig(w, width=e.width)
            )

            self._frames[card_number] = frame_outer
            self._frame_inners[card_number] = frame_inner
            self._frame_canvases[card_number] = canvas

            container = tk.Frame(self.sidebar, bg="#1e1e2e", padx=2, pady=2)
            container.pack(fill="x", padx=6, pady=2)
            btn = tk.Button(
                container, text=nom if nom else str(card_number),
                bg="#2d2d44", fg="white", relief="flat",
                font=("Segoe UI", 9), cursor="hand2",
                activebackground="#3d3d5c", activeforeground="white",
                command=lambda cn=card_number: [
                    self._afficher_frame(self._frames[cn]),
                    self._set_active_btn(self._sidebar_btns[cn])
                ]
            )
            btn.pack(fill="x", ipady=4)
            self._sidebar_btns[card_number] = container
            self._sidebar_inner[card_number] = btn

            menu = tk.Menu(self, tearoff=0)
            menu.add_command(label="Renommer", command=lambda cn=card_number: self._renommer_puce(cn))
            menu.add_command(label="Déplacer vers...", command=lambda cn=card_number: self._demander_deplacement(cn))  

            def _popup(e, m=menu):
                try:
                    m.tk_popup(e.x_root, e.y_root)
                finally:
                    m.grab_release()
            btn.bind("<Button-3>", _popup)

            if len(self._frames) == 1 and self._read_controls and self.btn_exporter is not None:
                self.btn_exporter.pack(fill="x", padx=10, pady=(0, 6), ipady=6)
                if hasattr(self, "btn_exporter_tous") and self.btn_exporter_tous is not None:
                    self.btn_exporter_tous.pack(fill="x", padx=10, pady=(0, 6), ipady=6)
            self.lbl_sidebar.config(text=f"Puces : {len(self._frames)}")
        else:
            ttk.Separator(
                self._frame_inners[card_number], orient="horizontal"
            ).pack(fill="x", padx=10, pady=(12, 0))

        frame_inner = self._frame_inners[card_number]
        canvas = self._frame_canvases[card_number]
        self._build_passage_section(frame_inner, card_number, card_data, passage, nom)

        # Auto-scroll vers le bas pour voir le nouveau passage
        if passage > 1:
            frame_inner.update_idletasks()
            canvas.configure(scrollregion=canvas.bbox("all"))
            canvas.yview_moveto(1.0)

        self._afficher_frame(self._frames[card_number])
        self._set_active_btn(self._sidebar_btns[card_number])

    def recevoir_puce(self, card_number, card_data, nom=""):
        """Reçoit les données d'une puce lue dans un autre onglet (diffusion)."""
        if self._closing:
            return
        self.after(0, lambda: self._recevoir_puce_ui(card_number, card_data, nom))

    def _recevoir_puce_ui(self, card_number, card_data, nom):
        """Enregistre une puce reçue par diffusion."""
        if self._closing:
            return
        is_new = card_number not in self._card_passages
        if is_new:
            self._noms[card_number] = nom
        passage = self._card_passages.get(card_number, 0) + 1
        self._card_passages[card_number] = passage
        if card_number not in self._card_data:
            self._card_data[card_number] = []
        self._card_data[card_number].append(card_data)
        self._ajouter_puce_dans_ui(card_number, card_data, nom, passage, is_new)
        msg_passage = f" (passage {passage})" if passage > 1 else ""
        self._set_status(f"Puce {card_number} reçue depuis un autre onglet{msg_passage}.", ok=True)
        # Rafraîchir le hub (compteurs) si présent
        try:
            root = self.winfo_toplevel()
            root.event_generate("<<HubRefresh>>")
        except Exception:
            pass

    def _demander_nom(self, card_number):
        """Affiche une boîte de dialogue pour saisir le nom du participant (obligatoire)."""
        while True:
            dialog = tk.Toplevel(self)
            dialog.title("Nom du participant")
            dialog.geometry("320x175")
            dialog.resizable(False, False)
            self._name_dialog = dialog
            dialog.grab_set()
            dialog.focus_set()

            tk.Label(dialog, text=f"Puce n{card_number}", font=("Segoe UI", 9), fg="#555").pack(pady=(12, 2))
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
                if valeur in self._noms.values():
                    self._lbl_erreur_nom.config(text="Ce nom est déja  utilisé par une autre puce.")
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
            self._name_dialog = None
            if self._closing or annule[0]:
                return None
            if nom_result[0]:
                return nom_result[0]

    def _annuler_lecture(self):
        """Annule l'attente d'une puce en cours."""
        self._lire_en_cours = False
        # Fermer le dialogue de saisie du nom s'il est ouvert (interrompt la saisie)
        try:
            if getattr(self, "_name_dialog", None) is not None:
                try:
                    self._name_dialog.destroy()
                except Exception:
                    pass
        except Exception:
            pass
        # Débloquer le thread de lecture si nécessaire
        try:
            self._card_event.set()
        except Exception:
            pass
        self._set_status("Lecture annulée.", ok=True)

    def _renommer_puce(self, card_number):
        """Affiche un dialogue pour renommer le participant d'une carte."""
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

        lbl_err = tk.Label(dialog, text="", fg="#e74c3c", font=("Segoe UI", 9))
        lbl_err.pack()

        def valider(event=None):
            nouveau = entry.get().strip()
            if not nouveau:
                lbl_err.config(text="Le nom ne peut pas être vide.")
                return
            noms_autres = {n for cn, n in self._noms.items() if cn != card_number}
            if nouveau in noms_autres:
                lbl_err.config(text="Ce nom est déja  utilisé par une autre puce.")
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

    def _demander_deplacement(self, card_number):
        """Demande au MainApp de déplacer cette puce vers un autre parcours."""
        if self._on_request_move:
            try:
                self._on_request_move(self, card_number)
            except Exception as e:
                messagebox.showerror("Erreur", f"Erreur lors du déplacement : {e}")
        else:
            messagebox.showinfo("Déplacer", "Fonction non disponible (pas de callback).")

    def remove_card(self, card_number, moved_to=None):
        """Supprime complètement une puce de cet onglet (après déplacement)."""
        frame = self._frames.pop(card_number, None)
        if frame:
            try:
                frame.destroy()
            except Exception:
                pass
        container = self._sidebar_btns.pop(card_number, None)
        if container:
            try:
                container.destroy()
            except Exception:
                pass
        self._sidebar_inner.pop(card_number, None)
        self._frame_inners.pop(card_number, None)
        self._frame_canvases.pop(card_number, None)
        passages = self._card_data.pop(card_number, [])
        self._noms.pop(card_number, None)
        self._lbl_participant.pop(card_number, None)
        self._card_passages.pop(card_number, None)
        move = {
            "card": card_number,
            "moved_to": moved_to,
            "moved_by": "user",
            "time": datetime.now().isoformat(),
            "passages_moved": len(passages),
        }
        self._moves.append(move)
        # Update exporter buttons visibility
        if not self._frames:
            try:
                self.btn_exporter.pack_forget()
                if hasattr(self, "btn_exporter_tous"):
                    self.btn_exporter_tous.pack_forget()
            except Exception:
                pass
        self.lbl_sidebar.config(text=f"Puces : {len(self._frames)}")
        self._set_status(f"Puce {card_number} déplacée vers {moved_to}.", ok=True)
        # Demander au MainApp de rafraîchir la liste du hub (si présent)
        try:
            root = self.winfo_toplevel()
            root.event_generate("<<HubRefresh>>")
        except Exception:
            pass

    def _charger_liste_candidats(self):
        chemin = filedialog.askopenfilename(
            title="Charger la liste des candidats",
            filetypes=[("Fichier CSV", "*.csv"), ("Tous les fichiers", "*.*")]
        )
        if not chemin:
            return

        try:
            candidats = parse_candidate_csv(chemin)
        except Exception as e:
            messagebox.showerror("Erreur", f"Impossible de charger la liste :\n{e}")
            return

        self._liste_candidats = candidats
        nb = len(candidats)
        self._set_status(f"Liste candidats chargée : {nb} personne(s).", ok=True)
        try:
            if getattr(self, "lbl_liste_chargee", None):
                self.lbl_liste_chargee.config(text=f"✓  {nb} candidat(s) chargé(s)", fg="#27ae60")
        except Exception:
            pass
        if self._on_candidats_loaded:
            self._on_candidats_loaded(self, candidats)

    def _appliquer_candidats(self, candidats):
        """Applique une liste de candidats (diffusion depuis un autre onglet)."""
        self._liste_candidats = candidats
        nb = len(candidats)
        try:
            if getattr(self, "lbl_liste_chargee", None):
                self.lbl_liste_chargee.config(text=f"-  {nb} candidat(s) chargé(s)", fg="#27ae60")
        except Exception:
            pass

    def _count_max_punches(self):
        """Retourne le nombre max de pointages terrain sur toutes les puces de cet onglet."""
        max_p = 0
        for passages in self._card_data.values():
            for data in passages:
                n = len([p for p in data.get("punches", []) if BALISE_MIN <= p[0] <= BALISE_MAX])
                if n > max_p:
                    max_p = n
        return max_p

    def _get_punch_statuses(self, punches_terrain):
        """Retourne la liste des statuts pour chaque pointage terrain.

        """
        if not self._parcours:
            return [None] * len(punches_terrain)

        balises_set = set(self._parcours["balises"])

        if self._parcours.get("ordre"):
            # Même algorithme de validation que _build_passage_section
            seen_ord, sequence_pointee = set(), []
            for p in punches_terrain:
                if p[0] in balises_set and p[0] not in seen_ord:
                    seen_ord.add(p[0])
                    sequence_pointee.append(p[0])
            balises_attendues = self._parcours["balises"]
            nb_valides = 0
            for i, bal in enumerate(sequence_pointee):
                if i < len(balises_attendues) and bal == balises_attendues[i]:
                    nb_valides += 1
                else:
                    break
            ordre_valide = set(sequence_pointee[:nb_valides])
            return ["ok" if p[0] in ordre_valide else "bad" for p in punches_terrain]
        else:
            return ["ok" if p[0] in balises_set else "bad" for p in punches_terrain]

    def _build_csv_rows(self, max_punches):
        """Génère les lignes CSV pour toutes les puces de cet onglet.

        Colonnes : Numéro puce | Participant | Parcours | Nb postes | Passage |
                   Départ | Arrivée | Temps course | [Balise i | Temps i]...

        Pour un parcours défini : n'exporte que les balises effectivement pointées,
        triées par numéro croissant. Si une balise pointée n'appartient pas au
        parcours attendu, la colonne temps contiendra "PM" (poste manquant).
        """
        parcours_nom = self._parcours["nom"] if self._parcours else "Lecture libre"
        parcours_set = set(self._parcours.get("balises", [])) if self._parcours else set()
        nb_postes    = len(self._parcours["balises"]) if self._parcours else ""
        rows = []
        for card_number, passages in self._card_data.items():
            nom = self._noms.get(card_number, "")
            for passage_num, data in enumerate(passages, start=1):
                punches = [
                    p for p in data.get("punches", [])
                    if BALISE_MIN <= p[0] <= BALISE_MAX
                ]
                # Dédupliquer : garder le dernier pointage pour chaque balise
                last_punch = {}
                for p in punches:
                    last_punch[p[0]] = p[1]

                # Statuts des pointages (utile en mode 'ordre')  on garde le statut
                # correspondant a  la dernière occurrence de chaque balise.
                punch_status_by_code = {}
                if self._parcours:
                    statuses = self._get_punch_statuses(punches)
                    for (p, st) in zip(punches, statuses):
                        punch_status_by_code[p[0]] = st

                start  = data.get("start")
                finish = data.get("finish")
                if isinstance(start, datetime) and isinstance(finish, datetime):
                    delta    = finish - start
                    total_s  = int(delta.total_seconds())
                    h, rem   = divmod(abs(total_s), 3600)
                    m, s     = divmod(rem, 60)
                    temps_course = f"{h:02d}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"
                else:
                    temps_course = ""

                row = [
                    card_number,
                    nom,
                    parcours_nom,
                    nb_postes,
                    passage_num,
                    self._fmt_time(start),
                    self._fmt_time(finish),
                    temps_course,
                ]

                # Utiliser uniquement les balises réellement pointées, triées numériquement
                balises_pointes = sorted(last_punch.keys())
                for b in balises_pointes:
                    row.append(str(b))
                    if self._parcours and b not in parcours_set:
                        row.append("PM")
                    # En mode 'ordre', si le pointage est hors-séquence, indiquer PM
                    elif self._parcours and self._parcours.get("ordre") and punch_status_by_code.get(b) != "ok":        
                        row.append("PM")
                    else:
                        t = last_punch.get(b)
                        row.append(t.strftime("%H:%M:%S") if t else "")

                # Compléter pour atteindre max_punches
                row += [""] * ((max_punches - len(balises_pointes)) * 2)

                rows.append(row)
        return rows

    def _exporter_csv(self):
        """Exporte toutes les puces de cet onglet dans un fichier CSV.

        Retourne True si l'export a été réalisé, False si annulé ou vide.
        """
        if not self._frames:
            return False
        chemin = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("Fichier CSV", "*.csv")],
            initialfile=f"lecture_puces_{datetime.now().strftime('%d-%m-%Y')}.csv",
            title="Enregistrer l'export CSV"
        )
        if not chemin:
            return False
        max_punches = self._count_max_punches()
        # En-tête générique : Balise 1, Temps 1 ... selon max_punches
        header = ["Numéro puce", "Participant", "Parcours", "Nb postes", "Passage",
                  "Départ", "Arrivée", "Temps course"]
        for i in range(1, max_punches + 1):
            header += [f"Balise {i}", f"Temps {i}"]

        with open(chemin, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.writer(f, delimiter=";")
            writer.writerow(header)
            for row in self._build_csv_rows(max_punches):
                writer.writerow(row)
        self._set_status(f"Export CSV enregistré : {chemin}", ok=True)
        return True

    def _exporter_tous_parcours(self):
        """Délègue l'export multi-parcours au callback fourni par main.py."""
        if self._on_export_all:
            self._on_export_all()

    def _effacer_toutes_puces(self):
        """Supprime toutes les puces lues de la sidebar et remet l'interface a  zéro."""
        if not self._frames:
            return
        if not messagebox.askyesno(
            "Effacer toutes les lectures",
            f"Voulez-vous effacer les données de {len(self._frames)} puce(s) ?\n\nCette action est irréversible.",    
            icon="warning"
        ):
            return

        for frame in self._frames.values():
            frame.destroy()
        for container in self._sidebar_btns.values():
            container.destroy()

        self._frames.clear()
        self._frame_inners.clear()
        self._frame_canvases.clear()
        self._sidebar_btns.clear()
        self._sidebar_inner.clear()
        self._noms.clear()
        self._card_data.clear()
        self._lbl_participant.clear()
        self._card_passages.clear()
        self._active_btn = None
        self._current = None

        if self.btn_exporter is not None:
            self.btn_exporter.pack_forget()
        if hasattr(self, "btn_exporter_tous") and self.btn_exporter_tous is not None:
            self.btn_exporter_tous.pack_forget()
        self.lbl_sidebar.config(text="Puces : 0")


        if self._read_controls:
            self._afficher_tab_lecture()
        self._set_status(f"Connecté sur {self.si.port}" if self.si else "Station non connectée.", ok=self.si is not None)

    def _on_close(self):
        """Ferme proprement en libérant le port série, puis supprime l'onglet."""
        if self._closing:
            return
        self._closing = True
        self._lire_en_cours = False
        self._card_event.set()  # débloque le thread s'il attend le dialogue de nom

        # Attendre que les threads en cours se terminent
        self.after(100, self._finaliser_fermeture)

    def _finaliser_fermeture(self):
        """Seconde étape de fermeture après que les threads aient eu le temps de s'arrêter."""
        if self.si is not None:
            try:
                self.si.disconnect()
            except Exception:
                pass
        cb = self._on_close_cb
        try:
            self.destroy()
        except Exception:
            pass
        if cb:
            cb()

    #  Utilitaires
    def _fmt_time(self, val):
        if val is None:
            return ""
        if isinstance(val, datetime):
            return val.strftime("%d/%m/%Y %H:%M:%S")
        return str(val)

    def _safe_after(self, ms, func):
        """Appel after() sécurisé : ignoré si l'app est en cours de destruction."""
        if self._closing:
            return
        try:
            self.after(ms, func)
        except Exception:
            pass

    def _reset_bouton(self, erreur=False):
        if self._closing:
            return
        try:
            self._lire_en_cours = False
            self.btn_annuler.pack_forget()
            etat = "disabled" if erreur else "normal"
            self.btn_lire.config(state=etat, text="Attendre une puce")
        except Exception:
            pass  # Widget détruit, ignorer
        # Notifier le hub pour qu'il mette à jour la couleur de son propre bouton
        try:
            root = self.winfo_toplevel()
            root.event_generate("<<AppReadingStopped>>", when="tail")
        except Exception:
            pass

if __name__ == "__main__":
    root = tk.Tk()
    root.title("Lecture Puce SportIdent")
    root.geometry("720x600")
    root.resizable(False, False)
    app = AppLecturePuce(root, on_close=root.destroy)
    root.protocol("WM_DELETE_WINDOW", app._on_close)
    root.mainloop()