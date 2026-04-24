from flask import Flask
from app.config import Config
from app.extensions import db, migrate, login_manager

def create_app(config_class=Config):
    """
    Application Factory Pattern.
    Crée et configure l'instance Flask de notre application.
    """
    app = Flask(__name__)
    app.config.from_object(config_class)

    # Initialisation des extensions avec l'instance de l'application
    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)

    # Configuration du user loader pour Flask-Login
    from app.models import User
    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    # Importation et enregistrement des Blueprints
    from app.admin.routes import admin_bp
    from app.student.routes import student_bp
    from app.teacher import teacher_bp

    # On enregistre l'admin sous le préfixe /admin et l'étudiant à la racine (ou /student)
    app.register_blueprint(admin_bp, url_prefix='/admin')
    app.register_blueprint(student_bp)
    app.register_blueprint(teacher_bp, url_prefix='/teacher')

    # Configuration Globale Jinja2
    app.jinja_env.globals.update(chr=chr)

    return app
