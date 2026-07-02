# Gestionnaire de course SportIdent — Journal des modifications

## Table des matières

- [ui_parcours.py](#ui_parcourspy)
- [ui_lecture_puce.py](#ui_lecture_pucepy)
- [main.py](#mainpy)
- [Système d'images balises](#système-dimages-balises)

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

### Corrections

| Problème | Cause | Solution |
|---|---|---|
| Crash systématique (`UnboundLocalError: res_txt`) à la lecture d'une puce sur un parcours sans ordre obligatoire | Le texte de résumé du passage n'était jamais défini dans cette branche du code | Texte ajouté pour les deux cas (réussi / incomplet) |
| Coupures de connexion confuses, reconnexions automatiques silencieuses | Jusqu'à 3 tentatives de reconnexion en arrière-plan avec pauses de 2s, sans retour clair | Arrêt immédiat et explicite ; le bouton "Attendre une puce" passe en rouge **"Relancer"** |
| Dépendance à `helpers.py` | `parse_candidate_csv` importée d'un fichier externe peu utilisé | Fonction déplacée directement ici ; `helpers.py` supprimable |
| Le label "candidats chargés" ne se mettait pas à jour | Seule la diffusion vers les autres onglets mettait à jour le label, pas le chargement local | Mise à jour immédiate ajoutée |
| `AttributeError` en mode hub lors d'une erreur de connexion | `btn_reconnecter` n'existe qu'en mode autonome ; des appels y accédaient sans vérifier son existence | Appels sécurisés via une méthode dédiée (`_pack_reconnecter`) |
| `TclError: invalid command name` au changement de parcours | `_set_active_btn` tentait de reconfigurer un widget sidebar appartenant à une autre app (détruite) | Appels `.config()` protégés par `try/except` |

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
| `main.py` | Attribut `_images_balises`, bouton "Charger images balises", méthode `_hub_charger_images`, propagation aux apps via `_appliquer_images` |
| `ui_lecture_puce.py` | Paramètre `images_balises` dans `__init__`, méthode `_appliquer_images`, méthode `_charger_photo` (PIL + fallback natif), galerie horizontale dans `_build_passage_section` |

### Structure du dossier images (exemple)

```
images/Animaux/
├── 31.jpg      ← morceau balise 31
├── 32.jpg      ← morceau balise 32
│   ...
└── 54.jpg      ← morceau balise 54
```