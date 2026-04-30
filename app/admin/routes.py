from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required, current_user
from app.extensions import db
from app.models import User, Formation, Module, Enseignant, Affectation, Seance, Salle
from app.admin.forms import LoginForm, FormationForm, ModuleForm, EnseignantForm, AffectationForm, SeanceForm, SalleForm
from urllib.parse import urlsplit
from datetime import date, time, datetime, timedelta
from app import csrf
from app.notifications import notify_seance_change, notify_admin

admin_bp = Blueprint('admin', __name__)

@admin_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        if current_user.is_admin():
            return redirect(url_for('admin.dashboard'))
        elif current_user.is_teacher():
            return redirect(url_for('teacher.planning'))
    
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if user is None or not user.check_password(form.password.data):
            flash('Email ou mot de passe invalide.', 'danger')
            return redirect(url_for('admin.login'))
        
        if not (user.is_admin() or user.is_teacher()):
            flash('Accès réservé aux administrateurs et enseignants.', 'danger')
            return redirect(url_for('admin.login'))
        
        login_user(user)
        if user.is_teacher():
            return redirect(url_for('teacher.planning'))
        next_page = request.args.get('next')
        if not next_page or urlsplit(next_page).netloc != '':
            next_page = url_for('admin.dashboard')
        return redirect(next_page)
    
    return render_template('admin/login.html', title='Connexion', form=form)

@admin_bp.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('student.index'))

@admin_bp.route('/')
@admin_bp.route('/dashboard')
@login_required
def dashboard():
    if not current_user.is_admin():
        flash('Accès refusé.', 'danger')
        return redirect(url_for('student.dashboard'))
    
    formations = Formation.query.all()
    modules = Module.query.all()
    enseignants = Enseignant.query.all()
    seances_count = Seance.query.count()
    
    stats = {
        'formations_count': len(formations),
        'modules_count': len(modules),
        'enseignants_count': len(enseignants),
        'seances_count': seances_count
    }
    
    # --- ALERTS COMPUTATION ---
    alertes = {
        'modules_sans_affectation': [],
        'seances_sans_enseignant': [],
        'seances_sans_salle': [],
        'enseignants_surcharge': [],
        'modules_incomplets': [],
        'formations_sans_seance': []
    }
    
    # 1. Formations sans séance
    form_seances = db.session.query(Module.formation_id, db.func.count(Seance.id)).join(Seance).group_by(Module.formation_id).all()
    form_seance_dict = {f_id: count for f_id, count in form_seances}
    for f in formations:
        if form_seance_dict.get(f.id, 0) == 0:
            alertes['formations_sans_seance'].append(f)

    # 2. Séances sans enseignant ou salle
    seances_sans_prof = Seance.query.filter(Seance.enseignant_id.is_(None)).all()
    if seances_sans_prof: alertes['seances_sans_enseignant'] = seances_sans_prof
    
    seances_sans_salle = Seance.query.filter(Seance.salle_id.is_(None)).all()
    if seances_sans_salle: alertes['seances_sans_salle'] = seances_sans_salle
    
    # 3. Enseignants en surcharge
    prof_summary = db.session.query(Seance.enseignant_id, db.func.sum(Seance.duree)).group_by(Seance.enseignant_id).all()
    prof_dict = {p_id: tot for p_id, tot in prof_summary if p_id}
    
    aff_summary = db.session.query(Affectation.enseignant_id, db.func.sum(Affectation.cm_heures + Affectation.td_heures + Affectation.tp_heures)).group_by(Affectation.enseignant_id).all()
    aff_dict = {p_id: tot for p_id, tot in aff_summary if p_id}
    
    for ens in enseignants:
        total_affecte = aff_dict.get(ens.id, 0)
        total_planifie = prof_dict.get(ens.id, 0)
        if total_planifie > total_affecte and total_affecte > 0:
            alertes['enseignants_surcharge'].append({'enseignant': ens, 'depassement': total_planifie - total_affecte})
            
    # 4. Modules sans affectation & Modules incomplets
    seances_summary = db.session.query(
        Seance.module_id, Seance.type_seance, Seance.groupe, db.func.sum(Seance.duree)
    ).group_by(Seance.module_id, Seance.type_seance, Seance.groupe).all()
    
    summary_dict = {}
    for mod_id, t_seance, gp, tot in seances_summary:
        if mod_id not in summary_dict: summary_dict[mod_id] = {}
        if t_seance not in summary_dict[mod_id]: summary_dict[mod_id][t_seance] = {}
        summary_dict[mod_id][t_seance][gp] = tot
        
    # Optimisation affectations par module
    aff_mod_summary = db.session.query(Affectation.module_id, db.func.count(Affectation.id)).group_by(Affectation.module_id).all()
    aff_mod_dict = {m_id: count for m_id, count in aff_mod_summary}

    for m in modules:
        # Modules sans affectation
        if aff_mod_dict.get(m.id, 0) == 0:
            alertes['modules_sans_affectation'].append(m)
            
        # Modules incomplets
        structure = build_group_structure(m.formation)
        missing = []
        d_mod = summary_dict.get(m.id, {})
        
        deja_cm = d_mod.get('CM', {}).get('CM', 0)
        if deja_cm < m.cm_heures:
            missing.append(f"CM: {deja_cm}/{m.cm_heures}h")
            
        for gp in structure['all_td']:
            deja = d_mod.get('TD', {}).get(gp, 0)
            if deja < m.td_heures:
                missing.append(f"TD {gp}: {deja}/{m.td_heures}h")
                
        for gp in structure['all_tp']:
            deja = d_mod.get('TP', {}).get(gp, 0)
            if deja < m.tp_heures:
                missing.append(f"TP {gp}: {deja}/{m.tp_heures}h")
                
        if missing:
            alertes['modules_incomplets'].append({'module': m, 'missing': missing})

    total_alertes = (len(alertes['modules_sans_affectation']) + 
                     len(alertes['seances_sans_enseignant']) + 
                     len(alertes['seances_sans_salle']) + 
                     len(alertes['enseignants_surcharge']) + 
                     len(alertes['modules_incomplets']) + 
                     len(alertes['formations_sans_seance']))

    return render_template('admin/dashboard.html', title='Dashboard', stats=stats, alertes=alertes, total_alertes=total_alertes)

@admin_bp.route('/formations', methods=['GET', 'POST'])
@login_required
def formations():
    if not current_user.is_admin():
        flash('Accès refusé.', 'danger')
        return redirect(url_for('student.dashboard'))
    
    form = FormationForm()
    if form.validate_on_submit():
        formation = Formation(
            nom=form.nom.data, 
            nb_groupes_td=form.nb_groupes_td.data, 
            nb_groupes_tp=form.nb_groupes_tp.data
        )
        db.session.add(formation)
        db.session.commit()
        flash('Formation ajoutée avec succès!', 'success')
        return redirect(url_for('admin.formations'))
    
    formations_list = Formation.query.all()
    return render_template('admin/formation.html', title='Gestion des Formations', form=form, formations=formations_list)

@admin_bp.route('/delete_formation/<int:id>', methods=['POST'])
@login_required
def delete_formation(id):
    if not current_user.is_admin():
        flash('Accès refusé.', 'danger')
        return redirect(url_for('student.dashboard'))
    
    formation = Formation.query.get_or_404(id)
    # Protection : ne pas supprimer si contient des modules
    if formation.modules.count() > 0:
        flash('Impossible de supprimer cette formation car elle contient encore des modules. Supprimez d\'abord les modules associés.', 'danger')
        return redirect(url_for('admin.formations'))
        
    db.session.delete(formation)
    db.session.commit()
    flash('Formation supprimée.', 'success')
    return redirect(url_for('admin.formations'))

@admin_bp.route('/modules', methods=['GET', 'POST'])
@login_required
def modules():
    if not current_user.is_admin():
        flash('Accès refusé.', 'danger')
        return redirect(url_for('student.dashboard'))
    
    form = ModuleForm()
    if form.validate_on_submit():
        module = Module(
            code=form.code.data,
            libelle=form.libelle.data,
            cm_heures=form.cm_heures.data,
            td_heures=form.td_heures.data,
            tp_heures=form.tp_heures.data,
            categorie=form.categorie.data,
            formation_id=form.formation_id.data
        )
        db.session.add(module)
        db.session.commit()
        flash('Module ajouté avec succès!', 'success')
        return redirect(url_for('admin.modules'))
    
    query = Module.query
    
    # Filtrage
    search_q = request.args.get('q', '').strip()
    formation_id = request.args.get('formation_id', '')
    categorie = request.args.get('categorie', '')
    sort_by = request.args.get('sort', 'code')
    
    if search_q:
        query = query.filter(db.or_(
            Module.code.ilike(f'%{search_q}%'),
            Module.libelle.ilike(f'%{search_q}%')
        ))
    if formation_id:
        query = query.filter(Module.formation_id == int(formation_id))
    if categorie:
        query = query.filter(Module.categorie.ilike(f'%{categorie}%'))
        
    if sort_by == 'formation':
        query = query.join(Formation).order_by(Formation.nom, Module.code)
    else:
        query = query.order_by(Module.code)
        
    modules_list = query.all()
    
    # Pour les selects de filtre
    formations_list = Formation.query.all()
    categories_list = sorted(set([m.categorie for m in Module.query.all() if m.categorie]))
    
    return render_template('admin/modules.html', title='Gestion des Modules', form=form, 
                           modules=modules_list, formations=formations_list, categories=categories_list)

@admin_bp.route('/delete_module/<int:id>', methods=['POST'])
@login_required
def delete_module(id):
    if not current_user.is_admin():
        flash('Accès refusé.', 'danger')
        return redirect(url_for('student.dashboard'))
    
    module = Module.query.get_or_404(id)
    # Protection : ne pas supprimer si déjà utilisé dans le planning
    if module.seances.count() > 0:
        flash('Impossible de supprimer ce module car des séances sont déjà planifiées pour lui.', 'danger')
        return redirect(url_for('admin.modules'))
        
    db.session.delete(module)
    db.session.commit()
    flash('Module supprimé.', 'success')
    return redirect(url_for('admin.modules'))

@admin_bp.route('/edit_module/<int:id>', methods=['GET', 'POST'])
@login_required
def edit_module(id):
    if not current_user.is_admin():
        flash('Accès refusé.', 'danger')
        return redirect(url_for('student.dashboard'))
    
    module = Module.query.get_or_404(id)
    
    if request.method == 'POST':
        try:
            module.cm_heures = float(request.form.get('cm_heures', module.cm_heures))
            module.td_heures = float(request.form.get('td_heures', module.td_heures))
            module.tp_heures = float(request.form.get('tp_heures', module.tp_heures))
            module.categorie = request.form.get('categorie', module.categorie)
            db.session.commit()
            flash('Module mis à jour avec succès !', 'success')
        except Exception as e:
            db.session.rollback()
            flash(f'Erreur lors de la mise à jour : {str(e)}', 'danger')
        return redirect(url_for('admin.modules'))
    
    return render_template('admin/edit_module.html', title=f'Modifier {module.code}', 
                           module=module,
                           categories=sorted(set(s.categorie for s in Salle.query.all() if s.categorie)))

@admin_bp.route('/enseignants', methods=['GET', 'POST'])
@login_required
def enseignants():
    if not current_user.is_admin():
        flash('Accès refusé.', 'danger')
        return redirect(url_for('student.dashboard'))
    
    form_enseignant = EnseignantForm()
    form_affectation = AffectationForm()
    
    if 'submit_enseignant' in request.form and form_enseignant.validate():
        enseignant = Enseignant(nom=form_enseignant.nom.data, prenom=form_enseignant.prenom.data)
        db.session.add(enseignant)
        db.session.commit()
        flash('Enseignant ajouté avec succès!', 'success')
        return redirect(url_for('admin.enseignants'))
        
    if 'submit_affectation' in request.form and form_affectation.validate():
        affectation = Affectation(
            enseignant_id=form_affectation.enseignant_id.data,
            module_id=form_affectation.module_id.data,
            cm_heures=form_affectation.cm_heures.data,
            td_heures=form_affectation.td_heures.data,
            tp_heures=form_affectation.tp_heures.data
        )
        db.session.add(affectation)
        db.session.commit()
        flash('Affectation réussie!', 'success')
        return redirect(url_for('admin.enseignants'))

    query = Enseignant.query
    search_q = request.args.get('q', '').strip()
    filter_module_id = request.args.get('module_id', '')
    filter_status = request.args.get('status', '') # 'surcharge', 'sans_affectation'
    
    if search_q:
        query = query.filter(db.or_(
            Enseignant.nom.ilike(f'%{search_q}%'),
            Enseignant.prenom.ilike(f'%{search_q}%')
        ))
        
    if filter_module_id:
        query = query.join(Affectation).filter(Affectation.module_id == int(filter_module_id))
        
    enseignants_list = query.order_by(Enseignant.nom).all()
    
    stats_profs = []
    for ens in enseignants_list:
        affectations = Affectation.query.filter_by(enseignant_id=ens.id).all()
        # Heures totales affectées (Maquette)
        total_affecte = sum([(a.cm_heures + a.td_heures + a.tp_heures) for a in affectations])
        # Heures déjà planifiées dans Seance
        total_planifie = sum([s.duree for s in Seance.query.filter_by(enseignant_id=ens.id).all()])
        
        has_surcharge = total_planifie > total_affecte
        is_sans_affectation = len(affectations) == 0
        
        # Application des filtres post-calcul
        if filter_status == 'surcharge' and not has_surcharge:
            continue
        if filter_status == 'sans_affectation' and not is_sans_affectation:
            continue
        
        stats_profs.append({
            'enseignant': ens,
            'total_affecte': total_affecte,
            'total_planifie': total_planifie,
            'reste': max(0, total_affecte - total_planifie),
            'h_sup': max(0, total_planifie - total_affecte),
            'percent': int((total_planifie / total_affecte * 100)) if total_affecte > 0 else 0
        })

    affectations_list = Affectation.query.all()
    all_modules = Module.query.order_by(Module.code).all()
    
    return render_template('admin/enseignants.html', title='Enseignants & Affectations', 
                           form_enseignant=form_enseignant, form_affectation=form_affectation, 
                           enseignants=enseignants_list, affectations=affectations_list,
                           stats_profs=stats_profs, modules=all_modules)
                           
@admin_bp.route('/salles', methods=['GET', 'POST'])
@login_required
def salles():
    if not current_user.is_admin():
        flash('Accès refusé.', 'danger')
        return redirect(url_for('student.dashboard'))
        
    form = SalleForm()
    if form.validate_on_submit():
        t = form.type_salle.data
        n = form.nombre.data
        cap = form.capacite.data
        cat = form.categorie.data
        
        if t == 'Amphi':
            salle = Salle(nom=form.nom.data, type_salle=t, capacite=cap)
            db.session.add(salle)
        else:
            # Bulk creation TD or TP
            for i in range(1, n + 1):
                nom_salle = f"{t}{i}"
                if t == 'TP' and cat:
                    nom_salle = f"TP {cat} {i}"
                elif t == 'TD':
                    nom_salle = f"TD {i}"
                
                salle = Salle(nom=nom_salle, type_salle=t, categorie=cat, capacite=cap)
                db.session.add(salle)
        
        db.session.commit()
        flash('Salles ajoutées avec succès!', 'success')
        return redirect(url_for('admin.salles'))
    
    query = Salle.query
    
    search_q = request.args.get('q', '').strip()
    type_salle = request.args.get('type_salle', '')
    categorie = request.args.get('categorie', '')
    min_cap = request.args.get('min_cap', type=int)
    
    if search_q:
        query = query.filter(Salle.nom.ilike(f'%{search_q}%'))
    if type_salle:
        query = query.filter(Salle.type_salle == type_salle)
    if categorie:
        query = query.filter(Salle.categorie.ilike(f'%{categorie}%'))
    if min_cap:
        query = query.filter(Salle.capacite >= min_cap)
        
    salles_list = query.order_by(Salle.nom).all()
    categories_list = sorted(set([s.categorie for s in Salle.query.all() if s.categorie]))
    
    return render_template('admin/salles.html', title='Gestion des Salles', form=form, salles=salles_list, categories=categories_list)

@admin_bp.route('/delete_salle/<int:id>', methods=['POST'])
@login_required
def delete_salle(id):
    if not current_user.is_admin():
        flash('Accès refusé.', 'danger')
        return redirect(url_for('student.dashboard'))
        
    salle = Salle.query.get_or_404(id)
    db.session.delete(salle)
    db.session.commit()
    flash('Salle supprimée.', 'info')
    return redirect(url_for('admin.salles'))

def build_group_structure(formation):
    """
    Construit la structure des groupes (CM, TD, TP) pour une formation.
    Répartit les TP équitablement entre les TD.
    
    Retourne un dictionnaire :
    - 'groupes_ordonnes': Liste pour l'affichage de la grille
    - 'groupes_form': Liste pour les menus déroulants
    - 'tp_to_td': dict { 'TP1A': 'TD1', 'TP1B': 'TD1', 'TP2A': 'TD2' }
    - 'td_to_tp': dict { 'TD1': ['TP1A', 'TP1B'], 'TD2': ['TP2A'] }
    - 'all_td': Liste de tous les TD
    - 'all_tp': Liste de tous les TP
    """
    nb_td = formation.nb_groupes_td
    nb_tp = formation.nb_groupes_tp
    
    td_list = [f"TD{i}" for i in range(1, nb_td + 1)]
    tp_list = []
    
    tp_to_td = {}
    td_to_tp = {td: [] for td in td_list}
    
    if nb_td > 0 and nb_tp > 0:
        base_tp_per_td = nb_tp // nb_td
        extra_tp = nb_tp % nb_td
        has_multiple_tp = nb_tp > nb_td
        
        for i, td in enumerate(td_list):
            nb_tp_for_this_td = base_tp_per_td + (1 if i < extra_tp else 0)
            for j in range(nb_tp_for_this_td):
                suffix = chr(65 + j) if has_multiple_tp else ""
                tp_name = f"TP{i+1}{suffix}"
                tp_list.append(tp_name)
                tp_to_td[tp_name] = td
                td_to_tp[td].append(tp_name)
                
    elif nb_tp > 0 and nb_td == 0:
        for i in range(1, nb_tp + 1):
            tp_name = f"TP{i}"
            tp_list.append(tp_name)
            tp_to_td[tp_name] = None
    
    # Construction de l'ordre d'affichage (CM -> TD1 -> TP1A -> TP1B -> TD2 ...)
    groupes_ordonnes = ['CM']
    for td in td_list:
        groupes_ordonnes.append(td)
        for tp in td_to_tp.get(td, []):
            groupes_ordonnes.append(tp)
            
    # Si on a des TP sans TD
    for tp in tp_list:
        if tp not in groupes_ordonnes:
            groupes_ordonnes.append(tp)
            
    groupes_form = ['CM'] + td_list + tp_list
            
    return {
        'groupes_ordonnes': groupes_ordonnes,
        'groupes_form': groupes_form,
        'tp_to_td': tp_to_td,
        'td_to_tp': td_to_tp,
        'all_td': td_list,
        'all_tp': tp_list
    }

def check_seance_collisions(d, t, duree, g, e_id, s_id, formation_id, exclude_id=None):
    """
    Vérifie les collisions pour une séance.
    Retourne (True, None) si OK, (False, "Raison") sinon.
    """
    new_start_dt = datetime.combine(d, t)
    new_end_dt = new_start_dt + timedelta(hours=duree)
    new_start = new_start_dt.time()
    new_end = new_end_dt.time()

    # On vérifie sur TOUTES les séances du jour (toutes formations confondues)
    seances_du_jour = Seance.query.filter_by(date_seance=d).all()
    formation = Formation.query.get(formation_id)
    structure = build_group_structure(formation)

    for s in seances_du_jour:
        if exclude_id and s.id == exclude_id: continue
        
        # Chevauchement temporel
        if s.heure_debut < new_end and s.heure_fin > new_start:
            # 1. Collision Groupe (uniquement au sein de la même formation)
            if s.module.formation_id == formation_id:
                parent_td_new = structure['tp_to_td'].get(g)
                parent_td_existing = structure['tp_to_td'].get(s.groupe)
                if (s.groupe == g or s.groupe == 'CM' or g == 'CM' or 
                    (parent_td_new and s.groupe == parent_td_new) or
                    (parent_td_existing and g == parent_td_existing)):
                    return False, f"Groupe {g} occupé par {s.module.code} ({s.groupe})"
            
            # 2. Collision Prof (global)
            if e_id and s.enseignant_id == int(e_id):
                return False, f"Enseignant déjà en cours ({s.module.code})"
            
            # 3. Collision Salle (global)
            if s_id and int(s_id) == s.salle_id:
                return False, f"Salle déjà occupée ({s.module.code})"
                
    return True, None

@admin_bp.route('/duplicate_week', methods=['POST'])
@login_required
def duplicate_week():
    fid = request.args.get('fid', type=int)
    source_monday_str = request.form.get('source_week')
    target_monday_str = request.form.get('target_week')
    
    if not fid or not source_monday_str or not target_monday_str:
        flash('Données de duplication incomplètes.', 'danger')
        return redirect(url_for('admin.planning', fid=fid))
        
    try:
        source_monday = datetime.strptime(source_monday_str, '%Y-%m-%d').date()
        target_monday = datetime.strptime(target_monday_str, '%Y-%m-%d').date()
    except ValueError:
        flash('Format de date invalide.', 'danger')
        return redirect(url_for('admin.planning', fid=fid))

    source_saturday = source_monday + timedelta(days=5)
    seances_source = Seance.query.join(Module).filter(
        Module.formation_id == fid,
        Seance.date_seance >= source_monday,
        Seance.date_seance <= source_saturday
    ).all()

    if not seances_source:
        flash('Aucune séance trouvée sur la semaine source.', 'warning')
        return redirect(url_for('admin.planning', fid=fid))

    delta_days = (target_monday - source_monday).days
    success, fail = 0, 0
    errors = []

    for s in seances_source:
        new_date = s.date_seance + timedelta(days=delta_days)
        
        # Vérification collisions
        ok, reason = check_seance_collisions(new_date, s.heure_debut, s.duree, s.groupe, s.enseignant_id, s.salle_id, fid)
        if not ok:
            fail += 1
            errors.append(f"{new_date.strftime('%d/%m')} {s.heure_debut.strftime('%H:%M')} : {reason}")
            continue
            
        # Création
        new_s = Seance(
            module_id=s.module_id, enseignant_id=s.enseignant_id,
            type_seance=s.type_seance, groupe=s.groupe,
            date_seance=new_date, heure_debut=s.heure_debut,
            duree=s.duree, salle_id=s.salle_id
        )
        db.session.add(new_s)
        success += 1

    db.session.commit()
    flash(f"Duplication terminée : {success} créées, {fail} ignorées.", 'success' if fail == 0 else 'warning')
    for err in errors[:10]: flash(err, 'info')
    
    return redirect(url_for('admin.planning', fid=fid, date=target_monday_str))


@admin_bp.route('/planning', methods=['GET', 'POST'])
@admin_bp.route('/planning/<int:fid>', methods=['GET', 'POST'])
@login_required
def planning(fid=None):
    if not current_user.is_admin():
        flash('Accès refusé.', 'danger')
        return redirect(url_for('student.dashboard'))
    
    form = SeanceForm()
    
    if form.validate_on_submit():
        d_orig = form.date_seance.data
        t = form.heure_debut.data
        g = form.groupe.data
        e = form.enseignant_id.data
        salle_id = form.salle_id.data
        duree = form.duree.data
        type_seance = form.type_seance.data
        module = Module.query.get(form.module_id.data)
        nb_sem = form.nb_semaines.data or 1
        
        success_count, fail_count = 0, 0
        errors = []

        for i in range(nb_sem):
            d = d_orig + timedelta(days=7*i)
            
            # 1. VERIFICATION QUOTA
            seances_groupe = Seance.query.filter_by(module_id=module.id, type_seance=type_seance, groupe=g).all()
            heures_deja_planifiees = sum([s.duree for s in seances_groupe])
            
            quota_max = getattr(module, f"{type_seance.lower()}_heures")
            if heures_deja_planifiees + duree > quota_max:
                fail_count += 1
                errors.append(f"Semaine {i+1} : Quota {type_seance} dépassé ({heures_deja_planifiees + duree}/{quota_max}h)")
                continue

            # 2. VERIFICATION COLLISIONS
            ok, reason = check_seance_collisions(d, t, duree, g, e, salle_id, module.formation_id)
            if not ok:
                fail_count += 1
                errors.append(f"Semaine {i+1} : {reason}")
                continue

            # 3. CREATION
            seance = Seance(
                module_id=module.id, enseignant_id=e,
                type_seance=type_seance, groupe=g,
                date_seance=d, heure_debut=t,
                duree=duree, salle_id=salle_id
            )
            db.session.add(seance)
            db.session.flush() # Pour que le calcul du quota au prochain tour de boucle soit correct
            
            # NOTIFICATION
            msg = f"Nouvelle séance de {module.code} ({type_seance}) planifiée le {d.strftime('%d/%m')} à {t.strftime('%H:%M')}."
            notify_seance_change(seance, msg, 'success')
            
            success_count += 1

        db.session.commit()
        if success_count > 0:
            flash(f"{success_count} séance(s) planifiée(s) avec succès !", 'success')
        if fail_count > 0:
            flash(f"{fail_count} séance(s) ignorée(s) :", 'warning')
            for err in errors[:5]: flash(err, 'info')
            
        return redirect(url_for('admin.planning', fid=fid))

    # GESTION MULTI-FORMATIONS
    if not fid:
        fid = request.args.get('fid', type=int)
    formations_all = Formation.query.all()
    
    current_formation = None
    if fid:
        current_formation = Formation.query.get(fid)
    if not current_formation:
        current_formation = Formation.query.first()

    if not current_formation:
        # Cas où aucune formation n'existe encore
        return render_template('admin/planning.html', title='Planification', 
                               form=form, formations=formations_all, current_formation=None)

    # Filtrage par semaine
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

    # Filtrage des données par formation ET par semaine
    seances_all = Seance.query.join(Module).filter(
        Module.formation_id == current_formation.id,
        Seance.date_seance >= lundi,
        Seance.date_seance <= samedi
    ).order_by(Seance.date_seance, Seance.heure_debut).all()
    modules_form = Module.query.filter_by(formation_id=current_formation.id).all()
    
    structure = build_group_structure(current_formation)
    groupes_tries = structure['groupes_ordonnes']
    groupes_form = structure['groupes_form']
    
    # On récupère toutes les dates uniques
    dates_uniques = sorted(list(set([s.date_seance for s in seances_all])))
    
    # On définit les créneaux horaires (pourrait être dynamique aussi)
    # On prend tous les créneaux présents dans la base
    creneaux_uniques = sorted(list(set([s.heure_debut for s in seances_all])))

    # Construction de la grille : grid[date][time][groupe] = seance
    grid_data = {}
    for s in seances_all:
        d = s.date_seance
        t = s.heure_debut
        g = s.groupe
        if d not in grid_data: grid_data[d] = {}
        if t not in grid_data[d]: grid_data[d][t] = {}
        grid_data[d][t][g] = s

    enseignants_all = Enseignant.query.all()
    modules_all = Module.query.all()
    salles_all = Salle.query.all()

    # Data for JS filtering
    modules_data = {m.id: {'categorie': m.categorie} for m in modules_all}
    salles_data = {s.id: {'type': s.type_salle, 'categorie': s.categorie} for s in salles_all}

    # Dictionnaire des profs autorisés par module (pour le filtrage dans la grille)
    allowed_instructors = {}
    for mod in modules_all:
        affs = Affectation.query.filter_by(module_id=mod.id).all()
        allowed_instructors[mod.id] = [a.enseignant_id for a in affs]

    next_week_date = lundi + timedelta(days=7)
    
    return render_template('admin/planning.html', title=f'Planification - {current_formation.nom}', 
                           form=form, grid_data=grid_data, 
                           dates=dates_uniques, creneaux=creneaux_uniques, 
                           groupes=groupes_tries, enseignants=enseignants_all,
                           modules=modules_form, allowed_instructors=allowed_instructors,
                           groupes_form=groupes_form, formations=formations_all,
                           current_formation=current_formation, salles=salles_all,
                           prev_week=prev_week, next_week=next_week_date,
                           lundi=lundi, monday=lundi, samedi=samedi, today_str=today_str,
                           modules_data=modules_data, salles_data=salles_data)

@admin_bp.route('/delete_seance/<int:id>', methods=['POST'])
@login_required
def delete_seance(id):
    if not current_user.is_admin():
        flash('Accès refusé.', 'danger')
        return redirect(url_for('student.dashboard'))
    
    seance = Seance.query.get_or_404(id)
    fid = seance.module.formation_id
    # Protection : ne pas supprimer une séance passée
    if seance.date_seance < date.today():
        flash('Impossible de supprimer une séance passée (historique protégé).', 'warning')
        return redirect(url_for('admin.planning', fid=fid))
    
    # NOTIFICATION
    msg = f"Votre séance de {seance.module.code} du {seance.date_seance.strftime('%d/%m')} à {seance.heure_debut.strftime('%H:%M')} a été SUPPRIMÉE."
    notify_seance_change(seance, msg, 'danger')
        
    db.session.delete(seance)
    db.session.commit()
    flash('Séance supprimée.', 'info')
    return redirect(url_for('admin.planning', fid=fid))

@admin_bp.route('/update_seance_enseignant', methods=['POST'])
@login_required
def update_seance_enseignant():
    if not current_user.is_admin():
        flash('Accès refusé.', 'danger')
        return redirect(url_for('student.dashboard'))
    
    seance_id = request.form.get('seance_id')
    enseignant_id = request.form.get('enseignant_id')
    
    if not seance_id: return redirect(url_for('admin.planning'))
    seance = Seance.query.get_or_404(seance_id)
    fid = seance.module.formation_id
    
    if enseignant_id:
        ens_id = int(enseignant_id)
        # 1. VÉRIFICATION COLLISION
        ok, reason = check_seance_collisions(seance.date_seance, seance.heure_debut, seance.duree, seance.groupe, ens_id, seance.salle_id, fid, exclude_id=seance.id)
        if not ok:
            flash(f"Collision Enseignant : {reason}", "danger")
            return redirect(url_for('admin.planning', fid=fid))

        # 2. VÉRIFICATION QUOTA (Warning uniquement)
        aff = Affectation.query.filter_by(module_id=seance.module_id, enseignant_id=ens_id).first()
        if not aff:
            flash(f"Cet enseignant n'est pas affecté au module {seance.module.code}.", "warning")
        else:
            deja_fait = sum([s.duree for s in Seance.query.filter_by(module_id=seance.module_id, enseignant_id=ens_id, type_seance=seance.type_seance).all() if s.id != seance.id])
            quota = getattr(aff, f"{seance.type_seance.lower()}_heures")
            if deja_fait + seance.duree > quota:
                flash(f"Attention : Dépassement de quota pour {aff.enseignant.nom} ({deja_fait + seance.duree}/{quota}h).", "warning")
            
        seance.enseignant_id = ens_id
        # NOTIFICATION
        msg = f"L'enseignant de votre séance de {seance.module.code} du {seance.date_seance.strftime('%d/%m')} à {seance.heure_debut.strftime('%H:%M')} a été modifié."
        notify_seance_change(seance, msg, 'info')
    else:
        seance.enseignant_id = None
        
    db.session.commit()
    flash('Enseignant mis à jour.', 'success')
    return redirect(url_for('admin.planning', fid=fid))

@admin_bp.route('/update_seance_salle', methods=['POST'])
@login_required
def update_seance_salle():
    if not current_user.is_admin():
        flash('Accès refusé.', 'danger')
        return redirect(url_for('student.dashboard'))
    
    seance_id = request.form.get('seance_id')
    salle_id = request.form.get('salle_id')
    
    if not seance_id or not salle_id: return redirect(url_for('admin.planning'))
    
    seance = Seance.query.get_or_404(seance_id)
    sid = int(salle_id)
    fid = seance.module.formation_id
    
    # VÉRIFICATION DE DISPONIBILITÉ
    ok, reason = check_seance_collisions(seance.date_seance, seance.heure_debut, seance.duree, seance.groupe, seance.enseignant_id, sid, fid, exclude_id=seance.id)
    if not ok:
        flash(f"Collision Salle : {reason}", "danger")
        return redirect(url_for('admin.planning', fid=fid))

    seance.salle_id = sid
    # NOTIFICATION
    msg = f"La salle de votre séance de {seance.module.code} du {seance.date_seance.strftime('%d/%m')} à {seance.heure_debut.strftime('%H:%M')} a été modifiée : {seance.salle.nom}."
    notify_seance_change(seance, msg, 'info')
    
    db.session.commit()
    flash('Salle mise à jour.', 'success')
    return redirect(url_for('admin.planning', fid=fid))

@admin_bp.route('/update_seance_module', methods=['POST'])
@login_required
def update_seance_module():
    if not current_user.is_admin():
        flash('Accès refusé.', 'danger')
        return redirect(url_for('student.dashboard'))
    
    seance_id = request.form.get('seance_id')
    module_id = request.form.get('module_id')
    
    seance = Seance.query.get_or_404(seance_id)
    fid = seance.module.formation_id
    seance.module_id = module_id
    # On reset l'enseignant car il pourrait ne pas être affecté au nouveau module
    seance.enseignant_id = None 
    # NOTIFICATION
    msg = f"Le module de votre séance du {seance.date_seance.strftime('%d/%m')} à {seance.heure_debut.strftime('%H:%M')} a été modifié."
    notify_seance_change(seance, msg, 'info')
    
    db.session.commit()
    
    flash('Module mis à jour pour cette séance. N\'oubliez pas d\'assigner un enseignant.', 'info')
    return redirect(url_for('admin.planning', fid=fid))

def choose_best_teacher_for_session(module_id, type_seance, date_s, time_s, duree):
    """
    Choisit le meilleur enseignant pour une séance donnée.
    Critères : 
    1. Doit être affecté au module.
    2. Doit être libre sur le créneau (pas de collision).
    3. Priorité à celui qui a le plus de quota restant pour ce type de séance.
    Retourne (enseignant_id, is_overload) ou (None, False).
    """
    # 1. Récupérer toutes les affectations pour ce module
    affs = Affectation.query.filter_by(module_id=module_id).all()
    if not affs:
        return None, False

    candidates = []
    for a in affs:
        # Quota affecté pour ce type
        assigned = 0.0
        if type_seance == 'CM': assigned = a.cm_heures
        elif type_seance == 'TD': assigned = a.td_heures
        elif type_seance == 'TP': assigned = a.tp_heures
        
        # Volume déjà planifié (dans la base actuelle)
        # Note: On compte aussi les séances qui viennent d'être ajoutées dans la session db
        planned = db.session.query(db.func.sum(Seance.duree)).filter_by(
            enseignant_id=a.enseignant_id,
            module_id=module_id,
            type_seance=type_seance
        ).scalar() or 0.0
        
        remaining = assigned - planned
        
        # Vérification de collision temporelle
        collision = Seance.query.filter_by(
            date_seance=date_s,
            heure_debut=time_s,
            enseignant_id=a.enseignant_id
        ).first()
        
        if not collision:
            candidates.append({
                'id': a.enseignant_id,
                'remaining': remaining
            })
    
    if not candidates:
        return None, False
        
    # Tri par quota restant décroissant (le plus disponible en premier)
    candidates.sort(key=lambda x: x['remaining'], reverse=True)
    
    best = candidates[0]
    is_overload = best['remaining'] < duree
    return best['id'], is_overload

    flash('Module mis à jour pour cette séance. N\'oubliez pas d\'assigner un enseignant.', 'info')
    return redirect(url_for('admin.planning', fid=fid))

# --- GÉNÉRATION AUTOMATIQUE AVANCÉE ---

def get_generation_tasks(formation, structure):
    """
    Identifie tous les besoins en séances (tasks) pour une formation donnée.
    Trie les tâches par difficulté (CM en premier, puis moins de profs disponibles).
    """
    tasks = []
    modules = Module.query.filter_by(formation_id=formation.id).all()
    
    for mod in modules:
        # On calcule les besoins restants
        # CM
        planned_cm = db.session.query(db.func.sum(Seance.duree)).filter_by(module_id=mod.id, type_seance='CM').scalar() or 0.0
        needed_cm = mod.cm_heures - planned_cm
        while needed_cm > 0.01:
            duree = min(2.0, needed_cm)
            tasks.append({'module': mod, 'type': 'CM', 'gp': 'CM', 'duree': duree})
            needed_cm -= duree
            
        # TD
        for gp in structure['all_td']:
            planned = db.session.query(db.func.sum(Seance.duree)).filter_by(module_id=mod.id, type_seance='TD', groupe=gp).scalar() or 0.0
            needed = mod.td_heures - planned
            while needed > 0.01:
                duree = min(2.0, needed)
                tasks.append({'module': mod, 'type': 'TD', 'gp': gp, 'duree': duree})
                needed -= duree
                
        # TP
        for gp in structure['all_tp']:
            planned = db.session.query(db.func.sum(Seance.duree)).filter_by(module_id=mod.id, type_seance='TP', groupe=gp).scalar() or 0.0
            needed = mod.tp_heures - planned
            while needed > 0.01:
                duree = min(2.0, needed)
                tasks.append({'module': mod, 'type': 'TP', 'gp': gp, 'duree': duree})
                needed -= duree

    # Calcul de la difficulté pour le tri
    # 1. CM est plus dur (bloque tout le monde)
    # 2. Nombre de profs affectés au module (moins de profs = plus dur)
    for t in tasks:
        aff_count = Affectation.query.filter_by(module_id=t['module'].id).count()
        t['priority'] = (0 if t['type'] == 'CM' else (1 if t['type'] == 'TD' else 2))
        t['difficulty'] = aff_count if aff_count > 0 else 99

    # Tri : Priorité (CM > TD > TP), puis Difficulté (moins de profs en premier)
    tasks.sort(key=lambda x: (x['priority'], x['difficulty']))
    return tasks

def score_combination(teacher_id, slot, day, task, state):
    """
    Calcule un score de pertinence pour une combinaison (prof, créneau).
    Plus le score est élevé, meilleure est la combinaison.
    """
    score = 1000
    
    # 1. Préférer les profs qui ont encore beaucoup de quota (équilibre)
    remaining = state['quotas'].get((teacher_id, task['module'].id, task['type']), 0.0)
    score += remaining * 10
    
    # 2. Pénalité légère pour les créneaux tardifs
    if slot == time(16, 0): score -= 10
    
    # 3. Éviter de trop charger une journée pour un prof
    load_day = state['teacher_load_per_day'].get((teacher_id, day), 0.0)
    score -= load_day * 50
    
    return score

@admin_bp.route('/generate_planning', methods=['POST'])
@login_required
def generate_planning():
    if not current_user.is_admin():
        flash('Accès refusé.', 'danger')
        return redirect(url_for('student.dashboard'))

    fid = request.args.get('fid', type=int)
    allow_overload = request.form.get('allow_overload') == 'on'
    
    if not fid:
        return redirect(url_for('admin.planning'))

    formation = Formation.query.get_or_404(fid)
    structure = build_group_structure(formation)
    
    # --- PRÉPARATION ---
    date_charniere = date.today() + timedelta(days=1)
    # Nettoyage des séances futures de cette formation
    seances_a_suppr = Seance.query.join(Module).filter(
        Module.formation_id == fid, 
        Seance.date_seance >= date_charniere
    ).all()
    for s in seances_a_suppr:
        db.session.delete(s)
    db.session.commit()
    
    # Chargement de l'état global pour éviter les requêtes en boucle
    all_salles = Salle.query.all()
    all_seances = Seance.query.all() # Toutes les séances du système (pour les collisions prof/salle)
    all_affectations = Affectation.query.all()
    
    # Dictionnaires d'état pour un accès rapide
    state = {
        'busy_teachers': {}, # {(date, time): [ids]}
        'busy_salles': {},   # {(date, time): [ids]}
        'busy_groups': {},   # {(date, time, formation_id): [names]}
        'quotas': {},        # {(enseignant_id, module_id, type): total_assigné}
        'planned': {},       # {(enseignant_id, module_id, type): total_planifié}
        'teacher_load_per_day': {}, # {(enseignant_id, date): total_heures}
        'eligible_teachers': {} # {module_id: [enseignant_ids]}
    }
    
    # Initialisation des quotas et profs éligibles
    for aff in all_affectations:
        if aff.module_id not in state['eligible_teachers']: state['eligible_teachers'][aff.module_id] = []
        state['eligible_teachers'][aff.module_id].append(aff.enseignant_id)
        state['quotas'][(aff.enseignant_id, aff.module_id, 'CM')] = aff.cm_heures
        state['quotas'][(aff.enseignant_id, aff.module_id, 'TD')] = aff.td_heures
        state['quotas'][(aff.enseignant_id, aff.module_id, 'TP')] = aff.tp_heures
        state['planned'][(aff.enseignant_id, aff.module_id, 'CM')] = 0.0
        state['planned'][(aff.enseignant_id, aff.module_id, 'TD')] = 0.0
        state['planned'][(aff.enseignant_id, aff.module_id, 'TP')] = 0.0

    # Remplissage des occupations actuelles (historique et autres formations)
    for s in all_seances:
        d, t = s.date_seance, s.heure_debut
        if (d, t) not in state['busy_teachers']: state['busy_teachers'][(d, t)] = []
        if (d, t) not in state['busy_salles']: state['busy_salles'][(d, t)] = []
        if (d, t, s.module.formation_id) not in state['busy_groups']: state['busy_groups'][(d, t, s.module.formation_id)] = []
        
        if s.enseignant_id: 
            state['busy_teachers'][(d, t)].append(s.enseignant_id)
            # On met à jour le déjà planifié pour les quotas
            key = (s.enseignant_id, s.module_id, s.type_seance)
            state['planned'][key] = state['planned'].get(key, 0.0) + s.duree
            # Charge journalière
            state['teacher_load_per_day'][(s.enseignant_id, d)] = state['teacher_load_per_day'].get((s.enseignant_id, d), 0.0) + s.duree
            
        if s.salle_id: state['busy_salles'][(d, t)].append(s.salle_id)
        
        # Pour les groupes, on gère la hiérarchie CM/TD/TP
        f_id = s.module.formation_id
        g_name = s.groupe
        state['busy_groups'][(d, t, f_id)].append(g_name)
        if g_name == 'CM':
            # CM bloque tous les groupes de la formation
            pass # On gérera ça au test de collision

    tasks = get_generation_tasks(formation, structure)
    
    # Aliases catégories
    info_aliases = ['python', 'linux', 'programation', 'programmation', 'bdd', 'info', 'logiciel', 'c', 'java', 'reseau', 'web', 'donnees', 'base de données']
    time_slots = [time(8, 0), time(10, 0), time(14, 0), time(16, 0)]
    
    report = {
        'success': 0,
        'failed': [], # list of {task, reason}
        'overload': 0
    }

    # --- BOUCLE DE GÉNÉRATION ---
    for task in tasks:
        best_candidate = None
        best_score = -99999
        
        # Déterminer la catégorie cible
        m_cat = task['module'].categorie.lower().strip() if task['module'].categorie else ""
        if not m_cat:
            libelle = task['module'].libelle.lower()
            if any(k in libelle for k in info_aliases): m_cat = 'info'
            elif 'anglais' in libelle: m_cat = 'anglais'
            elif 'physique' in libelle: m_cat = 'physique'

        eligible_profs = state['eligible_teachers'].get(task['module'].id, [])
        
        # On cherche un créneau sur 90 jours
        found_task = False
        reason = "Aucun créneau ou enseignant disponible respectant les contraintes"

        for day_offset in range(90):
            if found_task: break
            current_d = date_charniere + timedelta(days=day_offset)
            if current_d.weekday() >= 5: continue # Weekend
            
            for t_slot in time_slots:
                if found_task: break
                
                # 1. Test Disponibilité Groupe (formation locale)
                busy_gps = state['busy_groups'].get((current_d, t_slot, fid), [])
                if 'CM' in busy_gps: continue
                if task['gp'] == 'CM' and len(busy_gps) > 0: continue
                if task['gp'] in busy_gps: continue
                # Hiérarchie TD/TP
                parent_td = structure['tp_to_td'].get(task['gp'])
                if parent_td and parent_td in busy_gps: continue
                tp_children = structure['td_to_tp'].get(task['gp'], [])
                if any(child in busy_gps for child in tp_children): continue
                
                # 2. Trouver les enseignants éligibles libres et avec quota
                for prof_id in eligible_profs:
                    # Libre ?
                    if prof_id in state['busy_teachers'].get((current_d, t_slot), []):
                        continue
                    
                    # Quota ?
                    q_key = (prof_id, task['module'].id, task['type'])
                    rem = state['quotas'].get(q_key, 0.0) - state['planned'].get(q_key, 0.0)
                    is_overload_candidate = rem < task['duree']
                    
                    if is_overload_candidate and not allow_overload:
                        reason = "Quota enseignant épuisé (surcharges désactivées)"
                        continue
                        
                    # 3. Trouver une salle libre compatible
                    salle_id = None
                    for sl in all_salles:
                        if sl.id in state['busy_salles'].get((current_d, t_slot), []): continue
                        
                        # Compatibilité type
                        if task['type'] == 'CM' and sl.type_salle != 'Amphi': continue
                        if task['type'] == 'TD' and sl.type_salle != 'TD': continue
                        if task['type'] == 'TP' and sl.type_salle != 'TP': continue
                        
                        # Compatibilité catégorie TP
                        if task['type'] == 'TP' and m_cat:
                            r_cat = sl.categorie.lower().strip() if sl.categorie else ""
                            if m_cat in info_aliases:
                                if r_cat != 'info': continue
                            elif r_cat != m_cat: continue
                        
                        salle_id = sl.id
                        break # On prend la première salle libre trouvée pour ce slot/prof
                    
                    if not salle_id:
                        if reason == "Quota enseignant épuisé (surcharges désactivées)": pass
                        else: reason = "Aucune salle compatible disponible sur ce créneau"
                        continue

                    # On a une combinaison valide ! On calcule son score
                    candidate_score = score_combination(prof_id, t_slot, current_d, task, state)
                    if candidate_score > best_score:
                        best_score = candidate_score
                        best_candidate = {
                            'date': current_d,
                            'slot': t_slot,
                            'prof': prof_id,
                            'salle': salle_id,
                            'overload': is_overload_candidate
                        }
                        found_task = True # On s'arrête au premier créneau où on trouve des profs, pour limiter la recherche
                        # Mais on continue de tester les autres profs du même créneau pour prendre le meilleur score

        if best_candidate:
            # Création de la séance
            new_s = Seance(
                module_id=task['module'].id,
                enseignant_id=best_candidate['prof'],
                type_seance=task['type'],
                groupe=task['gp'],
                date_seance=best_candidate['date'],
                heure_debut=best_candidate['slot'],
                duree=task['duree'],
                salle_id=best_candidate['salle']
            )
            db.session.add(new_s)
            
            # Mise à jour de l'état local pour les prochaines tâches
            d, t, p, s = best_candidate['date'], best_candidate['slot'], best_candidate['prof'], best_candidate['salle']
            if (d, t) not in state['busy_teachers']: state['busy_teachers'][(d, t)] = []
            state['busy_teachers'][(d, t)].append(p)
            if (d, t) not in state['busy_salles']: state['busy_salles'][(d, t)] = []
            state['busy_salles'][(d, t)].append(s)
            if (d, t, fid) not in state['busy_groups']: state['busy_groups'][(d, t, fid)] = []
            state['busy_groups'][(d, t, fid)].append(task['gp'])
            
            key = (p, task['module'].id, task['type'])
            state['planned'][key] = state['planned'].get(key, 0.0) + task['duree']
            state['teacher_load_per_day'][(p, d)] = state['teacher_load_per_day'].get((p, d), 0.0) + task['duree']
            
            report['success'] += 1
            if best_candidate['overload']: report['overload'] += 1
        else:
            report['failed'].append({'task': task, 'reason': reason})

    db.session.commit()
    
    # --- RAPPORT FINAL ---
    msg_success = f"Génération terminée : {report['success']} séances créées."
    if report['overload'] > 0:
        msg_success += f" ({report['overload']} en surcharge)."
    flash(msg_success, "success")
    notify_admin(msg_success, 'success')
    
    if report['failed']:
        flash(f"⚠️ {len(report['failed'])} séances n'ont pas pu être générées.", "warning")
        notify_admin(f"{len(report['failed'])} échecs lors de la génération auto.", 'warning')
        # Regroupement par raison pour plus de clarté
        reasons_summary = {}
        for f in report['failed']:
            r = f['reason']
            reasons_summary[r] = reasons_summary.get(r, 0) + 1
        
        for r, count in reasons_summary.items():
            flash(f" - {count} échecs : {r}", "info")
            
    return redirect(url_for('admin.planning', fid=fid))

@admin_bp.route('/export/csv/<type_export>')
@login_required
def export_csv(type_export):
    if not current_user.is_admin():
        flash('Accès refusé.', 'danger')
        return redirect(url_for('student.dashboard'))
        
    from app.exports import generate_csv_response
    
    if type_export == 'modules':
        fid = request.args.get('fid', type=int)
        query = Module.query
        if fid:
            query = query.filter_by(formation_id=fid)
        modules = query.order_by(Module.code).all()
        # Colonnes en minuscules = directement réimportables
        header = ['code', 'libelle', 'categorie', 'formation', 'cm_heures', 'td_heures', 'tp_heures']
        rows = [[m.code, m.libelle, m.categorie or '', m.formation.nom if m.formation else '', m.cm_heures, m.td_heures, m.tp_heures] for m in modules]
        return generate_csv_response('modules.csv', header, rows)
        
    elif type_export == 'salles':
        salles = Salle.query.order_by(Salle.nom).all()
        header = ['nom', 'type_salle', 'categorie', 'capacite']
        rows = [[s.nom, s.type_salle, s.categorie or '', s.capacite or ''] for s in salles]
        return generate_csv_response('salles.csv', header, rows)
        
    elif type_export == 'affectations':
        affectations = Affectation.query.join(Enseignant).join(Module).order_by(Enseignant.nom, Enseignant.prenom).all()
        # Colonnes séparées nom/prénom = directement réimportables
        header = ['enseignant_nom', 'enseignant_prenom', 'module_code', 'cm_heures', 'td_heures', 'tp_heures']
        rows = [[a.enseignant.nom, a.enseignant.prenom, a.module.code, a.cm_heures, a.td_heures, a.tp_heures] for a in affectations]
        return generate_csv_response('affectations.csv', header, rows)
        
    elif type_export == 'enseignants':
        enseignants = Enseignant.query.order_by(Enseignant.nom, Enseignant.prenom).all()
        header = ['nom', 'prenom']
        rows = [[e.nom, e.prenom] for e in enseignants]
        return generate_csv_response('enseignants.csv', header, rows)
        
    elif type_export == 'seances':
        fid = request.args.get('fid', type=int)
        query = Seance.query.join(Module).order_by(Seance.date_seance, Seance.heure_debut)
        if fid:
            query = query.filter(Module.formation_id == fid)
        seances = query.all()
        header = ['Date', 'Heure Début', 'Heure Fin', 'Module', 'Type', 'Groupe', 'Enseignant', 'Salle', 'Formation']
        rows = [[s.date_seance.strftime('%Y-%m-%d'), s.heure_debut.strftime('%H:%M'), s.heure_fin.strftime('%H:%M'), 
                 s.module.code, s.type_seance, s.groupe, s.enseignant.nom_complet() if s.enseignant else 'N/A', 
                 s.salle.nom if s.salle else 'N/A', s.module.formation.nom if s.module.formation else ''] for s in seances]
        return generate_csv_response('seances.csv', header, rows)
        
    flash('Type d\'export invalide.', 'danger')
    return redirect(url_for('admin.dashboard'))

@admin_bp.route('/export/pdf/planning/<int:fid>')
@login_required
def export_pdf_planning(fid):
    if not current_user.is_admin():
        flash('Accès refusé.', 'danger')
        return redirect(url_for('student.dashboard'))
        
    from app.exports import generate_pdf_response
    formation = Formation.query.get_or_404(fid)
    
    seances = Seance.query.join(Module).filter(Module.formation_id == fid).order_by(Seance.date_seance, Seance.heure_debut).all()
    if not seances:
        flash('Aucune séance à exporter.', 'warning')
        return redirect(url_for('admin.planning', fid=fid))
        
    title = f'Emploi du Temps Global - {formation.nom}'
    return generate_pdf_response(f'planning_{formation.nom}.pdf', title, seances)

@admin_bp.route('/import/template/<type_import>')
@login_required
def import_template(type_import):
    if not current_user.is_admin():
        flash('Accès refusé.', 'danger')
        return redirect(url_for('student.dashboard'))
        
    from app.exports import generate_csv_response
    
    if type_import == 'modules':
        header = ['code', 'libelle', 'categorie', 'formation', 'cm_heures', 'td_heures', 'tp_heures']
        rows = [['M2103', 'Bases de données', 'Info', 'BUT1', '10', '15', '20'],
                ['M2104', 'Algorithmique', '', 'BUT1', '15', '10', '0']]
        return generate_csv_response('modele_modules.csv', header, rows)
    elif type_import == 'enseignants':
        # Pas d\'email en base (modèle Enseignant : nom, prenom uniquement)
        header = ['nom', 'prenom']
        rows = [['DUPONT', 'Jean'], ['MARTIN', 'Sophie']]
        return generate_csv_response('modele_enseignants.csv', header, rows)
    elif type_import == 'salles':
        header = ['nom', 'type_salle', 'categorie', 'capacite']
        rows = [['A101', 'TD', '', '30'],
                ['B202', 'TP', 'Info', '20'],
                ['Amphi 1', 'Amphi', '', '200']]
        return generate_csv_response('modele_salles.csv', header, rows)
    elif type_import == 'affectations':
        header = ['enseignant_nom', 'enseignant_prenom', 'module_code', 'cm_heures', 'td_heures', 'tp_heures']
        rows = [['DUPONT', 'Jean', 'M2103', '10', '15', '0'],
                ['MARTIN', 'Sophie', 'M2104', '15', '0', '0']]
        return generate_csv_response('modele_affectations.csv', header, rows)
        
    flash('Type de gabarit invalide.', 'danger')
    return redirect(url_for('admin.dashboard'))

@admin_bp.route('/import/<type_import>', methods=['POST'])
@login_required
def import_csv(type_import):
    if not current_user.is_admin():
        flash('Accès refusé.', 'danger')
        return redirect(url_for('student.dashboard'))
        
    if 'file' not in request.files:
        flash('Aucun fichier sélectionné.', 'danger')
        return redirect(request.referrer or url_for('admin.dashboard'))
        
    file = request.files['file']
    if file.filename == '':
        flash('Aucun fichier sélectionné.', 'danger')
        return redirect(request.referrer or url_for('admin.dashboard'))
        
    if not file.filename.endswith('.csv'):
        flash('Le fichier doit être au format CSV.', 'danger')
        return redirect(request.referrer or url_for('admin.dashboard'))

    from app.imports import import_modules_from_csv, import_enseignants_from_csv, import_salles_from_csv, import_affectations_from_csv
    
    file_content = file.read()
    success, duplicates, errors, total = 0, 0, [], 0
    
    if type_import == 'modules':
        success, duplicates, errors, total = import_modules_from_csv(file_content)
    elif type_import == 'enseignants':
        success, duplicates, errors, total = import_enseignants_from_csv(file_content)
    elif type_import == 'salles':
        success, duplicates, errors, total = import_salles_from_csv(file_content)
    elif type_import == 'affectations':
        success, duplicates, errors, total = import_affectations_from_csv(file_content)
    else:
        flash('Type d\'import invalide.', 'danger')
        return redirect(request.referrer or url_for('admin.dashboard'))

    # Rapport d\'import détaillé
    rejected = len(errors) - duplicates  # erreurs réelles (hors doublons)
    rapport = f'Rapport d\'import : {total} ligne(s) lue(s), {success} importée(s)'
    if duplicates:
        rapport += f', {duplicates} doublon(s) / mise(s) à jour'
    if rejected > 0:
        rapport += f', {rejected} rejetée(s)'
    
    if success > 0:
        flash(rapport, 'success')
    elif total > 0:
        flash(rapport, 'warning')
    else:
        flash('Aucune ligne lue. Le fichier était peut-être vide.', 'info')
    
    # Affiche les erreurs détaillées (max 15)
    real_errors = [e for e in errors if 'ignoré' not in e.lower() and 'mise à jour' not in e.lower()]
    for err in real_errors[:15]:
        flash(err, 'danger')
    if len(real_errors) > 15:
        flash(f'... et {len(real_errors) - 15} autres erreurs (voir logs).', 'danger')
        
    return redirect(request.referrer or url_for('admin.dashboard'))
