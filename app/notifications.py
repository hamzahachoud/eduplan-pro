from app.extensions import db
from app.models import Notification, User, Seance

def add_notification(user_id, message, type='info'):
    """Ajoute une notification en base pour un utilisateur."""
    n = Notification(user_id=user_id, message=message, type=type)
    db.session.add(n)

def notify_seance_change(seance, message, type='info'):
    """Notifie l'enseignant et les étudiants concernés par un changement de séance."""
    # 1. Enseignant
    if seance.enseignant_id:
        teacher_user = User.query.filter_by(enseignant_id=seance.enseignant_id).first()
        if teacher_user:
            add_notification(teacher_user.id, message, type)
            
    # 2. Étudiants
    fid = seance.module.formation_id
    query = User.query.filter_by(formation_id=fid, role='student')
    
    # Filtrage par groupe
    if seance.groupe == 'CM':
        students = query.all()
    elif seance.groupe.startswith('TD'):
        students = query.filter_by(td_group=seance.groupe).all()
    elif seance.groupe.startswith('TP'):
        students = query.filter_by(tp_group=seance.groupe).all()
    else:
        students = []
        
    for s in students:
        add_notification(s.id, message, type)

def notify_admin(message, type='warning'):
    """Notifie tous les administrateurs."""
    admins = User.query.filter_by(role='admin').all()
    for a in admins:
        add_notification(a.id, message, type)
