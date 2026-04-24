import os

basedir = os.path.abspath(os.path.dirname(__file__))
project_root = os.path.abspath(os.path.join(basedir, '..'))
instance_dir = os.path.join(project_root, 'instance')

os.makedirs(instance_dir, exist_ok=True)

class Config:
    # Clé secrète de l'application - essentiel pour la sécurité (sessions, CSRF)
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'une-cle-secrete-ultra-securisee'

    # Configuration de la base de données SQLite dans le dossier 'instance'
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or \
        'sqlite:///' + os.path.join(instance_dir, 'app.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False #Ça sert à quoi ? SQLAlchemy peut surveiller tous les objets : “est-ce que cet objet a changé ?” 
    #probleme si on le met true Ça consomme : mémoire et performance
    WTF_CSRF_ENABLED = True  # Flask-WTF active automatiquement la protection. CSRF = attaque web Flask protège avec un token secret dans le formulaire et le compare avec le token de la session utilisateur 
    #ça sert à quoi ? pour éviter les attaques web (un pirate envoie un formulaire à la place de l'utilisateur) 
