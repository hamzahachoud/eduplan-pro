# ⚙️ Guide Spécialisé : Back-End (La Logique)

Ce document est destiné à la personne qui présentera le serveur, la base de données et les calculs.

## 1. Flask : Le Chef d'Orchestre
Flask est le serveur. Son travail est de rester à l'écoute.
*   **Les Routes** : Ce sont les "adresses" du site.
    *   `@admin_bp.route('/login')` -> Si l'utilisateur demande cette adresse, Flask lance la fonction `login()`.
*   **Blueprints** : Nous avons découpé le projet en "quartiers" : `admin`, `student`, `teacher`. Ça rend le code plus propre et organisé.

## 2. SQLAlchemy : Le traducteur de Base de Données
Nous ne parlons pas directement SQL (langage de base de données complexe). Nous utilisons un **ORM (SQLAlchemy)**.
*   **Le concept** : Chaque "Table" de la base de données est représentée par une **Classe Python** dans `models.py`.
    *   Exemple : Pour ajouter un professeur, on crée un objet `Enseignant(nom="Nom", prenom="Prenom")` et on demande à SQLAlchemy de l'enregistrer avec `db.session.commit()`.
*   **Les Relations (Clés étrangères)** : C'est le point le plus important.
    *   Une **Séance** est reliée à un **Module** par l'ID du module. SQLAlchemy nous permet d'écrire `seance.module.libelle` pour obtenir directement le nom de la matière. C'est magique !

## 3. La Logique de Sécurité (Authentification)
Nous utilisons **Flask-Login**.
*   **Protection** : Le décorateur `@login_required` avant une fonction empêche quelqu'un de voir la page s'il n'est pas connecté.
*   **Rôles** : Après la connexion, nous vérifions `current_user.role`.
    *   Si c'est un 'admin', il va au Dashboard.
    *   Si c'est un 'teacher', il va à son planning personnel.

## 4. Les calculs d'heures (Le point fort)
Le professeur va sûrement vous demander comment les heures sont gérées.
*   **Maquette** : Le `Module` définit le quota (ex: 20h).
*   **Affectation** : On dit quel prof fait quel volume (ex: M. X fait 10h de ce module).
*   **Réel** : On compte les `Seance` dans la base de données.
*   **Calcul** : Dans `teacher/routes.py`, nous faisons la somme des durées de toutes les séances d'un prof pour voir s'il a fini son travail ou s'il est en heures sup.

## 5. Algorithme de Génération de Planning
Nous avons une route qui permet de générer des séances automatiquement.
*   Elle regarde chaque module de la formation.
*   Elle crée des séances de CM, puis de TD, puis de TP.
*   Elle cherche une salle disponible du bon type (Amphi pour CM, Salle TP pour TP).

## 6. Questions possibles pour vous
*   **Q : "C'est quoi `db.session.commit()` ?"**
    *   R : "C'est la validation finale. SQLAlchemy prépare les changements dans une 'session'. Le `commit` écrit définitivement ces changements dans le fichier de base de données `app.db`."
*   **Q : "Comment gérez-vous le hachage des mots de passe ?"**
    *   R : "Nous n'enregistrons jamais les mots de passe 'en clair'. Nous utilisons `generate_password_hash`. Même si on vole la base de données, personne ne peut lire les mots de passe."
*   **Q : "Pourquoi utiliser SQLite ?"**
    *   R : "Pour la simplicité. C'est un moteur de base de données qui ne nécessite aucune installation de serveur externe. Tout est stocké dans un fichier local."
