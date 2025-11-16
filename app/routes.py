from flask import Blueprint, render_template, request
from app.models import Persoon, Fractie, Thema, SchriftelijkeVragen, Persoonfunctie, ThemaKoppeling, Functies
from sqlalchemy import func
from app import db
from sqlalchemy.exc import OperationalError


main = Blueprint('main', __name__)

# --- HOOFDPAGINA ---
@main.route('/')
def index():
    try:
        # Statistieken
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

        # Recentste vragen
        vragen = (
            db.session.query(SchriftelijkeVragen)
            .order_by(SchriftelijkeVragen.ingediend.desc())
            .limit(5)
            .all()
        )

        # Thema’s
        themas = Thema.query.all()
        themes_data = [{'naam': t.naam, 'count': 0} for t in themas] #maak lijst van thema's elk krijgt voorlopig count 0

        # Fracties
        fracties_data = Fractie.query.all()
        fracties = [{'naam': f.naam, 'zetels': 0} for f in fracties_data]

    except OperationalError:
        # Database niet bereikbaar → geen crash, maar lege data
        aantal_vragen = 0
        aantal_themas = 0
        aantal_personen = 0
        aantal_fracties = 0
        aantal_beantwoord = 0
        vragen = []
        themes_data = []
        fracties = []

    stats_data = [
        {'label': 'Schriftelijke Vragen', 'value': aantal_vragen, 'icon': 'file-text'},
        {'label': 'Actieve Thema’s', 'value': aantal_themas, 'icon': 'tag'},
        {'label': 'Volksvertegenwoordigers', 'value': aantal_personen, 'icon': 'users'},
        {'label': 'Beantwoorde Vragen', 'value': f"{aantal_beantwoord}/{aantal_vragen}" if aantal_vragen else "0", 'icon': 'trending-up'},
    ]

    return render_template(
        'index.html',
        stats=stats_data,
        questions=vragen,
        themes=themes_data,
        fracties=fracties
    ) #stuurt alle data naar de pagina index.html


# --- OVERZICHTPAGINA STATISTIEKEN ---
@main.route('/statistieken')
def statistieken_overzicht():
    return render_template('statistieken_overzicht.html')


# --- STATISTIEKEN PER THEMA ---
@main.route('/statistieken/themas')
def statistieken_themas():
    try:
        themas = db.session.query(Thema).all()
        data = []

        for thema in themas:
            vragen = (
                db.session.query(SchriftelijkeVragen)
                .join(ThemaKoppeling, ThemaKoppeling.id_schv == SchriftelijkeVragen.id)
                .filter(ThemaKoppeling.id_thm == thema.id)
                .all()
            )
            if not vragen:
                continue

            totaal_vragen = len(vragen)
            fractie_telling, persoon_telling = {}, {}
            geslacht_telling = {"M": 0, "V": 0, "X": 0}
            laatste_vraag = max((v.ingediend for v in vragen if v.ingediend), default=None)

            for vraag in vragen:
                pf = db.session.query(Persoonfunctie).get(vraag.id_prsfnc_vs)
                if not pf:
                    continue

                fractie = db.session.query(Fractie).get(pf.id_frc)
                persoon = db.session.query(Persoon).get(pf.id_prs)

                if fractie:
                    fractie_telling[fractie.naam] = fractie_telling.get(fractie.naam, 0) + 1
                if persoon:
                    naam = f"{persoon.voornaam} {persoon.naam}"
                    persoon_telling[naam] = persoon_telling.get(naam, 0) + 1
                    if persoon.geslacht in geslacht_telling:
                        geslacht_telling[persoon.geslacht] += 1

            actiefste_fractie = max(fractie_telling, key=fractie_telling.get, default="-")
            actiefste_persoon = max(persoon_telling, key=persoon_telling.get, default="-")

            totaal_geslacht = sum(geslacht_telling.values())
            if totaal_geslacht > 0:
                geslacht_procenten = {
                    k: round(v * 100 / totaal_geslacht, 1)
                    for k, v in geslacht_telling.items()
                }
                dominant = max(geslacht_procenten, key=geslacht_procenten.get)
                dominant_geslacht = f"{geslacht_procenten[dominant]}% {dominant}"
            else:
                dominant_geslacht = "-"

            data.append({
                "thema_naam": thema.naam,
                "actiefste_fractie": actiefste_fractie,
                "actiefste_persoon": actiefste_persoon,
                "laatste_vraag": laatste_vraag.strftime("%Y-%m-%d") if laatste_vraag else "-",
                "dominant_geslacht": dominant_geslacht,
                "totaal_vragen": totaal_vragen,
            })
    except OperationalError:
        # DB niet bereikbaar -> toon lege lijst i.p.v. 500-error
        data = []

    return render_template("statistieken_themas.html", data=data)


# --- STATISTIEKEN PER FRACTIE ---
@main.route('/statistieken/fracties')
def statistieken_fracties():
    try:
        fracties = db.session.query(Fractie).all()
        data = []

        for fractie in fracties:
            vragen = (
                db.session.query(SchriftelijkeVragen)
                .join(Persoonfunctie, Persoonfunctie.id == SchriftelijkeVragen.id_prsfnc_vs)
                .filter(Persoonfunctie.id_frc == fractie.id)
                .all()
            )
            data.append({
                "fractie": fractie.naam,
                "aantal_vragen": len(vragen),
            })
    except OperationalError:
        data = []

    return render_template("statistieken_fracties.html", data=data)


# --- STATISTIEKEN PER PERSOON ---
@main.route('/statistieken/personen')
def statistieken_personen():
    try:
        personen = db.session.query(Persoon).all()
        data = []

        for persoon in personen:
            vragen = (
                db.session.query(SchriftelijkeVragen)
                .join(Persoonfunctie, Persoonfunctie.id == SchriftelijkeVragen.id_prsfnc_vs)
                .filter(Persoonfunctie.id_prs == persoon.id)
                .all()
            )
            data.append({
                "naam": f"{persoon.voornaam} {persoon.naam}",
                "aantal_vragen": len(vragen),
            })
    except OperationalError:
        data = []

    return render_template("statistieken_personen.html", data=data)


# --- ACTIEFSTE VOLKSVERTEGENWOORDIGERS PER THEMA & KIESKRING ---
@main.route('/statistieken/actiefste', methods=['GET'])
def actiefste_per_thema_en_kieskring():
    try:
        # Alle verschillende kieskringen ophalen (voor de dropdown)
        kieskringen = [
            k[0] for k in (
                db.session.query(Persoon.kieskring)
                .distinct()
                .order_by(Persoon.kieskring)
                .all()
            )
            if k[0] is not None
        ]

        # Alle thema's voor de dropdown
        themas = Thema.query.order_by(Thema.naam).all()

        # Wat heeft de gebruiker geselecteerd?
        geselecteerde_kieskring = request.args.get('kieskring')
        geselecteerd_thema_id = request.args.get('thema')

        data = []

        if geselecteerde_kieskring and geselecteerd_thema_id:
            rows = (
                db.session.query(
                    Persoon.id.label("persoon_id"),
                    Persoon.voornaam,
                    Persoon.naam,
                    Persoon.kieskring,
                    Fractie.naam.label("fractie_naam"),
                    func.count(SchriftelijkeVragen.id).label("aantal_vragen"),
                )
                .join(Persoonfunctie, Persoonfunctie.id_prs == Persoon.id)
                .join(Fractie, Fractie.id == Persoonfunctie.id_frc)
                .join(SchriftelijkeVragen, SchriftelijkeVragen.id_prsfnc_vs == Persoonfunctie.id)
                .join(ThemaKoppeling, ThemaKoppeling.id_schv == SchriftelijkeVragen.id)
                .filter(Persoon.kieskring == geselecteerde_kieskring)
                .filter(ThemaKoppeling.id_thm == geselecteerd_thema_id)
                .group_by(
                    Persoon.id,
                    Persoon.voornaam,
                    Persoon.naam,
                    Persoon.kieskring,
                    Fractie.naam,
                )
                .order_by(func.count(SchriftelijkeVragen.id).desc())
                .all()
            )

            for idx, r in enumerate(rows, start=1):
                data.append({
                    "rang": idx,
                    "naam": f"{r.voornaam} {r.naam}",
                    "fractie": r.fractie_naam,
                    "kieskring": r.kieskring,
                    "aantal_vragen": r.aantal_vragen,
                })

    except OperationalError:
        # Als de database niet bereikbaar is → lege state ipv 500 error
        kieskringen = []
        themas = []
        geselecteerde_kieskring = None
        geselecteerd_thema_id = None
        data = []

    return render_template(
        "statistieken_actiefste.html",
        kieskringen=kieskringen,
        themas=themas,
        geselecteerde_kieskring=geselecteerde_kieskring,
        geselecteerd_thema_id=geselecteerd_thema_id,
        data=data,
    )



# priority scoring algoritme 
from datetime import datetime
from app.models import ThemaKoppeling  # staat er waarschijnlijk al, zo niet: importeren

# --- PRIORITY SCORING ALGORITME ---
@main.route('/statistieken/priority')
def statistieken_priority():
    try:
        vragen = db.session.query(SchriftelijkeVragen).all()
        data = []

        for vraag in vragen:
            # Hoe recent is de vraag?
            dagen_verschil = (datetime.now().date() - vraag.ingediend).days if vraag.ingediend else 999
            recency_score = max(0, 100 - dagen_verschil)

            # Aantal thema’s gekoppeld aan de vraag
            aantal_themas = (
                db.session.query(ThemaKoppeling)
                .filter(ThemaKoppeling.id_schv == vraag.id)
                .count()
            )
            thema_score = aantal_themas * 10

            # Totale prioriteitsscore
            total_score = recency_score + thema_score

            data.append({
                "onderwerp": vraag.onderwerp,
                "ingediend": vraag.ingediend.strftime("%Y-%m-%d") if vraag.ingediend else "-",
                "beantwoord": "Nee" if vraag.beantwoord is None else "Ja",
                "aantal_themas": aantal_themas,
                "priority_score": total_score,
            })

        # Sorteer van hoogste naar laagste prioriteit
        data.sort(key=lambda x: x["priority_score"], reverse=True)
    except OperationalError:
        data = []

    return render_template("statistieken_priority.html", data=data)

@main.route('/volksvertegenwoordigers')
def volksvertegenwoordigers():
    try:
        personen = db.session.query(Persoon).all()
        data = []
        for p in personen:
            persoonfuncties = db.session.query(Persoonfunctie).filter_by(id_prs=p.id).all()
            for pf in persoonfuncties:
                fractie = db.session.query(Fractie).get(pf.id_frc)
                functie = db.session.query(Functies).get(pf.id_fnc)
                data.append({
                    "naam": f"{p.voornaam} {p.naam}",
                    "fractie": fractie.naam if fractie else "-",
                    "kieskring": p.kieskring or "-",
                    "functie": functie.naam if functie else "-"
                })
    except OperationalError:
        data = []
    return render_template("volksvertegenwoordigers.html", volksvertegenwoordigers=data)

# --- ZOEKFUNCTIE VOOR SCHRIFTELIJKE VRAGEN ---
@main.route('/zoeken', methods=['GET', 'POST'])
def zoeken():
    resultaten = []

    if request.method == 'POST':
        trefwoord = request.form.get('trefwoord', '').strip()

        if trefwoord:
            resultaten = (
                db.session.query(SchriftelijkeVragen)
                .filter(
                    (SchriftelijkeVragen.onderwerp.ilike(f"%{trefwoord}%")) |
                    (SchriftelijkeVragen.tekst.ilike(f"%{trefwoord}%"))
                )
                .order_by(SchriftelijkeVragen.ingediend.desc())
                .all()
            )

    return render_template('zoeken.html', resultaten=resultaten)

# --- ACTIEVE THEMA'S PAGINA ---
@main.route('/actieve_themas')
def actieve_themas():
    return render_template("actieve_themas.html")

@main.route('/statistieken/vragen', methods=['GET'])
def overzicht_schriftelijke_vragen():
    try:
        # Haal de schriftelijke vragen op met thema’s
        vragen = (
            db.session.query(
                SchriftelijkeVragen.vraag,
                SchriftelijkeVragen.datum_indiening,
                SchriftelijkeVragen.datum_beantwoord,
                Thema.naam.label("thema_naam")
            )
            .join(ThemaKoppeling, ThemaKoppeling.id_schv == SchriftelijkeVragen.id)
            .join(Thema, Thema.id == ThemaKoppeling.id_thm)
            .order_by(SchriftelijkeVragen.datum_indiening.desc())
            .all()
        )

    except Exception as e:
        print(e)
        vragen = []

    return render_template('schriftelijke_vragen.html', vragen=vragen)
