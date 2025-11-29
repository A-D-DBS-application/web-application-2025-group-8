from flask import Blueprint, render_template, request
from app.models import Persoon, Fractie, Thema, SchriftelijkeVragen, Persoonfunctie, ThemaKoppeling, Functies
from sqlalchemy import func
from app import db
from sqlalchemy.exc import OperationalError
from flask_caching import Cache

# priority scoring algoritme 
from datetime import datetime, date

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

@main.route("/statistieken/personen")
def statistieken_personen():
    # 1. Haal alle personen op
    personen = Persoon.query.all()

    resultaat = []

    for persoon in personen:

        # ─────────────────────────────────────────────
        # 2. Vind alle persoonfuncties van deze persoon
        # ─────────────────────────────────────────────
        functies = Persoonfunctie.query.filter_by(id_prs=persoon.id).all()
        functie_ids = [f.id for f in functies]

        if not functie_ids:
            continue

        # ─────────────────────────────────────────────
        # 3. Haal alle vragen die door deze persoon zijn ingediend
        # ─────────────────────────────────────────────
        vragen = SchriftelijkeVragen.query.filter(
            SchriftelijkeVragen.id_prsfnc_vs.in_(functie_ids)
        ).all()

        if not vragen:
            resultaat.append({
                "naam": f"{persoon.voornaam} {persoon.naam}",
                "populair": None,
                "pop_count": 0,
                "tweede": None,
                "tweede_count": 0,
                "derde": None,
                "derde_count": 0,
                "laatste_vraag": None
            })
            continue

        # ─────────────────────────────────────────────
        # 4. Tel hoeveel keer elk thema voorkomt
        # ─────────────────────────────────────────────
        thema_counts = db.session.query(
            Thema.naam,
            func.count(ThemaKoppeling.id).label("aantal")
        ).join(ThemaKoppeling, Thema.id == ThemaKoppeling.id_thm) \
         .join(SchriftelijkeVragen, SchriftelijkeVragen.id == ThemaKoppeling.id_schv) \
         .filter(SchriftelijkeVragen.id_prsfnc_vs.in_(functie_ids)) \
         .group_by(Thema.naam) \
         .order_by(func.count(ThemaKoppeling.id).desc()) \
         .all()

        # Sorteren
        top3 = thema_counts[:3]

        # ─────────────────────────────────────────────
        # 5. Laatste vraag (nieuwste datum)
        # ─────────────────────────────────────────────
        laatste = max(v.ingediend for v in vragen)

        resultaat.append({
            "naam": f"{persoon.voornaam} {persoon.naam}",
            "populair": top3[0][0] if len(top3) >= 1 else None,
            "pop_count": top3[0][1] if len(top3) >= 1 else 0,
            "tweede": top3[1][0] if len(top3) >= 2 else None,
            "tweede_count": top3[1][1] if len(top3) >= 2 else 0,
            "derde": top3[2][0] if len(top3) >= 3 else None,
            "derde_count": top3[2][1] if len(top3) >= 3 else 0,
            "laatste_vraag": laatste
        })

    return render_template("statistieken_personen.html", data=resultaat)



# --- ACTIEFSTE VOLKSVERTEGENWOORDIGERS PER THEMA & KIESKRING ---


# Caching initialiseren (zet dit in je __init__.py of bovenaan routes-bestand)
from app import db, cache  # gebruik de cache die in __init__.py is geïnitialiseerd


@main.route('/statistieken/actiefste', methods=['GET'])
@cache.cached(timeout=3600, query_string=True)   # cache 1 uur per combinatie van parameters
def actiefste_per_thema_en_kieskring():
    try:
        # Alle kieskringen en thema's voor dropdowns
        kieskringen = [
            k[0] for k in (
                db.session.query(Persoon.kieskring)
                .distinct()
                .order_by(Persoon.kieskring)
                .all()
            )
            if k[0] is not None
        ]
        themas = [{"id": t.id, "naam": t.naam} for t in Thema.query.order_by(Thema.naam).all()]


        geselecteerde_kieskring = request.args.get('kieskring')
        geselecteerd_thema_id = request.args.get('thema')
        data = []

        if geselecteerde_kieskring and geselecteerd_thema_id:
            # 🔹 Subquery: enkel persoonfuncties in gekozen kieskring
            subq_pf = (
                db.session.query(Persoonfunctie.id)
                .join(Persoon, Persoon.id == Persoonfunctie.id_prs)
                .filter(Persoon.kieskring == geselecteerde_kieskring)
                .subquery()
            )

            # 🔹 Hoofdquery: gebruik subquery + filter vóór join
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
                .filter(Persoonfunctie.id.in_(subq_pf))  # 🔥 filter eerst
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








# ✅ Zorg dat cache in __init__.py staat, bijvoorbeeld:
# cache = Cache(config={'CACHE_TYPE': 'simple'})
# cache.init_app(app)

@main.route('/statistieken/priority')
@cache.cached(timeout=1800)  # cache 30 minuten
def statistieken_priority():
    try:
        # 🔹 Eén query die alles in één keer ophaalt
        rows = (
            db.session.query(
                SchriftelijkeVragen.id,
                SchriftelijkeVragen.onderwerp,
                SchriftelijkeVragen.ingediend,
                SchriftelijkeVragen.beantwoord,
                func.count(ThemaKoppeling.id_thm).label("aantal_themas")
            )
            .outerjoin(ThemaKoppeling, ThemaKoppeling.id_schv == SchriftelijkeVragen.id)
            .group_by(SchriftelijkeVragen.id)
            .all()
        )

        data = []
        vandaag = date.today()

        for r in rows:
            # --- Actualiteitsscore (laatste 100 dagen) ---
            if r.ingediend:
                dagen_verschil = (vandaag - r.ingediend).days
                # Enkel laatste 100 dagen tellen mee, daarna score = 0
                if dagen_verschil <= 100:
                    # Lineair afnemen: 100 → 0 over 100 dagen
                    recency_score = max(0, 100 - dagen_verschil)
                else:
                    recency_score = 0
            else:
                recency_score = 0

            # --- Themascore ---
            thema_score = min(50, r.aantal_themas * 12)

            # --- Bonus of straf ---
            antwoord_bonus = -20 if r.beantwoord else 0

            # --- Totale prioriteit ---
            total_score = max(0, recency_score + thema_score + antwoord_bonus)

            data.append({
                "onderwerp": r.onderwerp,
                "ingediend": r.ingediend.strftime("%Y-%m-%d") if r.ingediend else "-",
                "beantwoord": "Ja" if r.beantwoord else "Nee",
                "aantal_themas": r.aantal_themas,
                "priority_score": round(total_score, 1),
            })

        # 🔹 Sorteer op hoogste prioriteit
        data.sort(key=lambda x: x["priority_score"], reverse=True)

    except OperationalError:
        data = []

    return render_template("statistieken_priority.html", data=data)

@main.route('/volksvertegenwoordigers')
def volksvertegenwoordigers():
    try:
        rows = (
            db.session.query(
                Persoon.voornaam,
                Persoon.naam,
                Persoon.kieskring,
                Fractie.naam.label("fractie"),
                Functies.naam.label("functie")
            )
            .join(Persoonfunctie, Persoonfunctie.id_prs == Persoon.id)
            .join(Fractie, Fractie.id == Persoonfunctie.id_frc, isouter=True)
            .join(Functies, Functies.id == Persoonfunctie.id_fnc, isouter=True)
            .order_by(Persoon.naam)
            .all()
        )

        data = [
            {
                "naam": f"{r.voornaam} {r.naam}",
                "fractie": r.fractie or "-",
                "kieskring": r.kieskring or "-",
                "functie": r.functie or "-"
            }
            for r in rows
        ]
    except OperationalError:
        data = []

    return render_template("volksvertegenwoordigers.html", volksvertegenwoordigers=data)



@main.route('/zoeken', methods=['GET', 'POST'])
def zoeken():
    resultaten = []
    trefwoord = ""

    if request.method == 'POST':
        trefwoord = request.form.get('trefwoord', '').strip()

        if trefwoord:
            # 🔹 Fuzzy + LIKE search gecombineerd
            resultaten = (
                db.session.query(SchriftelijkeVragen)
                .filter(
                    (func.similarity(SchriftelijkeVragen.onderwerp, trefwoord) > 0.1) |
                    (func.similarity(SchriftelijkeVragen.tekst, trefwoord) > 0.1) |
                    (SchriftelijkeVragen.onderwerp.ilike(f"%{trefwoord}%")) |
                    (SchriftelijkeVragen.tekst.ilike(f"%{trefwoord}%"))
                )
                .order_by(
                    func.greatest(
                        func.similarity(SchriftelijkeVragen.onderwerp, trefwoord),
                        func.similarity(SchriftelijkeVragen.tekst, trefwoord)
                    ).desc(),
                    SchriftelijkeVragen.ingediend.desc()
                )
                .limit(100)  # ⏩ maximaal 100 resultaten voor snelheid
                .all()
            )
        else:
            # Geen trefwoord → geen resultaten (leeg)
            resultaten = []

    # GET-verzoek toont enkel de zoekbalk
    return render_template('zoeken.html', resultaten=resultaten, trefwoord=trefwoord)


# --- ACTIEVE THEMA'S PAGINA ---
#@main.route('/actieve_themas')
#def actieve_themas():
#    return render_template("actieve_themas.html")

# --- SCHRIFTELIJKE VRAGEN PAGINA ---
@main.route('/schriftelijke_vragen')
def schriftelijke_vragen():
    try:
        vragen = (
            db.session.query(SchriftelijkeVragen)
            .filter(SchriftelijkeVragen.ingediend.isnot(None))
            .order_by(SchriftelijkeVragen.ingediend.desc())
            .limit(50)
            .all()
        )

        data = []
        for v in vragen:
            pf = db.session.query(Persoonfunctie).get(v.id_prsfnc_vs)
            indiener = "-"
            fractie = "-"
            if pf:
                persoon = db.session.query(Persoon).get(pf.id_prs)
                fractie_obj = db.session.query(Fractie).get(pf.id_frc)
                if persoon:
                    indiener = f"{persoon.voornaam} {persoon.naam}"
                if fractie_obj:
                    fractie = fractie_obj.naam

            data.append({
                "onderwerp": v.onderwerp,
                "indiener": indiener,
                "fractie": fractie,
                "datum": v.ingediend.strftime("%Y-%m-%d") if v.ingediend else "-"
            })

        data.sort(key=lambda x: x["datum"], reverse=True)

    except OperationalError as e:
        print("❌ Databasefout:", e)
        data = []

    return render_template("schriftelijke_vragen.html", vragen=data)




#verwijst naar ons recomendation algoritme
from app.recommendations import vergelijkbare_vragen

@main.route("/vraag/<int:vraag_id>")
def vraag_detail(vraag_id):
    vraag = SchriftelijkeVragen.query.get_or_404(vraag_id)
    similar = vergelijkbare_vragen(vraag_id)

    return render_template("vraag_detail.html", vraag=vraag, similar=similar)

from app.recommendations import actieve_politici_for_thema

@main.route("/thema/<int:thema_id>")
def thema_detail(thema_id):
    thema = Thema.query.get_or_404(thema_id)
    actieve = actieve_politici_for_thema(thema_id)

    return render_template("thema_detail.html", thema=thema, actieve=actieve)



from datetime import timedelta

@main.route('/actieve_themas')
def actieve_themas():
    try:
        # 🔹 Bepaal de meest recente datum van indiening
        laatste_vraag_datum = db.session.query(func.max(SchriftelijkeVragen.ingediend)).scalar()

        if not laatste_vraag_datum:
            print("⚠️ Geen data gevonden in SchriftelijkeVragen.")
            return render_template("actieve_themas.html", data=[])

        # 🔹 Bereken het 30-dagenvenster vanaf die laatste vraag
        maand_geleden = laatste_vraag_datum - timedelta(days=30)
        vorige_maand_start = maand_geleden - timedelta(days=30)

        # 🔹 Vragen per thema in de 'laatste 30 dagen'
        recent = (
            db.session.query(Thema.naam, func.count(SchriftelijkeVragen.id).label("aantal"))
            .join(ThemaKoppeling, Thema.id == ThemaKoppeling.id_thm)
            .join(SchriftelijkeVragen, SchriftelijkeVragen.id == ThemaKoppeling.id_schv)
            .filter(SchriftelijkeVragen.ingediend.between(maand_geleden, laatste_vraag_datum))
            .group_by(Thema.naam)
            .order_by(func.count(SchriftelijkeVragen.id).desc())
            .limit(10)
            .all()
        )

        # 🔹 Zelfde thema’s maar vorige maand
        vorige = dict(
            db.session.query(Thema.naam, func.count(SchriftelijkeVragen.id))
            .join(ThemaKoppeling, Thema.id == ThemaKoppeling.id_thm)
            .join(SchriftelijkeVragen, SchriftelijkeVragen.id == ThemaKoppeling.id_schv)
            .filter(SchriftelijkeVragen.ingediend.between(vorige_maand_start, maand_geleden))
            .group_by(Thema.naam)
            .all()
        )

        data = []
        for naam, aantal in recent:
            oud = vorige.get(naam, 0)
            verschil = aantal - oud

            if oud == 0:
                pct = 0
                nieuw = True
            else:
                pct = round((verschil / oud * 100), 1)
                nieuw = False

            positief = pct >= 0
            data.append({
                "thema": naam,
                "aantal": aantal,
                "pct": pct,
                "positief": positief,
                "nieuw": nieuw
            })

    except Exception as e:
        print("⚠️ Fout in actieve_themas:", e)
        data = []

    return render_template("actieve_themas.html", data=data)



# grafieken 
from flask import render_template, jsonify, request
from datetime import date
from dateutil.relativedelta import relativedelta
from sqlalchemy import func
from app import db
from app.models import Thema, SchriftelijkeVragen, ThemaKoppeling


@main.route("/grafieken")
def grafieken():
    """Toont dropdown met alle thema’s."""
    themas = db.session.query(Thema).order_by(Thema.naam.asc()).all()
    return render_template("grafieken.html", themas=themas)


# --- DATA VOOR GRAFIEK PER THEMA ---
@main.route("/grafieken/data/<uuid:thema_id>")
def grafieken_data(thema_id):
    """Levert JSON met evolutie van vragen per maand voor gekozen thema."""
    eind_datum = date.today()
    begin_datum = eind_datum - relativedelta(months=12)

    # Aantal vragen per maand voor dit thema (laatste 12 maanden)
    results = (
        db.session.query(
            func.date_trunc("month", SchriftelijkeVragen.ingediend).label("maand"),
            func.count(SchriftelijkeVragen.id)
        )
        .join(ThemaKoppeling, ThemaKoppeling.id_schv == SchriftelijkeVragen.id)
        .filter(ThemaKoppeling.id_thm == thema_id)
        .filter(SchriftelijkeVragen.ingediend >= begin_datum)
        .group_by(func.date_trunc("month", SchriftelijkeVragen.ingediend))
        .order_by(func.date_trunc("month", SchriftelijkeVragen.ingediend))
        .all()
    )

    labels = [r[0].strftime("%b %Y") for r in results]
    values = [r[1] for r in results]

    return jsonify({"labels": labels, "values": values})


# --- AUTOCOMPLETE VOOR VOLKSVERTEGENWOORDIGERS ---
@main.route("/grafieken/vv_suggesties")
def vv_suggesties():
    """Zoekt volksvertegenwoordigers bij naam (voornaam + achternaam)."""
    from app.models import Persoon

    term = request.args.get("q", "").strip().lower()
    if not term:
        return jsonify([])

    suggesties = (
        db.session.query(Persoon)
        .filter(func.lower(Persoon.voornaam + ' ' + Persoon.naam).like(f"%{term}%"))
        .order_by(Persoon.naam.asc())
        .limit(10)
        .all()
    )

    return jsonify([
        {"id": str(p.id), "naam": f"{p.voornaam} {p.naam}"} for p in suggesties
    ])


# --- DATA VOOR GRAFIEK PER VOLKSVERTEGENWOORDIGER ---
@main.route("/grafieken/vv_data/<uuid:vv_id>")
def vv_data(vv_id):
    """Aantal schriftelijke vragen per maand voor gekozen volksvertegenwoordiger."""
    from app.models import Persoonfunctie  # importeren binnen de functie om circular import te vermijden

    eind_datum = date.today()
    begin_datum = eind_datum - relativedelta(months=12)

    results = (
        db.session.query(
            func.date_trunc("month", SchriftelijkeVragen.ingediend).label("maand"),
            func.count(SchriftelijkeVragen.id)
        )
        .join(Persoonfunctie, SchriftelijkeVragen.id_prsfnc_vs == Persoonfunctie.id)
        .filter(Persoonfunctie.id_prs == vv_id)
        .filter(SchriftelijkeVragen.ingediend >= begin_datum)
        .group_by(func.date_trunc("month", SchriftelijkeVragen.ingediend))
        .order_by(func.date_trunc("month", SchriftelijkeVragen.ingediend))
        .all()
    )

    labels = [r[0].strftime("%b %Y") for r in results]
    values = [r[1] for r in results]

    return jsonify({"labels": labels, "values": values})


# --- DETAILVRAGEN VOOR EEN VOLKSVERTEGENWOORDIGER IN EEN MAAND ---
@main.route("/grafieken/vv_vragen/<uuid:vv_id>/<int:jaar>/<int:maand>")
def vv_vragen_maand(vv_id, jaar, maand):
    """Geeft de lijst schriftelijke vragen van één VV in een specifieke maand."""
    from app.models import Persoonfunctie  # vermijden van circular import

    # Start- en einddatum van de maand bepalen
    van = date(jaar, maand, 1)
    tot = date(jaar + (maand // 12), (maand % 12) + 1, 1)

    # Query: alle vragen in die maand van die persoon
    vragen = (
        db.session.query(SchriftelijkeVragen)
        .join(Persoonfunctie, SchriftelijkeVragen.id_prsfnc_vs == Persoonfunctie.id)
        .filter(Persoonfunctie.id_prs == vv_id)
        .filter(SchriftelijkeVragen.ingediend >= van)
        .filter(SchriftelijkeVragen.ingediend < tot)
        .order_by(SchriftelijkeVragen.ingediend.desc())
        .all()
    )

    # ✅ Link naar PDF toevoegen (v.tekst bevat de URL)
    data = [
        {
            "datum": v.ingediend.strftime("%d/%m/%Y"),
            "onderwerp": v.onderwerp,
            "link": v.tekst if v.tekst and v.tekst.startswith("http") else None
        }
        for v in vragen
    ]

    return jsonify(data)


# --- DETAILVRAGEN VOOR EEN THEMA IN EEN MAAND ---
@main.route("/grafieken/thema_vragen/<uuid:thema_id>/<int:jaar>/<int:maand>")
def thema_vragen_maand(thema_id, jaar, maand):
    """Geeft de lijst schriftelijke vragen binnen één thema in een specifieke maand."""
    van = date(jaar, maand, 1)
    tot = date(jaar + (maand // 12), (maand % 12) + 1, 1)

    # Query: alle vragen van dat thema in die maand
    vragen = (
        db.session.query(SchriftelijkeVragen)
        .join(ThemaKoppeling, ThemaKoppeling.id_schv == SchriftelijkeVragen.id)
        .filter(ThemaKoppeling.id_thm == thema_id)
        .filter(SchriftelijkeVragen.ingediend >= van)
        .filter(SchriftelijkeVragen.ingediend < tot)
        .order_by(SchriftelijkeVragen.ingediend.desc())
        .all()
    )

    # ✅ Link naar PDF toevoegen (v.tekst bevat de URL)
    data = [
        {
            "datum": v.ingediend.strftime("%d/%m/%Y"),
            "onderwerp": v.onderwerp,
            "link": v.tekst if v.tekst and v.tekst.startswith("http") else None
        }
        for v in vragen
    ]

    return jsonify(data)
