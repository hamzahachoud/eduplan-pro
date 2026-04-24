from app import create_app
from app.extensions import db
from app.models import User, Enseignant

app = create_app()
with app.app_context():
    # Supprimer ancien compte mal formé
    User.query.filter_by(role='teacher').delete()
    db.session.commit()
    
    # Créer un compte pour chaque enseignant
    print('=== CREATION DES COMPTES PROF ===\n')
    for ens in Enseignant.query.all():
        # Nettoyer le nom pour l'email (supprimer espaces, accents basiques)
        nom_clean = ens.nom.strip().lower().replace(' ', '_')
        prenom_clean = ens.prenom.strip().lower().replace(' ', '_')
        email = f'{prenom_clean}.{nom_clean}@eduplan.fr'
        
        # Supprimer si existe
        existing = User.query.filter_by(email=email).first()
        if existing:
            db.session.delete(existing)
        
        user = User(email=email, role='teacher', enseignant_id=ens.id)
        user.set_password('prof123')
        db.session.add(user)
        print(f'Enseignant: {ens.prenom.strip()} {ens.nom.strip()}')
        print(f'  Email   : {email}')
        print(f'  Mot de passe: prof123\n')
    
    db.session.commit()
    print('=== TOUS LES COMPTES ONT ETE CREES ===')
