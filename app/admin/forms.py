from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, IntegerField, FloatField, SelectField, DateField, TimeField
from wtforms.validators import DataRequired, Email, Length, NumberRange, ValidationError
from app.models import Formation, Enseignant, Module, Salle

class LoginForm(FlaskForm):
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Mot de passe', validators=[DataRequired()])
    submit = SubmitField('Se connecter')

class FormationForm(FlaskForm):
    nom = StringField('Nom de la formation', validators=[DataRequired(), Length(max=100)])
    nb_groupes_td = IntegerField('Nombre de groupes TD', validators=[DataRequired(), NumberRange(min=1)])
    nb_groupes_tp = IntegerField('Nombre de groupes TP', validators=[DataRequired(), NumberRange(min=1)])
    submit = SubmitField('Enregistrer')

class ModuleForm(FlaskForm):
    code = StringField('Code du module', validators=[DataRequired(), Length(max=20)])
    libelle = StringField('Libellé', validators=[DataRequired(), Length(max=100)])
    cm_heures = FloatField('Heures de CM prevues', validators=[NumberRange(min=0)], default=0.0)
    td_heures = FloatField('Heures de TD prevues', validators=[NumberRange(min=0)], default=0.0)
    tp_heures = FloatField('Heures de TP prevues', validators=[NumberRange(min=0)], default=0.0)
    categorie = StringField('Catégorie (ex: Info, Anglais)', validators=[Length(max=50)])
    formation_id = SelectField('Formation', coerce=int, validators=[DataRequired()])
    submit = SubmitField('Enregistrer')

    def __init__(self, *args, **kwargs):
        super(ModuleForm, self).__init__(*args, **kwargs)
        self.formation_id.choices = [(f.id, f.nom) for f in Formation.query.order_by(Formation.nom).all()]

class EnseignantForm(FlaskForm):
    nom = StringField('Nom', validators=[DataRequired(), Length(max=50)])
    prenom = StringField('Prénom', validators=[DataRequired(), Length(max=50)])
    submit = SubmitField('Enregistrer')

class AffectationForm(FlaskForm):
    enseignant_id = SelectField('Enseignant', coerce=int, validators=[DataRequired()])
    module_id = SelectField('Module', coerce=int, validators=[DataRequired()])
    cm_heures = FloatField('Heures CM', validators=[NumberRange(min=0)], default=0.0)
    td_heures = FloatField('Heures TD', validators=[NumberRange(min=0)], default=0.0)
    tp_heures = FloatField('Heures TP', validators=[NumberRange(min=0)], default=0.0)
    submit = SubmitField('Affecter')

    def __init__(self, *args, **kwargs):
        super(AffectationForm, self).__init__(*args, **kwargs)
        self.enseignant_id.choices = [(e.id, f"{e.nom} {e.prenom}") for e in Enseignant.query.order_by(Enseignant.nom).all()]
        self.module_id.choices = [(m.id, f"{m.code} - {m.libelle}") for m in Module.query.order_by(Module.code).all()]

class SalleForm(FlaskForm):
    type_salle = SelectField('Type', choices=[('Amphi', 'Amphithéâtre (Manuel)'), ('TD', 'Salles TD (Auto)'), ('TP', 'Salles TP (Auto)')], validators=[DataRequired()])
    nom = StringField('Nom (pour Amphi)', validators=[Length(max=50)])
    categorie = StringField('Catégorie (ex: Info, Anglais)', validators=[Length(max=50)])
    nombre = IntegerField('Nombre de salles à créer', default=1, validators=[NumberRange(min=1)])
    capacite = IntegerField('Capacité par salle', validators=[NumberRange(min=1)])
    submit = SubmitField('Enregistrer')

class SeanceForm(FlaskForm):
    module_id = SelectField('Module', coerce=int, validators=[DataRequired()])
    enseignant_id = SelectField('Enseignant', coerce=int, validators=[DataRequired()])
    type_seance = SelectField('Type', choices=[('CM', 'Cours Magistral'), ('TD', 'Travaux Dirigés'), ('TP', 'Travaux Pratiques')], validators=[DataRequired()])
    groupe = StringField('Groupe (ex: TD1, TP2A)', validators=[DataRequired(), Length(max=20)])
    date_seance = DateField('Date', validators=[DataRequired()])
    heure_debut = TimeField('Heure de début', validators=[DataRequired()])
    duree = FloatField('Durée (en heures)', validators=[DataRequired(), NumberRange(min=0.5)], default=1.5)
    salle_id = SelectField('Salle', coerce=int, validators=[DataRequired()])
    submit = SubmitField('Planifier')

    def __init__(self, *args, **kwargs):
        super(SeanceForm, self).__init__(*args, **kwargs)
        self.module_id.choices = [(m.id, f"{m.code} - {m.libelle}") for m in Module.query.order_by(Module.code).all()]
        self.enseignant_id.choices = [(e.id, f"{e.nom} {e.prenom}") for e in Enseignant.query.order_by(Enseignant.nom).all()]
        self.salle_id.choices = [(s.id, f"{s.nom} ({s.type_salle})") for s in Salle.query.order_by(Salle.nom).all()]
