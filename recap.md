# Gestionnaire de course SportIdent — Journal des modifications

## Table des matières

- [Refactorisation (branche `refactoring`)](#refactorisation-branche-refactoring)
- [ui_parcours.py](#ui_parcourspy) *(historique — voir [table de correspondance](#table-de-correspondance-ancien--nouveau))*
- [ui_lecture_puce.py](#ui_lecture_pucepy) *(historique — voir [table de correspondance](#table-de-correspondance-ancien--nouveau))*
- [main.py](#mainpy) *(historique — voir [table de correspondance](#table-de-correspondance-ancien--nouveau))*
- [Système d'images balises](#système-dimages-balises)

---

## Refactorisation (branche `refactoring`)

À partir de la v1.0.1, le code a été réorganisé pour éliminer les duplications
et réduire la taille des fichiers (`main.py`, `ui_parcours.py` et
`ui_lecture_puce.py` dépassaient chacun 1300-1550 lignes). Aucun changement
de comportement n'était visé : chaque étape a été vérifiée par compilation,
tests de non-régression et/ou instanciation réelle de l'application avant
d'être committée.

### Nouvelle arborescence

```
Application/
├── main.py                    # point d'entrée minimal (crée MainApp, lance mainloop) — 14 lignes
├── core/
│   ├── constants.py           # BALISE_MIN/MAX, BALISES_TOUTES, GRID_COLS, PRESETS
│   └── validation.py          # algorithme de validation d'ordre des balises
├── io_/
│   ├── parcours_parsers.py    # parseurs TSV / CSV / OCAD XML / OCAD TXT
│   ├── candidats_csv.py       # parseur du CSV liste de candidats
│   └── export_csv.py          # génération + écriture de l'export CSV des pointages
├── ui/
│   ├── app_main.py            # classe MainApp (fenêtre principale, onglet Accueil)
│   ├── hub.py                 # HubMixin : hub multi-parcours (routage, état, orchestration)
│   ├── hub_view.py            # HubViewMixin : construction des widgets du hub
│   ├── hub_validation.py      # HubValidationMixin : dialogue de validation mode contrôlée
│   ├── parcours.py            # classe AppParcours (éditeur : grille de balises)
│   ├── parcours_lot.py        # LotMixin : gestion du lot multi-parcours
│   ├── lecture_puce.py        # classe AppLecturePuce (affichage, dialogues, export)
│   └── lecture_puce_reader.py # ReaderMixin : connexion station + thread de lecture
├── sireader2.py                # inchangé (bibliothèque protocole SI, bas niveau)
├── check_punches.py            # inchangé (script CLI indépendant)
└── si_read_card.py             # inchangé (script CLI indépendant)
```

### Table de correspondance (ancien → nouveau)

| Ancien emplacement | Nouvel emplacement | Ce qui a changé |
|---|---|---|
| `main.py` (classe `MainApp`, ~1380 lignes) | `main.py` (14 lignes, point d'entrée) + `ui/app_main.py` (287 lignes) + `ui/hub.py`/`hub_view.py`/`hub_validation.py` (le hub multi-parcours, ~1230 lignes à 3) | Découpage en mixins (`HubMixin`, `HubViewMixin`, `HubValidationMixin`), aucune logique modifiée — méthodes déplacées telles quelles |
| `ui_parcours.py` (~1550 lignes) | `ui/parcours.py` (~1060 lignes) + `ui/parcours_lot.py` (`LotMixin`, gestion du lot) | Renommé, parseurs sortis, gestion du lot multi-parcours isolée en mixin |
| `ui_lecture_puce.py` (~1520 lignes) | `ui/lecture_puce.py` (~1040 lignes) + `ui/lecture_puce_reader.py` (`ReaderMixin`, connexion + thread) | Renommé, `parse_candidate_csv` sortie, connexion série/thread isolés en mixin |
| `BALISE_MIN`/`BALISE_MAX`/... (dupliqués dans `ui_parcours.py` **et** `ui_lecture_puce.py`) | `core/constants.py` | Source unique |
| Algorithme de validation d'ordre des balises (réimplémenté indépendamment 3 fois) | `core/validation.py` (`evaluer_ordre`, `statut_balise`, `resultat_parcours`) | Source unique ; équivalence vérifiée par un test à 5000 cas aléatoires comparant ancien/nouveau comportement |
| `AppParcours._parser_tsv` / `_parser_lot_tsv` / `_parser_csv_intelligent` / `_parser_lot_csv` / `_parser_ocad_xml` / `_parser_ocad_txt` (méthodes statiques appelées directement par `main.py` via `AppParcours._parser_xxx(...)`) | `io_/parcours_parsers.py` (fonctions libres `parser_xxx`) | Supprime le couplage anormal main.py ↔ classe UI de parcours |
| `parse_candidate_csv` (fonction dans `ui_lecture_puce.py`) | `io_/candidats_csv.py` | Fonction pure, sans dépendance Tkinter |
| Export CSV dupliqué (`_count_max_punches`/`_build_csv_rows` dans `AppLecturePuce`, ré-écrit dans `main.py._exporter_tous`) | `io_/export_csv.py` (`count_max_punches`, `build_csv_rows`, `write_csv`) | Source unique |

### Ce qui n'a pas changé

- `sireader2.py`, `check_punches.py`, `si_read_card.py` : aucun lien avec les fichiers refactorisés, jamais touchés.
- Le comportement de l'application (algorithmes, UI, formats de fichiers) est strictement identique à la v1.0.1.

### Documentation et qualité

- Toutes les classes et méthodes du code refactorisé (`core/`, `io_/`, `ui/`, `main.py`) ont une docstring expliquant leur rôle.
- Passe `pyflakes` sur tout le code : aucun avertissement (imports/variables inutilisés nettoyés).
- Un bug préexistant (avant refactorisation, présent depuis la v1.0.1) a été corrigé : les messages d'erreur de connexion à la station plantaient silencieusement (`NameError`) au lieu de s'afficher, à cause d'une variable d'exception Python supprimée avant l'exécution d'un callback Tkinter différé.

### Suite possible (non prioritaire)

- `ui/hub.py` (~835 lignes) reste le plus gros fichier : construction de widgets et logique de routage encore mélangées à l'intérieur des méthodes de routage elles-mêmes (au-delà de ce qu'un découpage mécanique par méthode permet).
- Aucun test n'a été fait avec une station SportIdent physique — tout a été vérifié par compilation, tests automatisés et simulation.

---

## ui_parcours.py

### Fonctionnalités

- Grille de sélection des 226 balises possibles (31 à 256) avec boutons toggle
- Sélection par drag : maintenir le clic et glisser pour sélectionner ou désélectionner plusieurs balises d'un coup
- Presets rapides : "10 balises", "24 balises", "26 balises" pour pré-sélectionner un lot standard ; le preset actif est mis en évidence
- Bouton "Tout effacer" pour réinitialiser la sélection
- Compteur de balises sélectionnées (avec limite affichée si un preset est actif)
- Champ de saisie du nom du parcours
- Case "Ordre obligatoire" : active la contrainte d'ordre et fait apparaître une zone de prévisualisation horizontale scrollable montrant la séquence des balises dans l'ordre de sélection
- En mode "Ordre obligatoire", les boutons de la grille affichent le numéro de position à la place du numéro de balise
- Grille responsive : le nombre de colonnes s'adapte automatiquement à la largeur de la fenêtre (plein écran inclus), les boutons s'étirent pour occuper toute la largeur
- Barre d'actions en bas : Ouvrir, Importer CSV, OCAD, Enregistrer TSV, Enregistrer CSV, Lancer la lecture
- Enregistrement en `.tsv` (un parcours ou un lot multi-parcours)
- Enregistrement en `.csv` (un parcours ou un lot multi-parcours)
- Ouverture d'un `.tsv` : charge un parcours simple dans l'éditeur ou un lot multi-parcours dans la listbox de lot
- Import CSV intelligent : détecte le séparateur, extrait un nom de parcours et toutes les valeurs numériques valides ; dialogue de confirmation avec aperçu avant import
- Import OCAD (`.xml`) : support IOF XML v2.0.3 (sans namespace, `<CourseName>` + `<ControlCode>`) et v3.0 (avec namespace, `<Name>` + `<Id>`) ; détection automatique de la version
- Import OCAD (`.txt`) : support du format "Export Courses Text" OCAD (colonnes tabulées, séquence `S1-31-42-...-F1`)
- Fallback OCAD : si le fichier XML ne contient pas de parcours définis mais uniquement la liste des balises du terrain, propose de les importer comme sélection de départ
- Lot de parcours : ajout / retrait de parcours dans une listbox, enregistrement du lot en TSV ou CSV, chargement d'un lot existant
- Bouton **▶ Lancer la lecture** (affiché uniquement si lancé depuis l'application principale) : démarre la lecture avec le parcours courant ou tout le lot

### Corrections

| Problème | Cause | Solution |
|---|---|---|
| Le bouton "Lancer la lecture" restait flottant même après fermeture de l'onglet | Le widget était créé sans parent (`barre` manquant), ce qui le rattachait à la fenêtre racine | Ajout du parent manquant |
| Fichier gonflé à 2497 lignes | Une ligne vide insérée après quasiment chaque instruction | Nettoyage automatisé ; contenu vérifié identique ligne par ligne → fichier réduit à 1593 lignes |

---

## ui_lecture_puce.py

### Fonctionnalités

- Connexion automatique à la station SportIdent au démarrage (mode autonome uniquement)
- Affichage du statut de connexion en haut de la fenêtre (mode autonome)
- Bouton "Attendre une puce" pour lancer la lecture en continu
- Dialogue obligatoire de saisie du nom du participant après chaque lecture
- Chaque puce lue crée un panneau avec : nom, numéro, date de lecture, balises pointées, temps (check/clear/départ/arrivée), liste des pointages
- Sidebar verticale scrollable avec un bouton par puce lue (nom du participant), masquée automatiquement quand le panneau de lecture global est affiché
- Gestion des doublons : si une même puce est lue deux fois, on propose de remplacer ou d'afficher l'ancienne
- Bouton "Annuler la lecture" (visible uniquement pendant l'attente d'une puce)
- Bouton "Reconnecter" (visible uniquement en cas de perte de connexion, mode autonome)
- Clic droit sur un nom dans la sidebar → renommer la puce sans la relire
- Bouton "Exporter en CSV" (visible dès qu'une puce est lue) → sauvegarde un fichier avec tous les participants et leurs pointages
- Bouton "Effacer toutes les puces" pour remettre l'application à zéro sans la redémarrer
- Fermeture propre de l'application : le port série est libéré correctement
- Déduplication des balises dans la liste des pointages : si une même balise est enregistrée plusieurs fois sur la puce, seule la dernière heure de passage est affichée
- Connexion partagée entre onglets : un seul onglet lit à la fois, les autres attendent leur tour (évite les conflits sur le port série)
- Diffusion automatique d'une puce lue sur un onglet vers tous les autres onglets ouverts sur le même parcours
- Bouton "Charger liste candidats (CSV)" : importe un fichier CSV avec numéro de puce, prénom, nom, catégorie, infos/groupe
- Détection automatique de l'encodage du CSV (`utf-8-sig`, `latin-1`, `cp1252`) et du séparateur
- Attribution automatique du nom du participant dès la lecture de la puce si elle figure dans la liste chargée (sans dialogue de saisie)
- Affichage de la catégorie et du groupe dans la fiche puce si le candidat est pré-chargé
- Si le parcours est défini, affichage d'un bandeau bleu avec le nom du parcours et le nombre de balises dans l'onglet de lecture
- **Mode Libre / Contrôlée** : en mode contrôlée, chaque puce lue ouvre une fenêtre de validation (numéro, nom, parcours de destination modifiable, liste des balises) avant tout enregistrement
- **Affichage décroissant des passages** : le passage le plus récent s'affiche toujours en haut, le plus ancien en bas ; le scroll remonte automatiquement à chaque nouvelle lecture
- **Marge d'erreur (N+2)** : seuls les N+2 derniers pointages terrain sont analysés (N = nombre de balises du parcours) ; le parcours est validé si au moins N d'entre eux sont corrects, autorisant ainsi 2 erreurs de pointage
- **Bandeau résultat agrandi** : le message "Parcours réussi" / "Parcours échoué" s'affiche en police taille 14, centré et sur toute la largeur pour une lecture immédiate
- **Galerie scindée (parcours sans ordre)** : le cadre "Reconstitution du personnage" est divisé 50/50 — images en galerie horizontale à gauche, grand ✓ vert ou ✗ rouge à droite indiquant le résultat global du parcours
- **Indicateur "Dernière balise"** : sous la dernière image de la galerie, un texte en gras signale la balise finale pointée
- **Conservation du nom entre parcours** : quand une même puce est relue sur un parcours différent, le nom déjà saisi est réutilisé automatiquement sans redemander

### Modifications UI/UX

- **Suppression du bloc info puce** : le cadre affichant le type et le numéro de la puce a été retiré — seul le nom du participant est conservé
- **Réduction des polices** : nom du parcours 14→11, label "Temps:" 11→9, durée 16→13, bandeau résultat 14→11
- **Suppression du 50/50 pour les parcours sans ordre** : le ✓/✗ agrandi n'est plus affiché ; la galerie occupe toute la largeur
- **Limite d'affichage à 10 balises** : seules les 10 dernières balises pointées sont affichées dans le tableau
- **Redimensionnement des images** : 150×120 → 90×75 px pour que 10 images tiennent dans la largeur du bloc galerie
- **Message de connexion simplifié** : `_set_status` n'affiche plus que `"Connecté sur le port X"` — tous les messages opérationnels intermédiaires ont été supprimés

### Corrections

| Problème | Cause | Solution |
|---|---|---|
| Crash systématique (`UnboundLocalError: res_txt`) à la lecture d'une puce sur un parcours sans ordre obligatoire | Le texte de résumé du passage n'était jamais défini dans cette branche du code | Texte ajouté pour les deux cas (réussi / incomplet) |
| Coupures de connexion confuses, reconnexions automatiques silencieuses | Jusqu'à 3 tentatives de reconnexion en arrière-plan avec pauses de 2s, sans retour clair | Arrêt immédiat et explicite ; le bouton "Attendre une puce" passe en rouge **"Relancer"** |
| Dépendance à `helpers.py` | `parse_candidate_csv` importée d'un fichier externe peu utilisé | Fonction déplacée directement ici ; `helpers.py` supprimable |
| Le label "candidats chargés" ne se mettait pas à jour | Seule la diffusion vers les autres onglets mettait à jour le label, pas le chargement local | Mise à jour immédiate ajoutée |
| `AttributeError` en mode hub lors d'une erreur de connexion | `btn_reconnecter` n'existe qu'en mode autonome ; des appels y accédaient sans vérifier son existence | Appels sécurisés via une méthode dédiée (`_pack_reconnecter`) |
| `TclError: invalid command name` au changement de parcours | `_set_active_btn` tentait de reconfigurer un widget sidebar appartenant à une autre app (détruite) | Appels `.config()` protégés par `try/except` |
| Bouton "Connexion..." bloqué indéfiniment sans reader | `SIReaderReadout()` tentait d'ouvrir chaque port Bluetooth (2s/port) sans possibilité d'annuler | Pré-vérification instantanée via `list_ports.comports()` + bouton "Annuler" affiché dès le début de la tentative |

---

## main.py

### Fonctionnalités

- **Hub de lecture unique** (un seul onglet "Lecture en cours") regroupant tous les parcours ouverts : navigation à gauche (listbox des parcours, badge du nombre de puces lues par parcours) et zone de contenu à droite
- Bouton **▶ Lecture** en haut de la navigation : affiche un panneau de lecture global, indépendant des parcours individuels, avec son propre "Mode : Libre/Contrôlée", "Charger liste candidats (CSV)", "Attendre une puce", "Annuler la lecture", "Exporter tous les parcours (CSV)" et "Effacer toutes les puces"
- Un seul clic sur "Attendre une puce" du panneau global suffit pour tous les parcours ouverts simultanément : une seule connexion physique au lecteur SI écoute, puis chaque puce lue est automatiquement routée vers le parcours dont les balises correspondent le mieux (score d'intersection)
- En mode libre, si aucun parcours ne correspond aux balises pointées, la puce est automatiquement assignée au premier parcours ouvert plutôt que rejetée
- En **mode contrôlée**, fenêtre de validation par puce avec :
  - menu déroulant de tous les parcours ouverts (pré-sélection automatique par score)
  - liste colorée des balises pointées : vert = correcte/bien placée, orange = mal placée dans l'ordre, rouge = hors parcours
  - boutons Valider / Annuler
  - fenêtre infermable par la croix ou Échap, pour éviter les validations accidentelles
- **Mode contrôlée renforcé** : la fenêtre de validation s'ouvre à **chaque** lecture, même pour une puce déjà enregistrée, permettant de placer la même puce dans plusieurs parcours différents
- **Mode libre dynamique** : le meilleur parcours est recalculé à chaque lecture par score d'intersection ; la puce n'est plus verrouillée sur son affectation précédente
- Bouton **✎ Modifier les parcours** : ouvre l'éditeur pré-rempli avec tous les parcours actuellement ouverts, pour les modifier/compléter puis relancer la lecture ; une alerte propose d'exporter les puces déjà lues avant de poursuivre
- Bouton **✕ Fermer ce parcours** avec confirmation d'export CSV si des puces ont été lues sur ce parcours
- Fermeture groupée de tous les parcours (fermeture de l'onglet du hub) avec confirmation d'export CSV global
- Déplacement manuel d'une puce d'un parcours vers un autre via une boîte de dialogue dédiée
- Export CSV unique regroupant tous les parcours du hub, avec en-têtes harmonisés sur le nombre maximal de balises parmi tous les parcours

### Modifications UI/UX

- **Bouton "Menu"** : le bouton de navigation gauche s'appelle désormais "Menu" (anciennement "Lecture")
- **Liste candidats persistante** : la liste chargée reste active même après modification des parcours (`_hub_candidats` stocké au niveau `MainApp`, appliqué à chaque nouvel onglet)
- **Messages de connexion épurés** : `_hub_lbl_status` n'affiche plus que `"Connecté sur le port X"` — les messages intermédiaires ("Posez la puce...", "Puce enregistrée...", etc.) ont été supprimés
- **Gestion du reader absent** : clic sur "Attendre une puce" sans reader → bouton gris "Connexion..." + bouton "Annuler" immédiat ; si la connexion échoue → bouton rouge "Relancer" ; `_hub_reset_btn_lecture` force l'état "Relancer" si le bouton était en "Connexion..." lors de l'arrêt

### Corrections

| Problème | Cause | Solution |
|---|---|---|
| Rectangle noir résiduel en bas de l'écran | Sidebar interne de chaque parcours qui s'accumulait visuellement avec la navigation du hub | Sidebar masquée/affichée proprement selon le contexte |
| Accumulation de hauteurs résiduelles lors des changements d'affichage | Utilisation de `pack`/`pack_forget` pour switcher entre parcours | Remplacé par `place` |
| Le panneau "Lecture" affichait le contenu d'un parcours au hasard | Pas de panneau dédié — réutilisation du `tab_lecture` d'une app quelconque | Panneau global construit indépendamment de toute `AppLecturePuce` |
| Atterrissage sur le dernier parcours au lieu du panneau "Lecture" après un chargement | Pas de redirection explicite après l'ouverture des parcours | Redirection systématique vers le panneau global, même avec un lot de 48 parcours |
| `AttributeError: 'MainApp' object has no attribute 'after'` | `MainApp` n'est pas un widget Tk | Remplacé par `self.root.after(...)` |
| **"No SI reader found"** persistant après création d'un seul parcours | Connexion automatique immédiate à la création (hors du panneau global) ; échec si la station n'était pas encore prête | Tous les parcours (seul ou lot) sont désormais ouverts en mode partagé, géré uniquement par le panneau global |
| **Port série verrouillé** après fermeture de tous les parcours | `self.si.disconnect()` programmé en différé (`after(100, ...)`) mais l'onglet détruit immédiatement après, empêchant son exécution | Déconnexion rendue synchrone et immédiate avant toute destruction de widget |
| Puce affichée comme "enregistrée" alors que le nom avait été annulé | Pas de vérification après l'appel d'enregistrement | Vérification systématique de la présence réelle de la puce avant de naviguer ou d'afficher un message de succès |
| Code mort | `_charger_tsv_multi_parcours` dupliquée et jamais appelée | Supprimée avec le nettoyage de `helpers.py` |

---

## Système d'images balises

### Présentation

Fonctionnalité ajoutée sur la branche `si_image`. Permet d'associer des images aux balises d'un parcours et de les afficher sous forme de galerie après la lecture d'une puce.

### Utilisation

1. Dans le panneau de lecture du hub, cliquer sur **"Charger images balises (dossier)"**
2. Choisir un dossier contenant des images nommées par numéro de balise (ex. `31.jpg`, `42.png`, `54.jpeg`)
3. Les images sont automatiquement associées : `31.jpg` → balise 31, `42.png` → balise 42, etc.
4. Après chaque lecture de puce, les balises pointées qui ont une image associée s'affichent en galerie horizontale scrollable en bas du panneau de résultat

### Comportement

- **Formats supportés** : `.png`, `.gif`, `.jpg`, `.jpeg`, `.bmp`, `.webp`
- **Nommage** : seul le nom sans extension doit être un entier (le numéro de balise) — les autres fichiers du dossier sont ignorés
- **Chargement d'images** : si Pillow (`PIL`) est installé, tous les formats sont supportés avec redimensionnement de qualité ; sinon, repli sur `tk.PhotoImage` natif (PNG et GIF uniquement)
- **Galerie** : affichée dans l'ordre des pointages de la puce, scrollable horizontalement, taille unitaire 150 × 120 px
- **Partage** : le dictionnaire d'images est partagé entre tous les parcours ouverts au moment du chargement, et propagé aux nouveaux parcours ouverts ensuite via `_appliquer_images`

### Fichiers modifiés

| Fichier | Modification |
|---|---|
| `main.py` *(→ `ui/app_main.py` depuis la refactorisation)* | Attribut `_images_balises`, bouton "Charger images balises", méthode `_hub_charger_images`, propagation aux apps via `_appliquer_images` |
| `ui_lecture_puce.py` *(→ `ui/lecture_puce.py` depuis la refactorisation)* | Paramètre `images_balises` dans `__init__`, méthode `_appliquer_images`, méthode `_charger_photo` (PIL + fallback natif), galerie horizontale dans `_build_passage_section` |

### Structure du dossier images (exemple)

```
images/Animaux/
├── 31.jpg      ← morceau balise 31
├── 32.jpg      ← morceau balise 32
│   ...
└── 54.jpg      ← morceau balise 54
```