# Gestionnaire de course SportIdent

Application de bureau (Windows, Python/Tkinter) pour gérer la lecture de puces SportIdent lors d'une course d'orientation : création de parcours, lecture de puces sur une ou plusieurs stations, validation des pointages, et export des résultats en CSV.

## Fonctionnalités

- **Création de parcours** : grille de sélection des balises (31 à 256), sélection au glisser, presets rapides, mode "ordre obligatoire"
- **Import de parcours** existants : `.tsv`, `.csv`, et formats OCAD (`.xml` IOF v2/v3, `.txt`)
- **Gestion d'un lot multi-parcours** : plusieurs parcours définis et lancés ensemble
- **Lecture de puces SI** sur une station SportIdent (BSM7/8), avec connexion partagée entre plusieurs parcours ouverts simultanément
- **Routage automatique** d'une puce lue vers le bon parcours (par correspondance des balises pointées), avec un **mode contrôlée** proposant une validation manuelle avant chaque enregistrement
- **Validation d'ordre des balises** avec une marge d'erreur (N+2), et affichage coloré (bonne balise / hors ordre / hors parcours)
- **Galerie d'images balises** : associe une image à chaque balise et l'affiche après lecture d'une puce
- **Export CSV** des résultats, par parcours ou agrégé sur tous les parcours ouverts

Le détail complet des fonctionnalités et l'historique des évolutions sont dans [`recap.md`](recap.md).

## Installation

### Utilisateurs (Windows)

Télécharger le dernier exécutable depuis la page [Releases](../../releases) et le lancer directement — aucune installation requise.

Un pilote peut être nécessaire pour que Windows reconnaisse la station SportIdent en USB : voir le [pilote USB officiel SportIdent](https://www.sportident.com/products/usb-driver).

### Développeurs

Prérequis : Python 3.

```bash
pip install -r requirements.txt
python main.py
```

L'affichage des images de la galerie balises dans tous les formats (au-delà de PNG/GIF) nécessite en plus [Pillow](https://pypi.org/project/Pillow/) (`pip install pillow`) — optionnel, l'application fonctionne sans.

## Structure du projet

```
Application/
├── main.py                    # point d'entrée
├── core/                      # règles métier (constantes, validation des pointages)
├── io_/                       # lecture/écriture de fichiers (parcours, candidats, export CSV)
├── ui/                        # interface graphique (Tkinter)
├── sireader2.py                # bibliothèque de communication avec les stations SportIdent
├── check_punches.py            # script CLI : vérifie des pointages par rapport à un parcours
└── si_read_card.py             # script CLI : lecture simple d'une puce
```

Voir [`recap.md`](recap.md) pour le détail de chaque module.

## Licence

Ce projet est distribué sous licence **[GNU General Public License v3.0](LICENSE)**.

Il s'appuie sur `sireader2.py`, une bibliothèque tierce sous licence GPLv3, développée par Gaudenz Steinlin, Simon Harston, Jan Vorwerk et Per Magnusson (voir l'en-tête du fichier). Cette dépendance impose que l'ensemble du projet soit distribué sous GPLv3.

Concrètement, cela signifie que toute personne peut utiliser, étudier, modifier et redistribuer ce code, à condition de :
- conserver la mention de licence et créditer les auteurs originaux,
- republier le code source de toute version modifiée distribuée,
- distribuer cette version modifiée sous la même licence (GPLv3).
