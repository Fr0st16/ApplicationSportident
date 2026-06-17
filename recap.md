# ui_lecture_puce.py :

- Connexion automatique à la station SportIdent au démarrage
- Affichage du statut de connexion en haut de la fenêtre
- Bouton "Attendre une puce" pour lancer la lecture en continu
- Dialogue obligatoire de saisie du nom du participant après chaque lecture
- Chaque puce lue crée un panneau avec : nom, numéro, date de lecture, balises pointées, temps (check/clear/départ/arrivée), liste des pointages
- Sidebar verticale scrollable avec un bouton par puce lue (nom du participant)
- Contour blanc sur le bouton actif dans la sidebar pour savoir où on se trouve
- Gestion des doublons : si une même puce est lue deux fois, on propose de remplacer ou d'afficher l'ancienne
- Bouton "Annuler la lecture" (visible uniquement pendant l'attente d'une puce)
- Bouton "Reconnecter" (visible uniquement en cas de perte de connexion)
- Clic droit sur un nom dans la sidebar → renommer la puce sans la relire
- Bouton "Exporter en CSV" (visible dès qu'une puce est lue) → sauvegarde un fichier avec tous les participants et leurs pointages
- Bouton "Effacer toutes les puces" pour remettre l'application à zéro sans la redémarrer
- Fermeture propre de l'application : le port série est libéré correctement
- Déduplication des balises dans la liste des pointages : si une même balise est enregistrée plusieurs fois sur la puce, seule la dernière heure de passage est affichée
- Connexion partagée entre onglets : un seul onglet lit à la fois, les autres attendent leur tour (évite les conflits sur le port série)
- Diffusion automatique d'une puce lue sur un onglet vers tous les autres onglets ouverts sur le même parcours
- Bouton "Charger liste candidats (CSV)" : importe un fichier CSV avec numéro de puce, prénom, nom, catégorie, infos/groupe
- Détection automatique de l'encodage du CSV (utf-8-sig, latin-1, cp1252) et du séparateur
- Attribution automatique du nom du participant dès la lecture de la puce si elle figure dans la liste chargée (sans dialogue de saisie)
- Affichage de la catégorie et du groupe dans la fiche puce si le candidat est pré-chargé
- Si le parcours est défini, affichage d'un bandeau bleu avec le nom du parcours et le nombre de balises dans l'onglet de lecture

# ui_parcours.py :

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
- Enregistrement en .tsv (un parcours ou un lot multi-parcours)
- Enregistrement en .csv (un parcours ou un lot multi-parcours)
- Ouverture d'un .tsv : charge un parcours simple dans l'éditeur ou un lot multi-parcours dans la listbox de lot
- Import CSV intelligent : détecte le séparateur, extrait un nom de parcours et toutes les valeurs numériques valides ; dialogue de confirmation avec aperçu avant import
- Import OCAD (.xml) : support IOF XML v2.0.3 (sans namespace, `<CourseName>` + `<ControlCode>`) et v3.0 (avec namespace, `<Name>` + `<Id>`) ; détection automatique de la version
- Import OCAD (.txt) : support du format "Export Courses Text" OCAD (colonnes tabulées, séquence `S1-31-42-...-F1`)
- Fallback OCAD : si le fichier XML ne contient pas de parcours définis mais uniquement la liste des balises du terrain, propose de les importer comme sélection de départ
- Lot de parcours : ajout / retrait de parcours dans une listbox, enregistrement du lot en TSV ou CSV, chargement d'un lot existant
- Bouton "▶ Lancer la lecture" (affiché uniquement si lancé depuis l'application principale) : démarre la lecture avec le parcours courant ou tout le lot