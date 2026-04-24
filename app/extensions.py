from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager

# Initialisation des extensions Flask
db = SQLAlchemy() #db = une connexion à la base (pas encore branchée) 
migrate = Migrate() #migrate = un outil pour faire évoluer la base de données sans perdre les données
login_manager = LoginManager() #login_manager = un outil pour gérer les utilisateurs connectés 

# Configuration du gestionnaire de connexion (LoginManager)
# On redirige vers la vue 'admin.login' si l'utilisateur non authentifié 
# tente d'accéder à une page protégée
login_manager.login_view = 'student.login' #login_manager.login_view = 'admin.login' = si un utilisateur non connecté essaie d'accéder à une page protégée, il sera redirigé vers la page de connexion de l'admin
login_manager.login_message = "Veuillez vous connecter pour accéder à cette page."   #login_manager.login_message = "Veuillez vous connecter pour accéder à cette page." = message affiché à l'utilisateur non connecté
login_manager.login_message_category = "info"  
# Sert pour le style du message (Bootstrap par exemple)

# Exemples :

# info → bleu
# warning → jaune
# danger → rouge
# success → vert




from flask import request, redirect, url_for, flash 

@login_manager.unauthorized_handler
def unauthorized(): #login_manager.unauthorized_handler = c'est une fonction qui est appelée lorsque un utilisateur non connecté tente d'accéder à une page protégée
    flash("Veuillez vous connecter pour accéder à cette page.", "info") #login_manager.login_message = "Veuillez vous connecter pour accéder à cette page." = message affiché à l'utilisateur non connecté

    if request.path.startswith('/admin'): #request.path.startswith('/admin') = si l'utilisateur essaie d'accéder à une page protégée, il sera redirigé vers la page de connexion de l'admin
        return redirect(url_for('admin.login')) #login_manager.login_view = 'admin.login' = si un utilisateur non connecté essaie d'accéder à une page protégée, il sera redirigé vers la page de connexion de l'admin

    if request.path.startswith('/teacher'): 
        return redirect(url_for('teacher.login')) #login_manager.login_view = 'admin.login' = si un utilisateur non connecté essaie d'accéder à une page protégée, il sera redirigé vers la page de connexion de l'admin

    return redirect(url_for('student.login'))
#il mets /admin/dashboard en generale tout ce qui concerne admin et qu'il nest pas connecter bah il le rend a la page de connexion admin et si l'inverse il mets des truc qui concerne pas admin comme http://127.0.0.1:5000/dashboard voila bah ca ca concerne pas cote admin bah la si il est pas connecter comme etudiant bah ca le renvoie a login etudiant


#EXEMPLE DE PROTECTION DES ROUTES

# @login_required  Parce que c’est lui qui déclenche la sécurité. 👉 Tout le monde passe ❌ 
# @admin_required  Parce que c’est lui qui vérifie si tu es admin. 👉 Seuls les admins passent ✅
# def admin_only():
#     return "Accès réservé aux administrateurs connectés" 
#from flask_login import login_required

# @admin_bp.route('/dashboard')
# @login_required
# def dashboard():
#     return "Dashboard"