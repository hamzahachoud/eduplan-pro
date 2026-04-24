# 🔗 Guide Spécialisé : La Liaison (Comment tout communique)

Ce document explique le voyage d'une donnée du clic de l'utilisateur jusqu'à la base de données. C'est la partie la plus "tech" qui lie le Front et le Back.

## 1. Le voyage d'un clic (Requête HTTP)
Imaginez qu'un admin ajoute une salle :
1.  **Front-End** : L'admin remplit le champ "Nom de la salle" et clique sur "Enregistrer".
2.  **Requête (POST)** : Le navigateur envoie un paquet de données à l'adresse `/admin/salles`.
3.  **Back-End (Route)** : Flask intercepte ce paquet via `request.form`.
4.  **Base de Données** : Flask crée un objet `Salle`, l'ajoute à la session et fait `commit()`.
5.  **Réponse (Redirect)** : Flask renvoie une instruction "Maintenant, recharge la page des salles pour montrer la nouvelle !".

## 2. Jinja2 : Le pont entre Python et HTML
C'est le langage qui permet de mettre du Python dans le HTML.
*   **Les Variables `{{ variable }}`** : Sert à afficher une info.
    *   *Exemple* : `{{ current_user.email }}` affiche l'adresse de la personne connectée.
*   **Les Boucles `{% for ... %}`** : Sert à créer des listes répétitives.
    *   *Exemple* : Pour afficher le planning, on fait une boucle `for seance in seances`. Pour chaque séance trouvée par le Back, le Front crée une nouvelle ligne dans le tableau.

## 3. Les Méthodes : GET vs POST
C'est capital de savoir faire la différence :
*   **GET** : L'utilisateur **demande** à voir quelque chose (ex: cliquer sur un lien pour voir son planning). C'est passif.
*   **POST** : L'utilisateur **envoie** quelque chose (ex: taper un mot de passe, ajouter un étudiant). C'est actif.

## 4. `url_for` : Le GPS interne
Plutôt que d'écrire des liens en dur comme `/admin/delete/5`, on utilise `{{ url_for('admin.delete_module', id=5) }}`.
*   **Avantage** : Si demain on décide de changer l'adresse de la page, on n'a pas besoin de modifier tous nos fichiers HTML. Flask s'occupe de trouver le bon chemin tout seul.

## 5. Les Messages Flash
C'est une communication "serveur vers utilisateur".
*   Le Back-End dit : `flash('Succès !')`.
*   Le Front-End (dans `base.html`) a un bloc spécial qui vérifie si un message existe et l'affiche dans une jolie boîte Bootstrap.

## 6. Questions possibles pour vous
*   **Q : "Comment le serveur sait-il que c'est moi qui suis connecté d'une page à l'autre ?"**
    *   R : "Grâce aux **Cookies de Session**. Flask envoie un petit fichier texte au navigateur qui contient un identifiant unique. À chaque nouvelle page demandée, le navigateur renvoie cet identifiant."
*   **Q : "Que se passe-t-il si je tape une URL qui n'existe pas ?"**
    *   R : "Flask renvoie par défaut une erreur 404. On peut personnaliser cette page pour qu'elle reste dans le design de notre site."
*   **Q : "Pourquoi mettre des formulaires dans des 'Modals' (fenêtres surgissantes) ?"**
    *   R : "C'est un choix d'expérience utilisateur (UX). Cela permet de rester sur la même page sans perdre le contexte visuel, ce qui est plus confortable pour l'administrateur."
