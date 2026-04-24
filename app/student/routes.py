from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required, current_user
from app.extensions import db
from app.models import User, Seance, Formation
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
    if not current_user.td_group or not current_user.tp_group:
        flash('Veuillez d\'abord sélectionner vos groupes TD et TP.', 'info')
        return redirect(url_for('student.dashboard'))

    # Récupération des séances : CM + TD de son groupe + TP de son groupe
    seances_all = Seance.query.filter(
        db.or_(
            Seance.type_seance == 'CM',
            Seance.groupe == current_user.td_group,
            Seance.groupe == current_user.tp_group
        )
    ).order_by(Seance.date_seance, Seance.heure_debut).all()
    
    dates_uniques = sorted(list(set([s.date_seance for s in seances_all])))
    creneaux_uniques = sorted(list(set([s.heure_debut for s in seances_all])))

    # Grid data
    grid_data = {}
    for s in seances_all:
        d = s.date_seance
        t = s.heure_debut
        if d not in grid_data: grid_data[d] = {}
        grid_data[d][t] = s

    return render_template('student/planning.html', 
                           title=f'Mon Planning ({current_user.td_group}/{current_user.tp_group})', 
                           grid_data=grid_data, 
                           dates=dates_uniques, creneaux=creneaux_uniques)
