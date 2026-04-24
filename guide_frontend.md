# 🎨 Guide Spécialisé : Front-End (L'Interface)

Ce document est destiné à la personne qui présentera la partie visuelle et interactive du projet.

## 1. Les 3 Piliers du Front-End
Pour expliquer le Front-End au professeur, utilisez cette métaphore :
*   **HTML (La Structure)** : C'est le squelette. Il dit "Ici il y a un titre", "Là il y a un tableau".
*   **CSS (Le Style)** : C'est l'habillage. Il dit "Le fond est sombre et transparent", "Les boutons ont des coins arrondis".
*   **Jinja2 (Le Dynamisme)** : C'est ce qui rend la page "intelligente". Il permet d'afficher le nom de l'utilisateur connecté ou de créer une liste de cours automatiquement.

## 2. Le Design : Glassmorphism
Nous avons choisi un style moderne appelé **Glassmorphism**.
*   **Aspect** : Effet de verre dépoli, transparence et flou d'arrière-plan.
*   **Pourquoi ?** : Pour donner un aspect "premium" et futuriste à l'application.
*   **Fichier clé** : `app/static/css/style.css`.
    *   *Exemple à montrer* : La classe `.glass-card`. Elle utilise `background: rgba(255, 255, 255, 0.05)` (transparence) et `backdrop-filter: blur(10px)` (le flou).

## 3. La Structure des Templates (Modèle "Héritage")
Nous n'avons pas réécrit la barre de navigation sur chaque page. Nous utilisons l'**Héritage de Templates**.
*   **`base.html`** : C'est le fichier parent. Il contient tout ce qui ne change jamais (le menu, le pied de page, les liens vers Google Fonts).
*   **`{% block content %}`** : C'est un "trou" dans le fichier parent que les autres fichiers (enfants) vont remplir.
*   **Pourquoi ?** : Si on veut changer le logo, on le fait 1 seule fois dans `base.html` et ça change sur tout le site. C'est un gain de temps énorme.

## 4. Les Formulaires : Le point de contact
Chaque bouton "Ajouter" ou "Enregistrer" fait partie d'un `<form>`.
*   **`method="POST"`** : Indique que nous envoyons des données vers le serveur de manière sécurisée.
*   **`{{ form.csrf_token }}`** : Un jeton de sécurité automatique qui empêche les pirates d'envoyer des faux formulaires.
*   **Les Inputs** : Chaque champ a un `name` (ex: `name="cm_heures"`). C'est grâce à ce nom que le Back-End pourra récupérer l'information.

## 5. Bootstrap : Notre allié
Nous utilisons **Bootstrap 5**, une bibliothèque CSS professionnelle.
*   Elle nous donne des composants prêts à l'usage : les boutons (`btn-primary`), les alertes (`alert-success`), et surtout la **Grille** (`row` et `col`).
*   **Grille** : Permet de diviser la page en 12 colonnes. Par exemple, sur le planning prof, le calendrier prend 7 colonnes (`col-lg-7`) et les stats prennent 5 colonnes (`col-lg-5`).

## 6. Questions possibles pour vous
*   **Q : "Comment avez-vous géré les icônes ?"**
    *   R : "Nous utilisons *Font Awesome*. C'est une bibliothèque qui permet d'afficher des icônes (comme le calendrier ou la poubelle) simplement avec des balises `<i>`."
*   **Q : "C'est quoi le `animate-fade-in` ?"**
    *   R : "C'est une animation CSS personnalisée que nous avons créée dans `style.css`. Elle permet aux éléments d'apparaître progressivement avec un léger mouvement vers le haut pour rendre le site plus 'vivant'."
*   **Q : "Pourquoi le tableau change de couleur selon le cours ?"**
    *   R : "Nous utilisons des classes CSS dynamiques (ex: `badge-cm`, `badge-td`). Jinja2 injecte le nom du type de cours dans la classe, et le CSS applique la bonne couleur."
