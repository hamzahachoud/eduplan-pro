from flask import render_template, redirect, url_for, flash
from flask_login import login_required, current_user
from app.teacher import teacher_bp
from app.models import Seance, Affectation, Module
from datetime import date, timedelta
from collections import OrderedDict

def _get_planning_data(enseignant):
    """Calcule toutes les données nécessaires pour le planning du professeur."""
    from flask import request
    from datetime import datetime
    
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
    dimanche = lundi + timedelta(days=6)
    
    prev_week = (lundi - timedelta(days=7)).strftime('%Y-%m-%d')
    next_week = (lundi + timedelta(days=7)).strftime('%Y-%m-%d')
    today_str = date.today().strftime('%Y-%m-%d')

    # Séances de la semaine ciblée
    seances_semaine_list = Seance.query.filter(
        Seance.enseignant_id == enseignant.id,
        Seance.date_seance >= lundi,
        Seance.date_seance <= samedi
    ).order_by(Seance.date_seance, Seance.heure_debut).all()
    
    jours_semaine = [lundi + timedelta(days=i) for i in range(6)]
    creneaux_uniques = sorted(list(set([s.heure_debut for s in seances_semaine_list])))

    grid_data = {}
    for s in seances_semaine_list:
        d = s.date_seance
        t = s.heure_debut
        if d not in grid_data: grid_data[d] = {}
        grid_data[d][t] = s

    view_mode = request.args.get('view', 'grid')

    # Stats calculées sur TOUTES les séances
    seances_all = Seance.query.filter_by(enseignant_id=enseignant.id).all()
    today = date.today()

    # Stats globales
    seances_futures = sum(1 for s in seances_all if s.date_seance >= today)
    seances_semaine_stats = sum(1 for s in seances_all if (today - timedelta(days=today.weekday())) <= s.date_seance <= (today - timedelta(days=today.weekday()) + timedelta(days=6)))
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
        'lundi': lundi,
        'samedi': samedi,
        'prev_week': prev_week,
        'next_week': next_week,
        'today_str': today_str,
        'jours_semaine': jours_semaine,
        'creneaux': creneaux_uniques,
        'grid_data': grid_data,
        'view_mode': view_mode,
        'seances_futures': seances_futures,
        'seances_semaine': seances_semaine_stats,
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

@teacher_bp.route('/export/pdf/planning')
@login_required
def export_pdf_planning():
    if not current_user.is_teacher():
        flash('Accès refusé.', 'danger')
        return redirect(url_for('admin.login'))
        
    enseignant = current_user.enseignant
    if not enseignant:
        flash('Profil enseignant introuvable.', 'warning')
        return redirect(url_for('admin.login'))
        
    seances = Seance.query.filter_by(enseignant_id=enseignant.id).order_by(Seance.date_seance, Seance.heure_debut).all()
    if not seances:
        flash('Aucune séance à exporter.', 'info')
        return redirect(url_for('teacher.planning'))
        
    from app.exports import generate_pdf_response
    title = f'Emploi du Temps - {enseignant.prenom.strip()} {enseignant.nom.strip()}'
    return generate_pdf_response('planning_enseignant.pdf', title, seances)
