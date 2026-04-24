from app import create_app
from app.extensions import db
from app.models import User, Formation, Module

app = create_app()

with app.app_context():
    # Création de toutes les tables définies dans les modèles
    db.create_all()
    print("Tables créées avec succès.")

    # Vérifier si l'admin existe déjà
    admin = User.query.filter_by(email='admin@univ.fr').first()
    if not admin:
        admin = User(email='admin@univ.fr', role='admin')
        admin.set_password('admin123')
        db.session.add(admin)
        print("Utilisateur Admin créé : admin@univ.fr / admin123")

    # Étudiant de test
    student = User.query.filter_by(email='test@student.fr').first()
    if not student:
        student = User(email='test@student.fr', role='student')
        student.set_password('student123')
        db.session.add(student)
        print("Utilisateur Étudiant créé : test@student.fr / student123")

    # Ajouter une formation par défaut pour que ce soit testable directement
    formation = Formation.query.first()
    if not formation:
        formation = Formation(nom='BUT Informatique', nb_groupes_td=2, nb_groupes_tp=4)
        db.session.add(formation)
        db.session.commit() # Commit pour avoir l'ID de la formation
        
        module1 = Module(code='R1.01', libelle='Initiation au développement', cm_heures=10.0, td_heures=15.0, tp_heures=15.0, formation_id=formation.id)
        db.session.add(module1)
        print("Formation et module de test créés.")

    db.session.commit()
    print("Base de données initialisée et prête à l'emploi.")
