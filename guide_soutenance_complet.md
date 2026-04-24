# 🚀 Guide de Soutenance Ultime : EduPlan Pro

Ce guide est destiné à deux étudiants qui présentent le projet **EduPlan Pro** à un professeur. Il explique tout depuis zéro, avec pédagogie et précision.

---

## 1. Présentation Générale du Projet

### À quoi sert le site ?
**EduPlan Pro** est une application de gestion d'emploi du temps universitaire. Imaginez le casse-tête : des centaines d'étudiants, des dizaines de professeurs, des salles de cours limitées et des quotas d'heures à respecter (la "maquette"). Notre site automatise et simplifie tout cela.

### Le besoin auquel il répond
1. **Éviter les erreurs** : Ne pas mettre deux cours dans la même salle au même moment.
2. **Respecter la pédagogie** : S'assurer qu'un module (ex: Mathématiques) a bien ses 20h de cours prévues.
3. **Visibilité** : Offrir aux étudiants et professeurs une vue claire et personnalisée de leur semaine.

### Les utilisateurs (Les "Rôles")
*   **L'Administrateur** : Le chef d'orchestre. Il crée les formations, ajoute les profs, définit les matières et génère le planning.
*   **L'Enseignant** : Il se connecte pour voir son planning personnel, ses heures effectuées et ses heures supplémentaires.
*   **L'Étudiant** : Il choisit son groupe (ex: TD1, TP2A) et voit l'emploi du temps qui ne concerne que lui.

---

## 2. Séparation des Rôles pour la Présentation

Pour une présentation fluide, voici comment vous répartir la parole :

### 👤 Personne 1 : Le "Front-End" (L'Interface et le Design)
*   **Son rôle** : Présenter tout ce que l'utilisateur touche et voit.
*   **Ce qu'elle doit dire** : "Mon rôle a été de concevoir une interface moderne et intuitive en utilisant le style 'Glassmorphism' (aspect verre fumé). J'ai veillé à ce que l'expérience utilisateur soit fluide sur toutes les pages."
*   **Notions à maîtriser** : HTML (la structure), CSS (le look), Bootstrap (la rapidité de mise en page).
*   **Fichiers à expliquer** : `base.html`, `style.css`, les dossiers de templates.
*   **Question type du prof** : "Comment avez-vous fait pour que la barre de navigation change selon qu'on est admin ou prof ?"
*   **Réponse** : "Grâce à Jinja2, nous utilisons des conditions `{% if current_user.role == 'admin' %}` directement dans le code HTML pour afficher ou cacher des boutons."

### 👤 Personne 2 : Le "Back-End" (La Logique et les Données)
*   **Son rôle** : Expliquer comment le "moteur" sous le capot fonctionne.
*   **Ce qu'elle doit dire** : "J'ai géré la logique du serveur avec Flask. Mon travail était de faire en sorte que lorsqu'un administrateur clique sur 'Générer', les données soient enregistrées dans la base de données et que les calculs d'heures soient exacts."
*   **Notions à maîtriser** : Python, les Routes, SQLAlchemy (Base de données), les Relations entre les tables.
*   **Fichiers à expliquer** : `routes.py`, `models.py`, `run.py`.
*   **Question type du prof** : "Où sont stockées les informations des professeurs ?"
*   **Réponse** : "Dans une table SQLite nommée 'enseignants'. Nous utilisons SQLAlchemy pour manipuler ces données comme des objets Python, ce qui est plus sécurisé et plus simple."

---

## 3. Le Web Expliqué aux Débutants (Le Socle)

Si le prof vous demande comment ça marche globalement, voici l'explication :
1.  **Le Navigateur (Le Client)** : C'est Chrome ou Firefox. C'est l'outil qui demande à voir une page.
2.  **La Requête** : Quand vous cliquez sur un bouton, le navigateur envoie un message ("Je veux voir la page /admin").
3.  **Le Serveur (Flask)** : C'est un programme qui tourne sur l'ordinateur. Il reçoit la requête, cherche les infos dans la base de données, et prépare le "cadeau" de retour.
4.  **La Réponse** : Le serveur renvoie du code HTML/CSS au navigateur, qui l'affiche joliment.

### Les langages :
*   **HTML** : Le squelette (ici il y a un titre, ici il y a un bouton).
*   **CSS** : Le maquillage (le bouton est bleu, le fond est flou).
*   **Python (Flask)** : Le cerveau (si le mot de passe est bon, laisse-le entrer).

---

## 4. Dossier Flask : Le Moteur de votre projet

Flask est ce qu'on appelle un **Framework**. C'est une boîte à outils qui évite de tout réinventer. 

### Les grandes fonctions Flask à connaître :
*   `render_template('page.html', data=...)` : Sert à dire "Prends ce fichier HTML, remplis-le avec ces données, et envoie-le à l'utilisateur".
*   `request.form.get('nom')` : Sert à récupérer ce que l'utilisateur a tapé dans un formulaire.
*   `redirect(url_for('destination'))` : Sert à envoyer l'utilisateur vers une autre page (ex: après une connexion réussie).
*   `flash('Message')` : Sert à afficher une petite alerte en haut de l'écran (ex: "Affectation réussie !").

---

## 5. La Base de Données (SQLite & SQLAlchemy)

C'est là que tout est enregistré pour ne pas disparaître quand on éteint l'ordinateur.

### Pourquoi SQLite ?
C'est une base de données "légère". Toutes les informations tiennent dans un seul fichier (`app.db`). C'est parfait pour un projet étudiant car on n'a pas besoin d'installer de gros serveurs complexes.

### Pourquoi SQLAlchemy ?
D'habitude, pour parler à une base de données, on utilise le langage "SQL". Avec SQLAlchemy, on reste en Python. On crée des **Classes** (des modèles).
*   Une **Table** = Une feuille Excel (ex: la feuille "Salles").
*   Une **Colonne** = Une catégorie d'info (ex: le nom de la salle).
*   Une **Ligne** = Une salle précise (ex: Salle 101).

---

## 6. Fichier par Fichier : La lecture détaillée

### 📁 `run.py`
C'est le point de départ. Quand on le lance, il crée les tables (si elles n'existent pas) et démarre le serveur.
**Ligne clé** : `app.run(debug=True)` -> Démarre le site et nous montre les erreurs s'il y en a.

### 📁 `app/models.py`
C'est le plan de construction de la base de données.
*   `User` : Stocke l'email, le mot de passe (haché pour la sécurité) et le rôle (admin/prof/étudiant).
*   `Module` : Stocke le nom de la matière et ses heures (CM, TD, TP).
*   `Seance` : C'est une case du planning (Date, Heure, Salle, Prof).

### 📁 `app/admin/routes.py`
Contient les instructions pour l'admin.
*   `@admin_bp.route('/login')` : La fonction qui vérifie l'identité au login.
*   `@admin_bp.route('/planning')` : La page où l'admin voit tout.

---

## 7. Préparation à la Soutenance (FAQ)

**Q: Comment est calculée l'heure de fin d'un cours ?**
R: "C'est une logique Python dans `models.py`. On prend l'heure de début, on lui ajoute la durée (ex: 1.5 pour 1h30), et SQLAlchemy fait le calcul."

**Q: Pourquoi les professeurs ne voient-ils que leur planning ?**
R: "Dans la route `/teacher/planning`, nous utilisons `current_user.enseignant_id` pour filtrer les séances. On ne demande que celles qui appartiennent à l'utilisateur connecté."

**Q: Et si demain vous avez 10 000 utilisateurs ?**
R: "Il suffirait de changer une seule ligne dans `config.py` pour passer de SQLite à une base de données plus robuste comme PostgreSQL."

---

## 8. Comment modifier le projet en direct (Pour épater le prof)

Si le prof vous dit : **"Ajoutez un champ pour la capacité des salles"**.
1.  **Étape 1 (Données)** : Allez dans `models.py`, dans la classe `Salle`, ajoutez `capacite = db.Column(db.Integer)`.
2.  **Étape 2 (Serveur)** : Allez dans `routes.py`, modifiez la fonction de création pour récupérer cette info du formulaire.
3.  **Étape 3 (Interface)** : Allez dans `salles.html`, ajoutez un `<input name="capacite">`.

---

## 💡 Conseils pour l'oral :
1.  **Montrez l'application** : Ne restez pas sur le code. Montrez comment vous créez un module, comment vous l'affectez, et comment il apparaît côté prof.
2.  **Restez calmement techniques** : Si vous ne savez pas, dites "C'est une fonctionnalité gérée par Flask-Login pour la sécurité, nous avons suivi la documentation officielle".
3.  **Parlez de l'expérience utilisateur** : Le prof adore entendre parler de "design", "ergonomie" et "clarté".

Bonne chance à tous les deux ! Vous avez un projet solide entre les mains.
