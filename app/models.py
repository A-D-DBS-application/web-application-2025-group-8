from app import db
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy import Enum
import enum

# ===== ENUM VOOR GESLACHT =====
class GeslachtEnum(enum.Enum):
    M = "M"
    V = "V"
    X = "X"

# ===== FRACTIE =====
class Fractie(db.Model):
    __tablename__ = "fractie"

    id = db.Column(UUID(as_uuid=True), primary_key=True)  # geen default
    naam = db.Column(db.String, nullable=False)
    logo_url = db.Column(db.String)

# ===== FUNCTIES =====
class Functies(db.Model):
    __tablename__ = "functies"

    id = db.Column(UUID(as_uuid=True), primary_key=True)  # geen default
    code = db.Column(db.String, unique=True, nullable=False)
    naam = db.Column(db.String, nullable=False)
    omschrijving = db.Column(db.Text)

# ===== PERSOON =====
class Persoon(db.Model):
    __tablename__ = "persoon"

    id = db.Column(UUID(as_uuid=True), primary_key=True)  # geen default
    voornaam = db.Column(db.String, nullable=False)
    naam = db.Column(db.String, nullable=False)
    geboortedatum = db.Column(db.Date)
    geslacht = db.Column(Enum(GeslachtEnum, name="geslacht_enum"))
    roepnaam = db.Column(db.String)
    kieskring = db.Column(db.String, nullable=False)

# ===== PERSOONFUNCTIE =====
class Persoonfunctie(db.Model):
    __tablename__ = "persoonfunctie"

    id = db.Column(UUID(as_uuid=True), primary_key=True)  # geen default
    id_fnc = db.Column(UUID(as_uuid=True), db.ForeignKey("functies.id"), nullable=False)
    id_prs = db.Column(UUID(as_uuid=True), db.ForeignKey("persoon.id"), nullable=False)
    id_frc = db.Column(UUID(as_uuid=True), db.ForeignKey("fractie.id"))
    van = db.Column(db.Date, nullable=False)
    tot = db.Column(db.Date)

# ===== THEMA =====
class Thema(db.Model):
    __tablename__ = "thema"

    id = db.Column(UUID(as_uuid=True), primary_key=True)  # geen default
    naam = db.Column(db.String, nullable=False)
    omschrijving = db.Column(db.Text)

# ===== SCHRIFTELIJKE VRAGEN =====
class SchriftelijkeVragen(db.Model):
    __tablename__ = "schriftelijke_vragen"

    id = db.Column(UUID(as_uuid=True), primary_key=True)  # geen default
    ingediend = db.Column(db.Date, nullable=False)
    onderwerp = db.Column(db.String, nullable=False)
    tekst = db.Column(db.Text)
    id_prsfnc_vs = db.Column(UUID(as_uuid=True), db.ForeignKey("persoonfunctie.id"), nullable=False)
    id_prsfnc_min = db.Column(UUID(as_uuid=True), db.ForeignKey("persoonfunctie.id"), nullable=False)
    beantwoord = db.Column(db.Date)

# ===== THEMA KOPPELING =====
class ThemaKoppeling(db.Model):
    __tablename__ = "thema_koppeling"

    id = db.Column(UUID(as_uuid=True), primary_key=True)  # geen default
    id_thm = db.Column(UUID(as_uuid=True), db.ForeignKey("thema.id"), nullable=False)
    id_schv = db.Column(UUID(as_uuid=True), db.ForeignKey("schriftelijke_vragen.id"), nullable=False)
    volgnr = db.Column(db.Integer, nullable=False)


