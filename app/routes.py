from flask import Blueprint, render_template
from app.models import Persoon, Fractie, Thema, SchriftelijkeVragen
from sqlalchemy import func
from app import db

main = Blueprint('main', __name__)

@main.route('/')
def index():
    # Dynamisch tellen uit database
    aantal_vragen = db.session.query(func.count(SchriftelijkeVragen.id)).scalar() or 0
    aantal_themas = db.session.query(func.count(Thema.id)).scalar() or 0
    aantal_personen = db.session.query(func.count(Persoon.id)).scalar() or 0
    aantal_fracties = db.session.query(func.count(Fractie.id)).scalar() or 0
    aantal_beantwoord = (
        db.session.query(func.count(SchriftelijkeVragen.id))
        .filter(SchriftelijkeVragen.beantwoord.isnot(None))
        .scalar()
        or 0
    )

    # Statistieken dynamisch tonen
    stats_data = [
        {
            'label': 'Schriftelijke Vragen',
            'value': aantal_vragen,
            'icon': 'file-text',
        },
        {
            'label': 'Actieve Thema’s',
            'value': aantal_themas,
            'icon': 'tag',
        },
        {
            'label': 'Volksvertegenwoordigers',
            'value': aantal_personen,
            'icon': 'users',
        },
        {
            'label': 'Beantwoorde Vragen',
            'value': f"{aantal_beantwoord}/{aantal_vragen}" if aantal_vragen else "0",
            'icon': 'trending-up',
        },
    ]

    # Laatste 5 schriftelijke vragen
    vragen = (
        db.session.query(SchriftelijkeVragen)
        .order_by(SchriftelijkeVragen.ingediend.desc())
        .limit(5)
        .all()
    )

    # Thema’s (lijst van namen)
    themas = Thema.query.all()
    themes_data = [{'naam': t.naam, 'count': 0} for t in themas]

    # Fracties (namen + placeholders)
    fracties_data = Fractie.query.all()
    fracties = [{'naam': f.naam, 'zetels': 0} for f in fracties_data]

    return render_template(
        'index.html',
        stats=stats_data,
        questions=vragen,
        themes=themes_data,
        fracties=fracties,
    )

