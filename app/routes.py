from flask import Blueprint, render_template
from app.models import Persoon

main = Blueprint('main', __name__)

@main.route('/')
def home():
    return "Welkom bij je Flask-app met Supabase"

@main.route('/personen')
def personen_tabel():
    kolomnamen = [kolom.name for kolom in Persoon.__table__.columns]
    personen = []
    return render_template("personen.html", kolomnamen=kolomnamen, personen=personen)


