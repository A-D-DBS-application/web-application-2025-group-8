import uuid
from app import db
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy import Enum
import enum


# ===== Enum voor geslacht =====
class GeslachtEnum(enum.Enum):
    M = "M"
    V = "V"
    X = "X"


# ===== Tabellen =====

class Fractie(db.Model):
    __tablename__ = "Fractie"

    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    naam = db.Column(db.String, nullable=False)
    logo_url = db.Column(db.String)


class Functies(db.Model):
    __tablename__ = "Functies"
    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    code = db.Column(db.String, unique=True, nullable=False)
    naam = db.Column(db.String, nullable=False)
    omschrijving = db.Column(db.Text)


class Persoon(db.Model):
    __tablename__ = "Persoon"

    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    voornaam = db.Column(db.String, nullable=False)
    naam = db.Column(db.String, nullable=False)
    geboortedatum = db.Column(db.Date)
    geslacht = db.Column(Enum(GeslachtEnum, name="geslacht_enum"))
    roepnaam = db.Column(db.String)


class Persoonfunctie(db.Model):
    __tablename__ = "Persoonfunctie"

    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    id_fnc = db.Column(UUID(as_uuid=True), db.ForeignKey("Functies.id"), nullable=False)
    id_prs = db.Column(UUID(as_uuid=True), db.ForeignKey("Persoon.id"), nullable=False)
    id_frc = db.Column(UUID(as_uuid=True), db.ForeignKey("Fractie.id"))
    van = db.Column(db.Date, nullable=False)
    tot = db.Column(db.Date)


class Thema(db.Model):
    __tablename__ = "Thema"

    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    naam = db.Column(db.String, nullable=False)
    omschrijving = db.Column(db.Text)
    thema = db.Column(db.String)


class SchriftelijkeVragen(db.Model):
    __tablename__ = "SchriftelijkeVragen"

    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    ingediend = db.Column(db.Date, nullable=False)
    onderwerp = db.Column(db.String, nullable=False)
    tekst = db.Column(db.Text)
    id_prsfnc_vs = db.Column(UUID(as_uuid=True), db.ForeignKey("Persoonfunctie.id"), nullable=False)
    id_prsfnc_min = db.Column(UUID(as_uuid=True), db.ForeignKey("Persoonfunctie.id"), nullable=False)
    beantwoord = db.Column(db.Date)


class ThemaKoppeling(db.Model):
    __tablename__ = "ThemaKoppeling"

    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    id_thm = db.Column(UUID(as_uuid=True), db.ForeignKey("Thema.id"), nullable=False)
    id_schv = db.Column(UUID(as_uuid=True), db.ForeignKey("SchriftelijkeVragen.id"), nullable=False)
    volgnr = db.Column(db.Integer, nullable=False)
