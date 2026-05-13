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