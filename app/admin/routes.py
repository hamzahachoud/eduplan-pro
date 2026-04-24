from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required, current_user
from app.extensions import db
from app.models import User, Formation, Module, Enseignant, Affectation, Seance, Salle
from app.admin.forms import LoginForm, FormationForm, ModuleForm, EnseignantForm, AffectationForm, SeanceForm, SalleForm
from urllib.parse import urlsplit
from datetime import date, time, datetime, timedelta

admin_bp = Blueprint('admin', __name__)

from app.extensions import db
from app.models import User

@admin_bp.route('/init-db')
def init_db_route():
    db.create_all()

    # créer un admin
    admin = User(email="admin@test.com", role="admin")
    admin.set_password("admin123")

    db.session.add(admin)
    db.session.commit()

    return "Base de données initialisée !"

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
    return redirect(url_for('admin.login'))

@admin_bp.route('/')
@admin_bp.route('/dashboard')
@login_required
def dashboard():
    if not current_user.is_admin():
        flash('Accès refusé.', 'danger')
        return redirect(url_for('student.dashboard'))
    
    stats = {
        'formations_count': Formation.query.count(),
        'modules_count': Module.query.count(),
        'enseignants_count': Enseignant.query.count(),
        'seances_count': Seance.query.count()
    }
    return render_template('admin/dashboard.html', title='Dashboard', stats=stats)

@admin_bp.route('/formations', methods=['GET', 'POST'])
@login_required
def formations():
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

@admin_bp.route('/modules', methods=['GET', 'POST'])
@login_required
def modules():
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
    
    modules_list = Module.query.all()
    return render_template('admin/modules.html', title='Gestion des Modules', form=form, modules=modules_list)

@admin_bp.route('/delete_module/<int:id>')
@login_required
def delete_module(id):
    if not current_user.is_admin():
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

    enseignants_list = Enseignant.query.all()
    # Calcul des stats de charge pour chaque enseignant
    stats_profs = []
    for ens in enseignants_list:
        affectations = Affectation.query.filter_by(enseignant_id=ens.id).all()
        # Heures totales affectées (Maquette)
        total_affecte = sum([(a.cm_heures + a.td_heures + a.tp_heures) for a in affectations])
        # Heures déjà planifiées dans Seance
        total_planifie = sum([s.duree for s in Seance.query.filter_by(enseignant_id=ens.id).all()])
        
        stats_profs.append({
            'enseignant': ens,
            'total_affecte': total_affecte,
            'total_planifie': total_planifie,
            'reste': max(0, total_affecte - total_planifie),
            'h_sup': max(0, total_planifie - total_affecte),
            'percent': int((total_planifie / total_affecte * 100)) if total_affecte > 0 else 0
        })

    affectations_list = Affectation.query.all()
    return render_template('admin/enseignants.html', title='Enseignants & Affectations', 
                           form_enseignant=form_enseignant, form_affectation=form_affectation, 
                           enseignants=enseignants_list, affectations=affectations_list,
                           stats_profs=stats_profs)
                           
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
    
    salles_list = Salle.query.all()
    return render_template('admin/salles.html', title='Gestion des Salles', form=form, salles=salles_list)

@admin_bp.route('/delete_salle/<int:id>')
@login_required
def delete_salle(id):
    if not current_user.is_admin():
        return redirect(url_for('student.dashboard'))
    
    salle = Salle.query.get_or_404(id)
    db.session.delete(salle)
    db.session.commit()
    flash('Salle supprimée.', 'info')
    return redirect(url_for('admin.salles'))


@admin_bp.route('/planning', methods=['GET', 'POST'])
@admin_bp.route('/planning/<int:fid>', methods=['GET', 'POST'])
@login_required
def planning(fid=None):
    form = SeanceForm()
    
    if form.validate_on_submit():
        d = form.date_seance.data
        t = form.heure_debut.data
        g = form.groupe.data
        e = form.enseignant_id.data
        salle_id = form.salle_id.data
        duree = form.duree.data
        type_seance = form.type_seance.data
        module = Module.query.get(form.module_id.data)
        
        # LOGIQUE CLÉ : Vérification des quotas par GROUPE
        # Chaque groupe (TD1, TP1A, etc.) doit recevoir le volume horaire prévu dans la maquette.
        quota_max = 0
        if type_seance == 'CM':
            quota_max = module.cm_heures
        elif type_seance == 'TD':
            if module.td_heures <= 0:
                flash(f"Erreur : Le module {module.code} ne prévoit pas de séances de type TD dans sa maquette.", "danger")
                return redirect(url_for('admin.planning'))
            quota_max = module.td_heures
        elif type_seance == 'TP':
            if module.tp_heures <= 0:
                flash(f"Erreur : Le module {module.code} ne prévoit pas de séances de type TP dans sa maquette.", "danger")
                return redirect(url_for('admin.planning'))
            quota_max = module.tp_heures

        if type_seance == 'CM' and module.cm_heures <= 0:
            flash(f"Erreur : Le module {module.code} ne prévoit pas de séances de type CM dans sa maquette.", "danger")
            return redirect(url_for('admin.planning'))

        # Calculer le total des heures déjà planifiées UNIQUEMENT pour ce groupe spécifique
        seances_groupe = Seance.query.filter_by(module_id=module.id, type_seance=type_seance, groupe=g).all()
        heures_deja_planifiees = sum([s.duree for s in seances_groupe])
        
        if heures_deja_planifiees + duree > quota_max:
            flash(f'Erreur QUOTA : Le groupe {g} a déjà atteint son volume max pour ce type de séance ({heures_deja_planifiees}/{quota_max}h).', 'danger')
            return redirect(url_for('admin.planning'))

        # 1. VERIFICATION COLLISION GROUPE (OU CM QUI BLOQUE TOUT)
        # Calculer l'intervalle de la nouvelle séance
        new_start_dt = datetime.combine(d, t)
        new_end_dt = new_start_dt + timedelta(hours=duree)
        new_start = new_start_dt.time()
        new_end = new_end_dt.time()

        # On récupère toutes les séances du jour pour filtrer en Python (plus simple pour les propriétés calculées)
        seances_du_jour = Seance.query.filter_by(date_seance=d).all()

        for s in seances_du_jour:
            # Vérifier le chevauchement d'intervalle : (S1 < E2) AND (S2 < E1)
            if s.heure_debut < new_end and s.heure_fin > new_start:
                # Il y a un chevauchement temporel. Vérifions maintenant les groupes.
                parent_td = None
                if g.startswith('TP'): parent_td = f'TD{g[2]}'
                
                # Collision si : même groupe, ou l'un est CM, ou hiérarchie TD/TP
                if (s.groupe == g or s.groupe == 'CM' or g == 'CM' or 
                    (parent_td and s.groupe == parent_td) or
                    (s.groupe.startswith('TD') and g.startswith(f'TP{s.groupe[2]}'))):
                    
                    flash(f"Collision détectée : Le groupe {g} est déjà occupé (ou bloqué par un CM) de {s.heure_debut.strftime('%H:%M')} à {s.heure_fin.strftime('%H:%M')}.", "danger")
                    return redirect(url_for('admin.planning', fid=fid))

                # 2. VERIFICATION CONFLIT ENSEIGNANT
                if e and s.enseignant_id == int(e):
                    flash(f"Conflit Enseignant : {s.enseignant.nom} est déjà en cours avec le groupe {s.groupe} jusqu'à {s.heure_fin.strftime('%H:%M')}.", "danger")
                    return redirect(url_for('admin.planning', fid=fid))
                
                # 3. VERIFICATION CONFLIT SALLE
                if int(salle_id) == s.salle_id:
                    flash(f"Conflit Salle : La salle {s.salle.nom} est déjà occupée par le groupe {s.groupe} jusqu'à {s.heure_fin.strftime('%H:%M')}.", "danger")
                    return redirect(url_for('admin.planning', fid=fid))

        if heures_deja_planifiees + duree > quota_max:
            flash(f'Attention : Dépassement de quota ! Total max pour {type_seance} = {quota_max}h. Déjà planifié : {heures_deja_planifiees}h. Séance enregistrée comme Heures Sup.', 'warning')
        
        seance = Seance(
            module_id=form.module_id.data,
            enseignant_id=e,
            type_seance=type_seance,
            groupe=g,
            date_seance=d,
            heure_debut=t,
            duree=duree,
            salle_id=salle_id
        )
        db.session.add(seance)
        db.session.commit()
        flash('Séance planifiée avec succès !', 'success')
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

    # Filtrage des données par formation
    seances_all = Seance.query.join(Module).filter(Module.formation_id == current_formation.id).order_by(Seance.date_seance, Seance.heure_debut).all()
    modules_form = Module.query.filter_by(formation_id=current_formation.id).all()
    
    # On récupère tous les groupes possibles POUR CETTE FORMATION spécifique
    groupes_tries = ['CM']
    for i in range(1, current_formation.nb_groupes_td + 1):
        groupes_tries.append(f'TD{i}')
    
    # Calcul des TP (TP1A, TP1B...)
    nb_tp_par_td = current_formation.nb_groupes_tp // current_formation.nb_groupes_td if current_formation.nb_groupes_td > 0 else 0
    for i in range(1, current_formation.nb_groupes_tp + 1):
        td_num = (i-1) // nb_tp_par_td + 1 if nb_tp_par_td > 0 else 1
        suffix = chr(65 + (i-1) % nb_tp_par_td) if nb_tp_par_td > 1 else ""
        groupes_tries.append(f'TP{td_num}{suffix}')
    
    # Liste des groupes pour le champ SELECT du formulaire de création
    groupes_form = groupes_tries.copy()
    
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

    return render_template('admin/planning.html', title=f'Planification - {current_formation.nom}', 
                           form=form, grid_data=grid_data, 
                           dates=dates_uniques, creneaux=creneaux_uniques, 
                           groupes=groupes_tries, enseignants=enseignants_all,
                           modules=modules_form, allowed_instructors=allowed_instructors,
                           groupes_form=groupes_form, formations=formations_all,
                           current_formation=current_formation, salles=salles_all,
                           modules_data=modules_data, salles_data=salles_data)

@admin_bp.route('/delete_seance/<int:id>')
@login_required
def delete_seance(id):
    if not current_user.is_admin():
        return redirect(url_for('student.dashboard'))
    
    seance = Seance.query.get_or_404(id)
    fid = seance.module.formation_id
    # Protection : ne pas supprimer une séance passée
    if seance.date_seance < date.today():
        flash('Impossible de supprimer une séance passée (historique protégé).', 'warning')
        return redirect(url_for('admin.planning', fid=fid))
        
    db.session.delete(seance)
    db.session.commit()
    flash('Séance supprimée.', 'info')
    return redirect(url_for('admin.planning', fid=fid))

@admin_bp.route('/update_seance_enseignant', methods=['POST'])
@login_required
def update_seance_enseignant():
    if not current_user.is_admin():
        return redirect(url_for('student.dashboard'))
    
    seance_id = request.form.get('seance_id')
    enseignant_id = request.form.get('enseignant_id')
    
    if not seance_id: return redirect(url_for('admin.planning'))
    
    seance = Seance.query.get_or_404(seance_id)
    fid = seance.module.formation_id
    
    if enseignant_id:
        # VÉRIFICATION DE QUOTA
        ens_id = int(enseignant_id)
        aff = Affectation.query.filter_by(module_id=seance.module_id, enseignant_id=ens_id).first()
        if not aff:
            flash(f"Cet enseignant n'est pas affecté au module {seance.module.code}.", "danger")
            return redirect(url_for('admin.planning', fid=fid))
            
        # VÉRIFICATION DE DISPONIBILITÉ (CONFLIT TEMPOREL)
        # On vérifie si le prof a un chevauchement avec une AUTRE séance
        S = seance.heure_debut
        E = seance.heure_fin
        conflit = Seance.query.filter(
            Seance.date_seance == seance.date_seance,
            Seance.enseignant_id == ens_id,
            Seance.id != seance.id # Ne pas se comparer à soi-même
        ).all()
        
        for c in conflit:
            if c.heure_debut < E and c.heure_fin > S:
                flash(f"Conflit : {aff.enseignant.nom} est déjà occupé de {c.heure_debut.strftime('%H:%M')} à {c.heure_fin.strftime('%H:%M')}.", "danger")
                return redirect(url_for('admin.planning', fid=fid))

        # Calculer l'utilisation actuelle
        deja_fait = sum([s.duree for s in Seance.query.filter_by(module_id=seance.module_id, enseignant_id=ens_id, type_seance=seance.type_seance).all() if s.id != seance.id])
        quota = 0
        if seance.type_seance == 'CM': quota = aff.cm_heures
        elif seance.type_seance == 'TD': quota = aff.td_heures
        elif seance.type_seance == 'TP': quota = aff.tp_heures
        
        if deja_fait + seance.duree > quota:
            flash(f"Attention : Dépassement de quota pour {aff.enseignant.nom} ({deja_fait + seance.duree}/{quota}h). Séance enregistrée en Heures Sup.", "warning")
            
        seance.enseignant_id = ens_id
    else:
        seance.enseignant_id = None
        
    db.session.commit()
    flash('Enseignant mis à jour.', 'success')
    return redirect(url_for('admin.planning', fid=fid))

@admin_bp.route('/update_seance_salle', methods=['POST'])
@login_required
def update_seance_salle():
    if not current_user.is_admin():
        return redirect(url_for('student.dashboard'))
    
    seance_id = request.form.get('seance_id')
    salle_id = request.form.get('salle_id')
    
    if not seance_id or not salle_id: return redirect(url_for('admin.planning'))
    
    seance = Seance.query.get_or_404(seance_id)
    sid = int(salle_id)
    fid = seance.module.formation_id
    
    # VÉRIFICATION DE DISPONIBILITÉ
    S = seance.heure_debut
    E = seance.heure_fin
    conflit = Seance.query.filter(
        Seance.date_seance == seance.date_seance,
        Seance.salle_id == sid,
        Seance.id != seance.id
    ).all()
    
    for c in conflit:
        if c.heure_debut < E and c.heure_fin > S:
            flash(f"Conflit Salle : La salle est déjà occupée de {c.heure_debut.strftime('%H:%M')} à {c.heure_fin.strftime('%H:%M')}.", "danger")
            return redirect(url_for('admin.planning', fid=fid))

    seance.salle_id = sid
    db.session.commit()
    flash('Salle mise à jour.', 'success')
    return redirect(url_for('admin.planning', fid=fid))

@admin_bp.route('/update_seance_module', methods=['POST'])
@login_required
def update_seance_module():
    if not current_user.is_admin():
        return redirect(url_for('student.dashboard'))
    
    seance_id = request.form.get('seance_id')
    module_id = request.form.get('module_id')
    
    seance = Seance.query.get_or_404(seance_id)
    fid = seance.module.formation_id
    seance.module_id = module_id
    # On reset l'enseignant car il pourrait ne pas être affecté au nouveau module
    seance.enseignant_id = None 
    db.session.commit()
    
    flash('Module mis à jour pour cette séance. N\'oubliez pas d\'assigner un enseignant.', 'info')
    return redirect(url_for('admin.planning', fid=fid))

@admin_bp.route('/generate_planning', methods=['POST'])
@login_required
def generate_planning():
    """
    LOGIQUE DE GÉNÉRATION AUTOMATIQUE
    Génère des séances CM, TD, TP pour remplir les quotas des modules.
    """
    if not current_user.is_admin():
        return redirect(url_for('student.dashboard'))

    fid = request.args.get('fid', type=int)
    if not fid:
        return redirect(url_for('admin.planning'))

    current_formation = Formation.query.get_or_404(fid)
    
    # On commence la planification à partir de demain
    date_charniere = date.today() + timedelta(days=1)
    # Suppression uniquement pour CETTE formation
    seances_a_suppr = Seance.query.join(Module).filter(Module.formation_id == fid, Seance.date_seance >= date_charniere).all()
    for s in seances_a_suppr:
        db.session.delete(s)
    
    start_date = date_charniere
    time_slots = [time(8, 0), time(10, 0), time(14, 0), time(16, 0)]
    
    modules = Module.query.filter_by(formation_id=fid).all()
    seances_creees = 0
    salles_all = Salle.query.all()
    nb_tp_par_td = current_formation.nb_groupes_tp // current_formation.nb_groupes_td if current_formation.nb_groupes_td > 0 else 0

    # Étape 1 : Lister tous les besoins (séances à créer)
    besoins = []
    for module in modules:
        # On récupère l'affectation par défaut pour le prof
        aff = Affectation.query.filter_by(module_id=module.id).first()
        ens_id = aff.enseignant_id if aff else None

        # CM
        deja_cm = sum([s.duree for s in Seance.query.filter_by(module_id=module.id, type_seance='CM').all()])
        a_faire_cm = module.cm_heures - deja_cm
        while a_faire_cm > 0:
            duree = min(2.0, a_faire_cm)
            besoins.append({'module': module, 'type': 'CM', 'gp': 'CM', 'duree': duree, 'ens': ens_id})
            a_faire_cm -= duree

        # TD
        for i in range(1, current_formation.nb_groupes_td + 1):
            gp = f'TD{i}'
            deja = sum([s.duree for s in Seance.query.filter_by(module_id=module.id, type_seance='TD', groupe=gp).all()])
            a_faire = module.td_heures - deja
            while a_faire > 0:
                duree = min(2.0, a_faire)
                besoins.append({'module': module, 'type': 'TD', 'gp': gp, 'duree': duree, 'ens': ens_id})
                a_faire -= duree

        # TP
        for i in range(1, current_formation.nb_groupes_tp + 1):
            td_num = (i-1) // nb_tp_par_td + 1 if nb_tp_par_td > 0 else 1
            suffix = chr(65 + (i-1) % nb_tp_par_td) if nb_tp_par_td > 1 else ""
            gp = f'TP{td_num}{suffix}'
            
            deja = sum([s.duree for s in Seance.query.filter_by(module_id=module.id, type_seance='TP', groupe=gp).all()])
            a_faire = module.tp_heures - deja
            while a_faire > 0:
                duree = min(2.0, a_faire)
                besoins.append({'module': module, 'type': 'TP', 'gp': gp, 'duree': duree, 'ens': ens_id})
                a_faire -= duree

    # Étape 2 : Planifier (Priorité CM, puis TD, puis TP)
    besoins.sort(key=lambda x: (x['type'] != 'CM', x['type'] != 'TD'))

    # Catégories de matières associées à l'informatique
    info_aliases = ['python', 'linux', 'programation', 'programmation', 'bdd', 'info', 'logiciel', 'c', 'java', 'reseau', 'web', 'donnees', 'base de données']

    for b in besoins:
        current_d = start_date
        planifie = False
        
        # On détermine la catégorie cible une seule fois pour cette séance
        m_cat = b['module'].categorie.lower().strip() if b['module'].categorie else ""
        if not m_cat:
            # Séance TP sans catégorie : Tentative de deviner d'après le nom du module
            libelle = b['module'].libelle.lower()
            if any(k in libelle for k in info_aliases):
                m_cat = 'info'
            elif 'anglais' in libelle:
                m_cat = 'anglais'
            elif 'physique' in libelle:
                m_cat = 'physique'
        
        # On cherche sur 90 jours max
        while not planifie and (current_d - start_date).days < 90:
            if current_d.weekday() >= 5: # Skip weekend
                current_d += timedelta(days=1)
                continue
            
            for t_slot in time_slots:
                # 1. Collision Groupe
                parent_td = None
                if b['gp'].startswith('TP'): parent_td = f'TD{b["gp"][2]}' 
                
                collision_gp = Seance.query.filter(
                    Seance.date_seance == current_d,
                    Seance.heure_debut == t_slot,
                    db.or_(
                        Seance.groupe == b['gp'],
                        Seance.groupe == 'CM',
                        Seance.groupe == parent_td if parent_td else False,
                        Seance.groupe.like(f'TP{b["gp"][2]}%') if b['gp'].startswith('TD') else False
                    )
                ).first()
                if collision_gp: continue

                # 2. Collision Prof
                if b['ens']:
                    collision_ens = Seance.query.filter_by(date_seance=current_d, heure_debut=t_slot, enseignant_id=b['ens']).first()
                    if collision_ens: continue

                # 3. Attribution SALLE auto
                salle_id = None
                
                for sl in salles_all:
                    # Type compatible
                    if b['type'] == 'CM' and sl.type_salle != 'Amphi': continue
                    if b['type'] == 'TD' and sl.type_salle != 'TD': continue
                    if b['type'] == 'TP' and sl.type_salle != 'TP': continue
                    
                    # Catégorie compatible (pour TP)
                    if b['type'] == 'TP' and m_cat:
                        r_cat = sl.categorie.lower().strip() if sl.categorie else ""
                        if m_cat in info_aliases:
                            if r_cat != 'info': continue
                        elif r_cat != m_cat:
                            continue
                    
                    # Disponibilité salle
                    collision_sl = Seance.query.filter_by(date_seance=current_d, heure_debut=t_slot, salle_id=sl.id).first()
                    if not collision_sl:
                        salle_id = sl.id
                        break
                
                if salle_id:
                    nouv = Seance(
                        module_id=b['module'].id, enseignant_id=b['ens'],
                        type_seance=b['type'], groupe=b['gp'],
                        date_seance=current_d, heure_debut=t_slot,
                        duree=b['duree'], salle_id=salle_id
                    )
                    db.session.add(nouv)
                    seances_creees += 1
                    planifie = True
                    break
            
            if not planifie:
                current_d += timedelta(days=1)

    db.session.commit()
    flash(f'{seances_creees} séances ont été générées avec salles automatiques !', 'success')
    return redirect(url_for('admin.planning', fid=fid))
