"""
Moteur d'import CSV — cohérent avec les vrais modèles SQLAlchemy.

Modèles réels :
  Enseignant : id, nom, prenom  (PAS d'email en base)
  Module     : id, code, libelle, cm_heures, td_heures, tp_heures, categorie, formation_id
  Salle      : id, nom, type_salle, categorie, capacite
  Affectation: id, enseignant_id, module_id, cm_heures, td_heures, tp_heures
  Formation  : id, nom, nb_groupes_td, nb_groupes_tp

Formats CSV attendus (séparateur ;) :
  modules.csv    : code;libelle;categorie;formation;cm_heures;td_heures;tp_heures
  salles.csv     : nom;type_salle;categorie;capacite
  enseignants.csv: nom;prenom
  affectations.csv: enseignant_nom;enseignant_prenom;module_code;cm_heures;td_heures;tp_heures
"""

import csv
import io
from app.models import db, Module, Formation, Salle, Enseignant, Affectation
from sqlalchemy import func


# ─────────────────────────────────────────────
# Utilitaires internes
# ─────────────────────────────────────────────

def _s(val):
    """Strip et retourne une chaîne, ou '' si None."""
    return str(val).strip() if val is not None else ''

def _float(val, default=0.0):
    try:
        return float(_s(val))
    except (ValueError, TypeError):
        return default

def _parse_csv(file_content, required_cols):
    """
    Décode le contenu, crée un DictReader, normalise les en-têtes en minuscules.
    Retourne (reader, error_message).
    """
    if isinstance(file_content, bytes):
        file_content = file_content.decode('utf-8-sig', errors='ignore')
    
    reader = csv.DictReader(io.StringIO(file_content), delimiter=';')
    
    if not reader.fieldnames:
        return None, "Le fichier CSV est vide ou invalide (aucun en-tête détecté)."
    
    # Normalise les en-têtes
    reader.fieldnames = [_s(h).lower() for h in reader.fieldnames]
    
    missing = [c for c in required_cols if c not in reader.fieldnames]
    if missing:
        return None, f"Colonnes manquantes : {', '.join(missing)}. Colonnes trouvées : {', '.join(reader.fieldnames)}"
    
    return reader, None

def _report(success, duplicates, errors, total):
    return {
        'total': total,
        'success': success,
        'duplicates': duplicates,
        'rejected': len(errors),
        'errors': errors
    }


# ─────────────────────────────────────────────
# Import Modules
# Colonnes : code;libelle;categorie;formation;cm_heures;td_heures;tp_heures
# ─────────────────────────────────────────────

def import_modules_from_csv(file_content):
    required = ['code', 'libelle', 'categorie', 'formation', 'cm_heures', 'td_heures', 'tp_heures']
    reader, err = _parse_csv(file_content, required)
    if err:
        return 0, 0, [f"Erreur de format : {err}"], 0

    # Pré-charger les formations (insensible à la casse)
    formations = {f.nom.strip().lower(): f for f in Formation.query.all()}

    success, duplicates, errors, total = 0, 0, [], 0

    for row in reader:
        total += 1
        line = total + 1  # ligne 1 = en-tête

        code = _s(row.get('code'))
        if not code:
            errors.append(f"Ligne {line} : Le code est vide.")
            continue

        # Doublon
        existant = Module.query.filter(func.lower(Module.code) == code.lower()).first()
        if existant:
            duplicates += 1
            errors.append(f"Ligne {line} : Module '{code}' déjà présent (ignoré).")
            continue

        # Formation
        form_key = _s(row.get('formation')).lower()
        if not form_key or form_key not in formations:
            errors.append(f"Ligne {line} : Formation '{_s(row.get('formation'))}' introuvable. Formations disponibles : {', '.join(f.nom for f in Formation.query.all())}")
            continue

        libelle = _s(row.get('libelle'))
        if not libelle:
            errors.append(f"Ligne {line} : Le libellé est vide.")
            continue

        m = Module(
            code=code,
            libelle=libelle,
            categorie=_s(row.get('categorie')) or None,
            formation_id=formations[form_key].id,
            cm_heures=_float(row.get('cm_heures')),
            td_heures=_float(row.get('td_heures')),
            tp_heures=_float(row.get('tp_heures'))
        )
        db.session.add(m)
        success += 1

    db.session.commit()
    return success, duplicates, errors, total


# ─────────────────────────────────────────────
# Import Salles
# Colonnes : nom;type_salle;categorie;capacite
# type_salle valide : Amphi, TD, TP
# ─────────────────────────────────────────────

def import_salles_from_csv(file_content):
    required = ['nom', 'type_salle', 'categorie', 'capacite']
    reader, err = _parse_csv(file_content, required)
    if err:
        return 0, 0, [f"Erreur de format : {err}"], 0

    TYPES_VALIDES = {'amphi', 'td', 'tp'}
    success, duplicates, errors, total = 0, 0, [], 0

    for row in reader:
        total += 1
        line = total + 1

        nom = _s(row.get('nom'))
        if not nom:
            errors.append(f"Ligne {line} : Le nom de salle est vide.")
            continue

        existant = Salle.query.filter(func.lower(Salle.nom) == nom.lower()).first()
        if existant:
            duplicates += 1
            errors.append(f"Ligne {line} : Salle '{nom}' déjà présente (ignorée).")
            continue

        type_salle = _s(row.get('type_salle'))
        if type_salle.lower() not in TYPES_VALIDES:
            errors.append(f"Ligne {line} : type_salle '{type_salle}' invalide. Valeurs acceptées : Amphi, TD, TP.")
            continue

        # Normalise la casse du type
        type_map = {'amphi': 'Amphi', 'td': 'TD', 'tp': 'TP'}
        type_salle_norm = type_map[type_salle.lower()]

        cap_raw = _s(row.get('capacite'))
        cap = int(float(cap_raw)) if cap_raw else None

        s = Salle(
            nom=nom,
            type_salle=type_salle_norm,
            categorie=_s(row.get('categorie')) or None,
            capacite=cap
        )
        db.session.add(s)
        success += 1

    db.session.commit()
    return success, duplicates, errors, total


# ─────────────────────────────────────────────
# Import Enseignants
# Colonnes : nom;prenom
# (Pas de champ email dans le modèle Enseignant)
# ─────────────────────────────────────────────

def import_enseignants_from_csv(file_content):
    required = ['nom', 'prenom']
    reader, err = _parse_csv(file_content, required)
    if err:
        return 0, 0, [f"Erreur de format : {err}"], 0

    success, duplicates, errors, total = 0, 0, [], 0

    for row in reader:
        total += 1
        line = total + 1

        nom = _s(row.get('nom'))
        prenom = _s(row.get('prenom'))

        if not nom or not prenom:
            errors.append(f"Ligne {line} : Nom ou prénom vide.")
            continue

        # Doublon (nom + prenom, insensible à la casse)
        existant = Enseignant.query.filter(
            func.lower(Enseignant.nom) == nom.lower(),
            func.lower(Enseignant.prenom) == prenom.lower()
        ).first()

        if existant:
            duplicates += 1
            errors.append(f"Ligne {line} : Enseignant '{prenom} {nom}' déjà présent (ignoré).")
            continue

        e = Enseignant(nom=nom, prenom=prenom)
        db.session.add(e)
        success += 1

    db.session.commit()
    return success, duplicates, errors, total


# ─────────────────────────────────────────────
# Import Affectations
# Colonnes : enseignant_nom;enseignant_prenom;module_code;cm_heures;td_heures;tp_heures
# Si affectation existante → mise à jour des heures
# Jamais de création d'enseignant ou module manquant
# ─────────────────────────────────────────────

def import_affectations_from_csv(file_content):
    required = ['enseignant_nom', 'enseignant_prenom', 'module_code', 'cm_heures', 'td_heures', 'tp_heures']
    reader, err = _parse_csv(file_content, required)
    if err:
        return 0, 0, [f"Erreur de format : {err}"], 0

    success, duplicates, errors, total = 0, 0, [], 0

    for row in reader:
        total += 1
        line = total + 1

        nom = _s(row.get('enseignant_nom'))
        prenom = _s(row.get('enseignant_prenom'))
        module_code = _s(row.get('module_code'))

        if not nom or not prenom:
            errors.append(f"Ligne {line} : enseignant_nom ou enseignant_prenom vide.")
            continue
        if not module_code:
            errors.append(f"Ligne {line} : module_code vide.")
            continue

        # Recherche enseignant (insensible à la casse)
        candidats = Enseignant.query.filter(
            func.lower(Enseignant.nom) == nom.lower(),
            func.lower(Enseignant.prenom) == prenom.lower()
        ).all()

        if len(candidats) == 0:
            errors.append(f"Ligne {line} : Enseignant '{prenom} {nom}' introuvable. Vérifiez nom/prénom.")
            continue
        if len(candidats) > 1:
            errors.append(f"Ligne {line} : Plusieurs enseignants correspondent à '{prenom} {nom}' (ambiguïté). Corrigez la base.")
            continue

        enseignant = candidats[0]

        # Recherche module (insensible à la casse)
        module = Module.query.filter(func.lower(Module.code) == module_code.lower()).first()
        if not module:
            codes_existants = ', '.join(m.code for m in Module.query.order_by(Module.code).limit(10).all())
            errors.append(f"Ligne {line} : Module '{module_code}' introuvable. Exemples : {codes_existants}...")
            continue

        cm = _float(row.get('cm_heures'))
        td = _float(row.get('td_heures'))
        tp = _float(row.get('tp_heures'))

        # Mise à jour si existante
        existant = Affectation.query.filter_by(
            enseignant_id=enseignant.id,
            module_id=module.id
        ).first()

        if existant:
            existant.cm_heures = cm
            existant.td_heures = td
            existant.tp_heures = tp
            duplicates += 1  # Mise à jour comptée séparément
            success += 1
        else:
            a = Affectation(
                enseignant_id=enseignant.id,
                module_id=module.id,
                cm_heures=cm,
                td_heures=td,
                tp_heures=tp
            )
            db.session.add(a)
            success += 1

    db.session.commit()
    return success, duplicates, errors, total
