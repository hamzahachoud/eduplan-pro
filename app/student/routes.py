from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required, current_user
from app.extensions import db
from app.models import User, Seance, Formation, Module, Notification
from app.admin.forms import LoginForm  # On réutilise le formulaire de login

student_bp = Blueprint('student', __name__)

@student_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        if current_user.is_admin():
            return redirect(url_for('admin.dashboard'))
        if current_user.is_teacher():
            return redirect(url_for('teacher.planning'))
        return redirect(url_for('student.dashboard'))
    
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if user is None or not user.check_password(form.password.data):
            flash('Email ou mot de passe invalide.', 'danger')
            return redirect(url_for('student.login'))
        
        login_user(user)
        # Redirection selon le rôle
        if user.is_admin():
            return redirect(url_for('admin.dashboard'))
        return redirect(url_for('student.dashboard'))
    
    return render_template('student/login.html', title='Connexion Étudiant', form=form)

@student_bp.route('/')
def index():
    if current_user.is_authenticated:
        if current_user.is_admin():
            return redirect(url_for('admin.dashboard'))
        if current_user.is_teacher():
            return redirect(url_for('teacher.planning'))
        return redirect(url_for('student.dashboard'))
    return render_template('home.html', title='Accueil')

@student_bp.route('/dashboard')
@login_required
def dashboard():
    # Rediriger les profs vers leur espace
    if current_user.is_teacher():
        return redirect(url_for('teacher.planning'))
    if current_user.is_admin():
        return redirect(url_for('admin.dashboard'))
    
    formations = Formation.query.all()
    return render_template('student/dashboard.html', title='Espace Étudiant', formations=formations)

@student_bp.route('/setup_groups', methods=['POST'])
@login_required
def setup_groups():
    fid = request.form.get('formation_id')
    td_group = request.form.get('td_group')
    tp_group = request.form.get('tp_group')
    
    current_user.formation_id = int(fid) if fid else None
    current_user.td_group = td_group
    current_user.tp_group = tp_group
    db.session.commit()
    
    flash('Groupes mis à jour avec succès.', 'success')
    return redirect(url_for('student.planning'))

@student_bp.route('/planning')
@login_required
def planning():
    """
    Affiche le planning personnalisé pour l'étudiant connecté.
    """
    if not current_user.formation_id or not current_user.td_group or not current_user.tp_group:
        flash('Veuillez d\'abord configurer votre profil (Formation, TD, TP).', 'info')
        return redirect(url_for('student.dashboard'))

    # Filtrage par semaine
    from datetime import datetime, date, timedelta
    target_date_str = request.args.get('date')
    if target_date_str:
        try:
            target_date = datetime.strptime(target_date_str, '%Y-%m-%d').date()
        except ValueError:
            target_date = date.today()
    else:
        target_date = date.today()
        
    lundi = target_date - timedelta(days=target_date.weekday())
    samedi = lundi + timedelta(days=5)
    
    prev_week = (lundi - timedelta(days=7)).strftime('%Y-%m-%d')
    next_week = (lundi + timedelta(days=7)).strftime('%Y-%m-%d')
    today_str = date.today().strftime('%Y-%m-%d')

    # Récupération des séances : CM + TD de son groupe + TP de son groupe UNIQUEMENT pour sa formation et cette semaine
    seances_all = Seance.query.join(Module).filter(
        Module.formation_id == current_user.formation_id,
        Seance.date_seance >= lundi,
        Seance.date_seance <= samedi,
        db.or_(
            Seance.type_seance == 'CM',
            Seance.groupe == current_user.td_group,
            Seance.groupe == current_user.tp_group
        )
    ).order_by(Seance.date_seance, Seance.heure_debut).all()
    
    # On force les jours de la semaine (Lundi à Samedi) même s'ils sont vides pour avoir une belle grille
    jours_semaine = [lundi + timedelta(days=i) for i in range(6)]
    creneaux_uniques = sorted(list(set([s.heure_debut for s in seances_all])))

    # Grid data reste identique pour compatibilité avec vue liste, mais on l'utilisera aussi pour la grille
    grid_data = {}
    for s in seances_all:
        d = s.date_seance
        t = s.heure_debut
        if d not in grid_data: grid_data[d] = {}
        grid_data[d][t] = s

    view_mode = request.args.get('view', 'grid')

    return render_template('student/planning.html', 
                           title=f'Mon Planning ({current_user.td_group}/{current_user.tp_group})', 
                           grid_data=grid_data, 
                           jours_semaine=jours_semaine, creneaux=creneaux_uniques,
                           lundi=lundi, samedi=samedi, prev_week=prev_week, 
                           next_week=next_week, today_str=today_str, view_mode=view_mode)

@student_bp.route('/notifications')
@login_required
def view_notifications():
    notifications = current_user.notifications.order_by(Notification.created_at.desc()).all()
    return render_template('student/notifications.html', title='Mes Notifications', notifications=notifications)

@student_bp.route('/notification/read/<int:id>')
@login_required
def read_notification(id):
    notif = Notification.query.get_or_404(id)
    if notif.user_id == current_user.id:
        notif.is_read = True
        db.session.commit()
    return redirect(request.referrer or url_for('student.dashboard'))

@student_bp.route('/notifications/read_all')
@login_required
def read_all_notifications():
    current_user.notifications.filter_by(is_read=False).update({'is_read': True})
    db.session.commit()
    flash('Toutes les notifications ont été marquées comme lues.', 'success')
    return redirect(request.referrer or url_for('student.dashboard'))

@student_bp.route('/export/pdf/planning')
@login_required
def export_pdf_planning():
    if not current_user.formation_id or not current_user.td_group or not current_user.tp_group:
        flash('Veuillez d\'abord configurer votre profil.', 'warning')
        return redirect(url_for('student.dashboard'))
        
    seances = Seance.query.join(Module).filter(
        Module.formation_id == current_user.formation_id,
        db.or_(
            Seance.type_seance == 'CM',
            Seance.groupe == current_user.td_group,
            Seance.groupe == current_user.tp_group
        )
    ).order_by(Seance.date_seance, Seance.heure_debut).all()
    
    if not seances:
        flash('Aucune séance à exporter.', 'info')
        return redirect(url_for('student.planning'))
        
    from app.exports import generate_pdf_response
    title = f'Emploi du Temps - {current_user.formation.nom} ({current_user.td_group}/{current_user.tp_group})'
    return generate_pdf_response('mon_planning.pdf', title, seances)
