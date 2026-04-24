from flask import render_template, redirect, url_for, flash
from flask_login import login_required, current_user
from app.teacher import teacher_bp
from app.models import Seance, Affectation, Module
from datetime import date, timedelta
from collections import OrderedDict

def _get_planning_data(enseignant):
    """Calcule toutes les données nécessaires pour le planning du professeur."""
    today = date.today()
    lundi = today - timedelta(days=today.weekday())
    dimanche = lundi + timedelta(days=6)

    seances_all = Seance.query.filter_by(enseignant_id=enseignant.id) \
                              .order_by(Seance.date_seance, Seance.heure_debut).all()

    # Grouper par date
    seances_grouped = OrderedDict()
    for s in seances_all:
        seances_grouped.setdefault(s.date_seance, []).append(s)

    # Stats globales
    seances_futures = sum(1 for s in seances_all if s.date_seance >= today)
    seances_semaine = sum(1 for s in seances_all if lundi <= s.date_seance <= dimanche)
    heures_effectuees = sum(s.duree for s in seances_all if s.date_seance < today)
    heures_planifiees = sum(s.duree for s in seances_all)

    # Stats par module (quota vs réalisé)
    affectations = Affectation.query.filter_by(enseignant_id=enseignant.id).all()
    module_stats = []
    total_quota = 0
    total_heures_sup = 0.0

    for aff in affectations:
        cm_fait = sum(s.duree for s in seances_all if s.module_id == aff.module_id and s.type_seance == 'CM')
        td_fait = sum(s.duree for s in seances_all if s.module_id == aff.module_id and s.type_seance == 'TD')
        tp_fait = sum(s.duree for s in seances_all if s.module_id == aff.module_id and s.type_seance == 'TP')
        
        quota = aff.cm_heures + aff.td_heures + aff.tp_heures
        fait  = cm_fait + td_fait + tp_fait
        reste = max(0, quota - fait)
        h_sup = max(0, fait - quota)
        total_heures_sup += h_sup
        total_quota += quota

        module_stats.append({
            'module': aff.module,
            'quota': quota,
            'fait': fait,
            'reste': reste,
            'h_sup': h_sup,
            'percent': min(100, int(fait / quota * 100)) if quota > 0 else 0,
            'cm_quota': aff.cm_heures, 'cm_fait': cm_fait,
            'td_quota': aff.td_heures, 'td_fait': td_fait,
            'tp_quota': aff.tp_heures, 'tp_fait': tp_fait,
        })

    heures_restantes = max(0, total_quota - heures_planifiees)

    return {
        'today': today,
        'seances_grouped': seances_grouped,
        'seances_futures': seances_futures,
        'seances_semaine': seances_semaine,
        'seances_total': len(seances_all),
        'heures_effectuees': heures_effectuees,
        'heures_planifiees': heures_planifiees,
        'heures_restantes': heures_restantes,
        'heures_sup': total_heures_sup,
        'module_stats': module_stats,
    }


@teacher_bp.route('/dashboard')
@login_required
def dashboard():
    return redirect(url_for('teacher.planning'))


@teacher_bp.route('/planning')
@login_required
def planning():
    if not current_user.is_teacher():
        flash('Accès réservé aux enseignants.', 'danger')
        return redirect(url_for('admin.login'))

    enseignant = current_user.enseignant
    if not enseignant:
        flash('Votre compte n\'est pas lié à un profil enseignant.', 'warning')
        return redirect(url_for('admin.login'))

    ctx = _get_planning_data(enseignant)
    return render_template(
        'teacher/planning.html',
        title=f'Mon Planning – {enseignant.prenom.strip()} {enseignant.nom.strip()}',
        enseignant=enseignant,
        **ctx
    )
