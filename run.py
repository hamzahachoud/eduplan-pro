from app import create_app
from app.extensions import db

# Création de l'application Flask
app = create_app()

# Initialisation de la base de données au premier lancement
# Cela va créer toutes les tables définies dans nos modèles
with app.app_context():
    db.create_all()
    # Note: Dans un environnement de production, on utiliserait Flask-Migrate
    # au lieu de db.create_all() pour gérer l'évolution du schéma.


if __name__ == '__main__':
    
    
    # Lancement du serveur de développement sur le port 5000
    app.run(debug=True, port=5000)
