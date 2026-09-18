#!/usr/bin/env python3
"""Point d'entrée — SportIdent."""

from ui.app_main import MainApp


def main():
    """Lance l'application : crée la fenêtre principale et démarre la boucle Tkinter."""
    app = MainApp()
    app.root.mainloop()


if __name__ == "__main__":
    main()
