from app.extensions import db
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta

class User(UserMixin, db.Model):
    """
    Modèle Utilisateur. Gère l'authentification et les rôles.
    Hérite de UserMixin pour l'intégration avec Flask-Login.
    """
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(256), nullable=False)
    role = db.Column(db.String(20), nullable=False, default='student') # 'admin' ou 'student'
    
    # Nouveaux champs pour la personnalisation du planning étudiant/prof
    formation_id = db.Column(db.Integer, db.ForeignKey('formations.id'), nullable=True)
    enseignant_id = db.Column(db.Integer, db.ForeignKey('enseignants.id'), nullable=True) # Pour le rôle 'teacher'
    td_group = db.Column(db.String(10), nullable=True) # ex: 'TD1'
    tp_group = db.Column(db.String(10), nullable=True) # ex: 'TP1A'
    
    formation = db.relationship('Formation', backref=db.backref('students', lazy='dynamic'))
    enseignant = db.relationship('Enseignant', backref=db.backref('user', uselist=False))

    def set_password(self, password):
        """Hache le mot de passe avant de le stocker."""
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        """Vérifie si le mot de passe fourni correspond au hachage."""
        return check_password_hash(self.password_hash, password)

    def is_admin(self):
        """Vérifie si l'utilisateur est un administrateur."""
        return self.role == 'admin'

    def is_teacher(self):
        """Vérifie si l'utilisateur est un enseignant."""
        return self.role == 'teacher'


class Formation(db.Model):
    """
    Modèle Formation (ex: BUT Informatique).
    """
    __tablename__ = 'formations'
    id = db.Column(db.Integer, primary_key=True)
    nom = db.Column(db.String(100), nullable=False)
    nb_groupes_td = db.Column(db.Integer, nullable=False, default=1)
    nb_groupes_tp = db.Column(db.Integer, nullable=False, default=1)
    
    # Relation : Une formation contient plusieurs modules
    modules = db.relationship('Module', backref='formation', lazy='dynamic', cascade='all, delete-orphan')


class Module(db.Model):
    """
    Modèle Module / Matière (ex: M2103 Base de données).
    Définit la maquette pédagogique (volumes horaires prévus).
    """
    __tablename__ = 'modules'
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(20), nullable=False, index=True)
    libelle = db.Column(db.String(100), nullable=False)
    
    # Quotas horaires selon la maquette
    cm_heures = db.Column(db.Float, nullable=False, default=0.0)
    td_heures = db.Column(db.Float, nullable=False, default=0.0)
    tp_heures = db.Column(db.Float, nullable=False, default=0.0)
    categorie = db.Column(db.String(50), nullable=True) # ex: 'Info', 'Anglais'
    
    formation_id = db.Column(db.Integer, db.ForeignKey('formations.id'), nullable=False)
    
    # Relations
    affectations = db.relationship('Affectation', backref='module', lazy='dynamic', cascade='all, delete-orphan')
    seances = db.relationship('Seance', backref='module', lazy='dynamic', cascade='all, delete-orphan')
    
    @property
    def volume_total(self):
        """Calcule le volume total de la maquette pour ce module."""
        return self.cm_heures + self.td_heures + self.tp_heures


class Enseignant(db.Model):
    """
    Modèle Enseignant / Intervenant.
    """
    __tablename__ = 'enseignants'
    id = db.Column(db.Integer, primary_key=True)
    nom = db.Column(db.String(50), nullable=False)
    prenom = db.Column(db.String(50), nullable=False)
    
    # Relations
    affectations = db.relationship('Affectation', backref='enseignant', lazy='dynamic', cascade='all, delete-orphan')
    seances = db.relationship('Seance', backref='enseignant', lazy='dynamic', cascade='all, delete-orphan')
    
    def nom_complet(self):
        return f"{self.nom} {self.prenom}"


class Salle(db.Model):
    """
    Modèle Salle de classe.
    """
    __tablename__ = 'salles'
    id = db.Column(db.Integer, primary_key=True)
    nom = db.Column(db.String(50), nullable=False)
    type_salle = db.Column(db.String(10), nullable=False) # 'Amphi', 'TD', 'TP'
    categorie = db.Column(db.String(50), nullable=True) # ex: 'Anglais', 'Info'
    capacite = db.Column(db.Integer, nullable=True)
    
    # Relation
    seances = db.relationship('Seance', backref='salle', lazy='dynamic')


class Affectation(db.Model):
    """
    Modèle Affectation. 
    Lien entre un enseignant et un module pour y effectuer des heures.
    Permet de définir qui a le droit d'enseigner quoi, et pour quel volume.
    """
    __tablename__ = 'affectations'
    id = db.Column(db.Integer, primary_key=True)
    enseignant_id = db.Column(db.Integer, db.ForeignKey('enseignants.id'), nullable=False)
    module_id = db.Column(db.Integer, db.ForeignKey('modules.id'), nullable=False)
    
    # Volumes horaires assignés à cet enseignant pour ce module
    cm_heures = db.Column(db.Float, nullable=False, default=0.0)
    td_heures = db.Column(db.Float, nullable=False, default=0.0)
    tp_heures = db.Column(db.Float, nullable=False, default=0.0)


class Seance(db.Model):
    """
    Modèle Seance (Le planning effectif).
    Représente un bloc horaire dans l'emploi du temps.
    """
    __tablename__ = 'seances'
    id = db.Column(db.Integer, primary_key=True)
    module_id = db.Column(db.Integer, db.ForeignKey('modules.id'), nullable=False)
    enseignant_id = db.Column(db.Integer, db.ForeignKey('enseignants.id'), nullable=True)
    
    type_seance = db.Column(db.String(10), nullable=False) # 'CM', 'TD', 'TP'
    date_seance = db.Column(db.Date, nullable=False)
    heure_debut = db.Column(db.Time, nullable=False)
    duree = db.Column(db.Float, nullable=False) # Durée en heures (ex: 1.5 pour 1h30)
    
    # Représentation du groupe (ex: 'TD1', 'TP2A', 'CM')
    groupe = db.Column(db.String(20), nullable=False)
    
    salle_id = db.Column(db.Integer, db.ForeignKey('salles.id'), nullable=True)
    
    @property
    def heure_fin(self):
        """Calcul automatique de l'heure de fin basé sur le début et la durée."""
        # Combinaison avec une date factice pour faciliter le calcul
        dt = datetime.combine(self.date_seance, self.heure_debut)
        # Ajout de la durée
        dt_fin = dt + timedelta(hours=self.duree)
        return dt_fin.time()
