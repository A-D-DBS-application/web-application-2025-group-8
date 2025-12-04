from flask import Blueprint, render_template, request
from app.models import Persoon, Fractie, Thema, SchriftelijkeVragen, Persoonfunctie, ThemaKoppeling, Functies
from sqlalchemy import func
from app import db
from sqlalchemy.exc import OperationalError
from flask_caching import Cache

# priority scoring algoritme 
from datetime import datetime, date

main = Blueprint('main', __name__)

# ---- HOOFDPAGINA ----
@main.route('/')
def index():
    try:
        # Korte statistieken
        aantal_vragen = db.session.query(func.count(SchriftelijkeVragen.id)).scalar() or 0
        aantal_themas = db.session.query(func.count(Thema.id)).scalar() or 0
        aantal_personen = db.session.query(func.count(Persoon.id)).scalar() or 0
        aantal_beantwoord = db.session.query(func.count(SchriftelijkeVragen.id)).filter(SchriftelijkeVragen.beantwoord.isnot(None)).scalar() or 0

        # Recente vragen en thema's en fracties om op de homepage te tonen
        vragen = db.session.query(SchriftelijkeVragen).order_by(SchriftelijkeVragen.ingediend.desc()).limit(10).all()
        themas = db.session.query(Thema).order_by(Thema.naam.asc()).limit(10).all()
        fracties = db.session.query(Fractie).order_by(Fractie.naam.asc()).all()

        stats_data = [
            {'label': 'Schriftelijke Vragen', 'value': aantal_vragen, 'icon': 'file-text'},
            {'label': 'Actieve Thema’s', 'value': aantal_themas, 'icon': 'tag'},
            {'label': 'Volksvertegenwoordigers', 'value': aantal_personen, 'icon': 'users'},
            {'label': 'Beantwoorde Vragen', 'value': f"{aantal_beantwoord}/{aantal_vragen}" if aantal_vragen else "0", 'icon': 'trending-up'},
        ]

    except OperationalError:
        stats_data = []
        vragen = []
        themas = []
        fracties = []

    return render_template(
        'index.html',
        stats=stats_data,
        questions=vragen,
        themes=themas,
        fracties=fracties
    )


# --- OVERZICHTPAGINA STATISTIEKEN ---
@main.route('/statistieken')
def statistieken_overzicht():
    return render_template('statistieken_overzicht.html')

# --- STATISTIEKEN PER THEMA ---

@main.route('/statistieken/themas')
def statistieken_themas():
    """Toont de keuze tussen de 2 thematische analyses."""
    return render_template('statistieken_themas.html')


# --- GEMIDDELDE BEANTWOORDINGSSNELHEID PER THEMA ---
from datetime import datetime

@main.route("/statistieken/thema_beantwoordtijd")
def statistieken_thema_beantwoordtijd():
    """Bereken gemiddelde beantwoordingstijd (in dagen) per thema."""
    data = (
        db.session.query(
            Thema.naam,
            SchriftelijkeVragen.ingediend,
            SchriftelijkeVragen.beantwoord
        )
        .join(ThemaKoppeling, ThemaKoppeling.id_thm == Thema.id)
        .join(SchriftelijkeVragen, ThemaKoppeling.id_schv == SchriftelijkeVragen.id)
        .filter(SchriftelijkeVragen.ingediend.isnot(None))
        .filter(SchriftelijkeVragen.beantwoord.isnot(None))
        .all()
    )

    resultaten = {}
    for naam, ingediend, beantwoord in data:
        try:
            # Zorg dat ook datetime.date objecten werken (niet enkel strings)
            if isinstance(ingediend, datetime):
                d1 = ingediend.date()
            else:
                d1 = datetime.strptime(str(ingediend), "%Y-%m-%d").date()

            if isinstance(beantwoord, datetime):
                d2 = beantwoord.date()
            else:
                d2 = datetime.strptime(str(beantwoord), "%Y-%m-%d").date()

            dagen = (d2 - d1).days
            if dagen >= 0:  # geen negatieve waarden
                resultaten.setdefault(naam, []).append(dagen)
        except Exception:
            continue

    resultaten = [
        {"thema": k, "gem_dagen": round(sum(v) / len(v), 1)}
        for k, v in resultaten.items()
        if len(v) > 0
    ]

    # Sorteer van snelst naar traagst
    resultaten.sort(key=lambda x: x["gem_dagen"])

    return render_template("statistieken_thema_beantwoordtijd.html", resultaten=resultaten)



# --- NETWERK VAN SAMENHANGENDE THEMA’S ---
@main.route("/statistieken/thema_netwerk")
def statistieken_thema_netwerk():
    """Berekent hoe vaak thema’s samen in dezelfde vraag voorkomen."""
    from app.models import Thema, ThemaKoppeling

    koppelingen = (
        db.session.query(ThemaKoppeling.id_schv, func.array_agg(ThemaKoppeling.id_thm))
        .group_by(ThemaKoppeling.id_schv)
        .all()
    )

    combinaties = {}
    for _, ids in koppelingen:
        ids = list(set(ids))
        if len(ids) > 1:
            for i in range(len(ids)):
                for j in range(i + 1, len(ids)):
                    paar = tuple(sorted([ids[i], ids[j]]))
                    combinaties[paar] = combinaties.get(paar, 0) + 1

    id_to_naam = {t.id: t.naam for t in db.session.query(Thema).all()}
    resultaten = [
        {"thema1": id_to_naam.get(a, "?"), "thema2": id_to_naam.get(b, "?"), "aantal": n}
        for (a, b), n in sorted(combinaties.items(), key=lambda x: x[1], reverse=True)
    ]

    return render_template("statistieken_thema_netwerk.html", resultaten=resultaten)



# --- STATISTIEKEN PER FRACTIE ---
@main.route('/statistieken/fractie')
def statistieken_fractie():
    """Toont dropdowns om fractie en thema te kiezen."""
    from app.models import Fractie, Thema
    fracties = db.session.query(Fractie).order_by(Fractie.naam.asc()).all()
    themas = db.session.query(Thema).order_by(Thema.naam.asc()).all()
    return render_template('statistieken_fracties.html', fracties=fracties, themas=themas)


@main.route("/statistieken/fractie/data/<uuid:fractie_id>/<uuid:thema_id>")
def statistieken_fractie_data(fractie_id, thema_id):
    """Geeft statistieken over 1 fractie en 1 thema."""
    from app.models import Persoonfunctie  # om circular import te vermijden

    # Totaal aantal vragen van de fractie
    totaal_vragen_fractie = (
        db.session.query(SchriftelijkeVragen)
        .join(Persoonfunctie, SchriftelijkeVragen.id_prsfnc_vs == Persoonfunctie.id)
        .filter(Persoonfunctie.id_frc == fractie_id)
        .count()
    )

    # Aantal vragen van deze fractie over dit thema
    thema_vragen_fractie = (
        db.session.query(SchriftelijkeVragen)
        .join(Persoonfunctie, SchriftelijkeVragen.id_prsfnc_vs == Persoonfunctie.id)
        .join(ThemaKoppeling, ThemaKoppeling.id_schv == SchriftelijkeVragen.id)
        .filter(Persoonfunctie.id_frc == fractie_id)
        .filter(ThemaKoppeling.id_thm == thema_id)
        .count()
    )

    # Totaal aantal vragen over dit thema (alle fracties samen)
    totaal_vragen_thema = (
        db.session.query(SchriftelijkeVragen)
        .join(ThemaKoppeling, ThemaKoppeling.id_schv == SchriftelijkeVragen.id)
        .filter(ThemaKoppeling.id_thm == thema_id)
        .count()
    )

    # Berekeningen
    perc_van_fractie = round((thema_vragen_fractie / totaal_vragen_fractie) * 100, 2) if totaal_vragen_fractie else 0
    perc_van_thema = round((thema_vragen_fractie / totaal_vragen_thema) * 100, 2) if totaal_vragen_thema else 0

    return jsonify({
        "totaal_vragen_fractie": totaal_vragen_fractie,
        "thema_vragen_fractie": thema_vragen_fractie,
        "perc_van_fractie": perc_van_fractie,
        "totaal_vragen_thema": totaal_vragen_thema,
        "perc_van_thema": perc_van_thema
    })


# --- STATISTIEKEN PER PERSOON ---
@main.route("/statistieken/personen")
def statistieken_personen():
    # 1. Haal alle personen op
    personen = Persoon.query.all()

    resultaat = []

    for persoon in personen:

        # 2. Haal alle functies op + JOIN naar Functies
        functies = (
            db.session.query(Persoonfunctie, Functies)
            .join(Functies, Persoonfunctie.id_fnc == Functies.id)
            .filter(Persoonfunctie.id_prs == persoon.id)
            .all()
        )

        if not functies:
            continue

        # 3. ➤ FILTER: Als één van de functies "minister" bevat → skip
        if any("minister" in f2.naam.lower() for f1, f2 in functies):
            continue

        # 4. lijst van persoonfunctie-ID's
        functie_ids = [f1.id for f1, f2 in functies]

        # 5. Haal alle vragen van deze persoon
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

        # 6. Thema’s tellen
        thema_counts = (
            db.session.query(Thema.naam, func.count(ThemaKoppeling.id))
            .join(ThemaKoppeling, Thema.id == ThemaKoppeling.id_thm)
            .join(SchriftelijkeVragen, SchriftelijkeVragen.id == ThemaKoppeling.id_schv)
            .filter(SchriftelijkeVragen.id_prsfnc_vs.in_(functie_ids))
            .group_by(Thema.naam)
            .order_by(func.count(ThemaKoppeling.id).desc())
            .all()
        )

        top3 = thema_counts[:3]

        # 7. Laatste vraag
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


# --- STATISTIEKEN PRIORITY SCORE SCHRIFTELIJKE VRAGEN ---
#merk op we beginnen hier te tellen vanaf 2025-10-15. Dit is omdat tot dan de data loopt. 
#Dit is makkelijk aan te passen in de toekomst indien nodig, wanneer er nieuwe data wordt ingeladen.
@main.route('/statistieken/priority')
@cache.cached(timeout=1800)
def statistieken_priority():
    try:
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
        referentie = date(2025, 10, 15)  # <<< eventueel aanpassen bij nieuwe dataset

        for r in rows:
            # --- RECENCY SCORE (max 90) ---
            if r.ingediend:
                dagen_verschil = (referentie - r.ingediend).days
                if dagen_verschil <= 0:
                    recency_score = 90
                elif dagen_verschil <= 60:
                    recency_score = max(20, 90 - (dagen_verschil * 1.1))
                else:
                    recency_score = 20
            else:
                recency_score = 0

            # --- THEMA SCORE (max 30) ---
            thema_score = min(30, r.aantal_themas * 6)

            # --- BONUS/STRAF ---
            antwoord_bonus = -10 if r.beantwoord else 0

            # --- TOTAAL ---
            total_score = round(max(0, recency_score + thema_score + antwoord_bonus), 1)
            if total_score > 100:
                total_score = 100

            data.append({
                "onderwerp": r.onderwerp,
                "ingediend": r.ingediend.strftime("%Y-%m-%d") if r.ingediend else "-",
                "aantal_themas": r.aantal_themas,
                "priority_score": total_score,
            })

        # sorteer op hoogste score en toon enkel top 100
        data.sort(key=lambda x: x["priority_score"], reverse=True)
        data = data[:200]

    except OperationalError:
        data = []

    return render_template("statistieken_priority.html", data=data)





from datetime import date
from sqlalchemy.exc import OperationalError

@main.route('/volksvertegenwoordigers')
def volksvertegenwoordigers():
    try:
        # Haal alle personen; we selecteren ook de id zodat we links kunnen maken
        rows = (
            db.session.query(
                Persoon.id,
                Persoon.voornaam,
                Persoon.naam,
                Persoon.kieskring,
                Persoon.geboortedatum,
                Fractie.naam.label("fractie"),
                Functies.naam.label("functie")
            )
            .join(Persoonfunctie, Persoonfunctie.id_prs == Persoon.id)
            .join(Fractie, Fractie.id == Persoonfunctie.id_frc, isouter=True)
            .join(Functies, Functies.id == Persoonfunctie.id_fnc, isouter=True)
            .distinct(Persoon.id)
            .order_by(Persoon.id, Persoon.naam)
            .all()
        )

        def bereken_leeftijd(geboortedatum):
            if geboortedatum:
                vandaag = date.today()
                leeftijd = (
                    vandaag.year - geboortedatum.year -
                    ((vandaag.month, vandaag.day) < (geboortedatum.month, geboortedatum.day))
                )
                return leeftijd
            return "-"

        data = [
            {
                "id": str(r.id),
                "naam": f"{r.voornaam} {r.naam}",
                "leeftijd": bereken_leeftijd(r.geboortedatum),
                "fractie": r.fractie or "-",
                "kieskring": r.kieskring or "-",
                "functie": r.functie or "-"
            }
            for r in rows
        ]

    except OperationalError:
        data = []

    return render_template("volksvertegenwoordigers.html", volksvertegenwoordigers=data)



# --- DETAIL LIJST VAN VRAGEN VOOR EEN VOLKSVERTEGENWOORDIGER ---
@main.route('/vv/<uuid:vv_id>/vragen')
def vv_vragen(vv_id):
    try:
        # Haal persoon op
        persoon = Persoon.query.get_or_404(vv_id)

        # alle persoonfunctie ids voor deze persoon
        prsfncs = db.session.query(Persoonfunctie).filter(Persoonfunctie.id_prs == vv_id).all()
        prsfnc_ids = [p.id for p in prsfncs]

        # Bepaal of deze persoon een minister is: check functienaam/code op 'minister' of 'min'
        minister_functie = (
            db.session.query(Functies)
            .join(Persoonfunctie, Persoonfunctie.id_fnc == Functies.id)
            .filter(Persoonfunctie.id_prs == vv_id)
            .filter(
                (func.lower(Functies.naam).like("%minister%")) |
                (func.lower(Functies.code).like("%min%"))
            )
            .first()
        )

        vragen_q = []
        title = f"Schriftelijke vragen van {persoon.voornaam} {persoon.naam}"

        if minister_functie:
            # Voor ministers: toon beantwoorde vragen waarvoor zij de ontvanger/minister waren
            vragen = (
                db.session.query(SchriftelijkeVragen)
                .filter(SchriftelijkeVragen.id_prsfnc_min.in_(prsfnc_ids))
                .filter(SchriftelijkeVragen.beantwoord.isnot(None))
                .order_by(SchriftelijkeVragen.beantwoord.desc())
                .all()
            )
            title = f"Beantwoorde vragen voor {persoon.voornaam} {persoon.naam}"
            # Bepaal de fractie van de minister (indien beschikbaar)
            minister_fractie = None
            minister_pf_current = (
                db.session.query(Persoonfunctie)
                .filter(Persoonfunctie.id_prs == vv_id, Persoonfunctie.id_frc.isnot(None), Persoonfunctie.tot.is_(None))
                .first()
            )
            if not minister_pf_current:
                minister_pf_current = (
                    db.session.query(Persoonfunctie)
                    .filter(Persoonfunctie.id_prs == vv_id, Persoonfunctie.id_frc.isnot(None))
                    .first()
                )
            if minister_pf_current and minister_pf_current.id_frc:
                fmin = db.session.query(Fractie).get(minister_pf_current.id_frc)
                minister_fractie = fmin.naam if fmin else None

            for v in vragen:
                # Haal de indiener op via de persoonfunctie die de vraag indiende
                indiener_naam = None
                try:
                    pf_sub = db.session.query(Persoonfunctie).filter(Persoonfunctie.id == v.id_prsfnc_vs).first()
                    if pf_sub and pf_sub.id_prs:
                        p_sub = db.session.query(Persoon).get(pf_sub.id_prs)
                        if p_sub:
                            indiener_naam = f"{p_sub.voornaam} {p_sub.naam}"
                except Exception:
                    indiener_naam = None

                vragen_q.append({
                    "onderwerp": v.onderwerp,
                    "indiener": indiener_naam,
                    "fractie": minister_fractie,
                    "datum": v.beantwoord.strftime("%d/%m/%Y") if v.beantwoord else "-",
                    "link": v.tekst if v.tekst and isinstance(v.tekst, str) and v.tekst.startswith("http") else None
                })
        else:
            # Voor gewone volksvertegenwoordigers: toon vragen die zij indienden
            vragen = (
                db.session.query(SchriftelijkeVragen, Persoonfunctie)
                .join(Persoonfunctie, SchriftelijkeVragen.id_prsfnc_vs == Persoonfunctie.id)
                .filter(Persoonfunctie.id_prs == vv_id)
                .order_by(SchriftelijkeVragen.ingediend.desc())
                .all()
            )

            for v, pf in vragen:
                # probeer fractie-naam op te halen uit persoonfunctie (kan None zijn)
                fractie_naam = None
                if pf and pf.id_frc:
                    f = db.session.query(Fractie).get(pf.id_frc)
                    fractie_naam = f.naam if f else None

                vragen_q.append({
                    "onderwerp": v.onderwerp,
                    "indiener": f"{persoon.voornaam} {persoon.naam}",
                    "fractie": fractie_naam,
                    "datum": v.ingediend.strftime("%d/%m/%Y") if v.ingediend else "-",
                    "link": v.tekst if v.tekst and isinstance(v.tekst, str) and v.tekst.startswith("http") else None
                })

    except OperationalError:
        vragen_q = []
        title = "Schriftelijke vragen"

    return render_template('schriftelijke_vragen.html', vragen=vragen_q, title=title)



@main.route('/zoeken', methods=['GET', 'POST'])
def zoeken():
    resultaten = []
    trefwoord = ""

    if request.method == 'POST':
        trefwoord = request.form.get('trefwoord', '').strip()

        if trefwoord:
            # 🔹 Fuzzy + LIKE search gecombineerd
            vragen = (
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
                .limit(100)
                .all()
            )

            from app.models import Persoonfunctie, Persoon, Fractie

            # 🔹 Verrijk met indiener + fractie + link
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

                resultaten.append({
                    "onderwerp": v.onderwerp,
                    "indiener": indiener,
                    "fractie": fractie,
                    "datum": v.ingediend.strftime("%Y-%m-%d") if v.ingediend else "-",
                    "link": v.tekst if v.tekst and v.tekst.startswith("http") else None
                })

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

            # ✅ Nieuw: link toevoegen als het een echte URL is
            link = v.tekst if v.tekst and v.tekst.startswith("http") else None

            data.append({
                "onderwerp": v.onderwerp,
                "indiener": indiener,
                "fractie": fractie,
                "datum": v.ingediend.strftime("%Y-%m-%d") if v.ingediend else "-",
                "link": link
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

    maanden = ["jan", "feb", "mrt", "apr", "mei", "jun",
           "jul", "aug", "sep", "okt", "nov", "dec"]

    labels = [f"{maanden[r[0].month - 1]} {r[0].year}" for r in results]

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

