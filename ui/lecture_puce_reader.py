#!/usr/bin/env python3
"""ReaderMixin : connexion a la station SI et thread de lecture (mixin de AppLecturePuce).

Regroupe tout ce qui touche a la station physique : connexion (autonome ou
partagee via le hub), configuration du protocole etendu + mode lecture,
thread bloquant de lecture des puces, annulation, et les petits utilitaires
lies (_safe_after, _reset_bouton).

Extrait de ui_lecture_puce.py sans changement de comportement : ReaderMixin
est melange (mixin) dans AppLecturePuce (ui/lecture_puce.py), qui garde
l'etat (self.si, self._lire_en_cours, self.btn_lire, ...) initialise dans
son __init__ ; les methodes ci-dessous continuent d'y acceder via `self`
exactement comme avant.
"""

import threading
from time import sleep
from tkinter import messagebox

from sireader2 import SIReaderReadout, SIReaderException


class ReaderMixin:
    """Mixin de AppLecturePuce : connexion à la station SI et thread de
    lecture des puces (autonome ou piloté par le hub)."""

    #  Connexion a  la station
    def _connect_station(self):
        """Lance dans un thread la connexion (autonome) à la station SI et
        sa configuration en protocole étendu + mode lecture, sans bloquer l'UI."""
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
            """Corps du thread de connexion (bloquant, tourne hors du thread UI)."""
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
                    erreur_msg = f"Station mal configurée : {e}"
                    try:
                        si_nouveau.disconnect()
                    except Exception:
                        pass
                    self._safe_after(0, lambda: self._set_status(erreur_msg, ok=False))
                    self._safe_after(0, lambda: self.btn_lire.config(state="disabled"))
                    self._safe_after(0, lambda: self._pack_reconnecter())
                    return
                self.si = si_nouveau
                port = si_nouveau.port  # capture locale : self.si peut changer après
                self._safe_after(0, lambda: self._set_status(f"Connecté sur {port}", ok=True))
                self._safe_after(0, lambda: self.btn_lire.config(state="normal"))
            except Exception as e:
                erreur_msg = f"Erreur connexion : {e}"
                self._safe_after(0, lambda: self._set_status(erreur_msg, ok=False))
                self._safe_after(0, lambda: self.btn_lire.config(state="disabled"))
                self._safe_after(0, lambda: self._pack_reconnecter())
        threading.Thread(target=_try_connect, daemon=True).start()

    def _set_status(self, msg, ok=True):
        """Met à jour le message de statut (vert si `ok`, rouge sinon). En mode
        autonome, met à jour le label local ; dans tous les cas, émet un
        événement Tkinter `<<AppStatus>>` pour que le hub puisse aussi
        l'afficher dans son panneau global."""
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
        """Démarre l'attente d'une puce (bouton "Attendre une puce") : réclame
        le lecteur partagé si on est dans le hub, puis lance le thread de lecture."""
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
            threading.Thread(target=self._connecter_puis_lire, daemon=True).start()
        else:
            self._set_status("Posez la puce sur la station...", ok=True)
            threading.Thread(target=self._lire_puce, daemon=True).start()

    def _connecter_puis_lire(self):
        """Connexion + lecture en un seul thread (mode partagé)."""
        try:
            import serial.tools.list_ports as _lp
            if not list(_lp.comports()):
                self._erreur_connexion = True
                self._safe_after(0, lambda: self._reset_bouton(erreur=True))
                return
        except Exception:
            pass
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
                erreur_msg = f"Station mal configurée : {e}."
                try:
                    si_nouveau.disconnect()
                except Exception:
                    pass
                self._erreur_connexion = True
                self._safe_after(0, lambda: self._set_status(erreur_msg, ok=False))
                self._safe_after(0, lambda: self._reset_bouton(erreur=True))
                return
            self.si = si_nouveau
            port = si_nouveau.port
            self._safe_after(0, lambda: self._set_status(
                f"Connecté sur le port {port}", ok=True))
            self._lire_puce()
        except Exception as e:
            erreur_msg = f"Erreur connexion : {e}."
            self._erreur_connexion = True
            self._safe_after(0, lambda: self._set_status(erreur_msg, ok=False))
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
                    f"Connexion perdue : {er}.", ok=False))
                self._safe_after(0, lambda: self._pack_reconnecter())
                self._safe_after(0, lambda: self._reset_bouton(erreur=True))
                return

        # Boucle terminée proprement (annulation utilisateur)
        self._safe_after(0, self._reset_bouton)

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

    def _safe_after(self, ms, func):
        """Appel after() sécurisé : ignoré si l'app est en cours de destruction."""
        if self._closing:
            return
        try:
            self.after(ms, func)
        except Exception:
            pass

    def _reset_bouton(self, erreur=False):
        """Remet le bouton "Attendre une puce" en état repos ; le désactive
        si la lecture s'est arrêtée sur une erreur de connexion."""
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
