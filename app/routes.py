from flask import Blueprint, render_template, request
from app.models import Persoon, Fractie, Thema, SchriftelijkeVragen, Persoonfunctie, ThemaKoppeling, Functies
from sqlalchemy import func
from app import db, cache
from sqlalchemy.exc import OperationalError


# priority scoring algoritme 
from datetime import datetime, date

main = Blueprint('main', __name__)

# ---- HOOFDPAGINA ---
@main.route('/')
def index():
    try:
        # Statistieken (haalt op uit database), count functie want we willen aantallen
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

        # Recentste vragen: haalt 5 recentste vragen op
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
        fracties = [{'naam': f.naam, 'zetels': 0} for f in fracties_data] #maak ook lijst van fracties 

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
    ] #lijst van 4 dictionaries

    return render_template(
        'index.html',
        stats=stats_data,
        questions=vragen,
        themes=themes_data,
        fracties=fracties
    ) #stuurt alle data naar de pagina index.html


# --- OVERZICHTPAGINA STATISTIEKEN ---
@main.route('/statistieken') #'zegt' als iem naar statistieken pagina gaat
def statistieken_overzicht(): #voer deze functie uit
    return render_template('statistieken_overzicht.html') #geef deze pagina terug

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
            Thema.naam, #haal kolom naam ut tabel thema
            SchriftelijkeVragen.ingediend,
            SchriftelijkeVragen.beantwoord
        )
        .join(ThemaKoppeling, ThemaKoppeling.id_thm == Thema.id) #verbind thema  met themakoppeling via thema id
        .join(SchriftelijkeVragen, ThemaKoppeling.id_schv == SchriftelijkeVragen.id) #verbind themakoppeling met schriftelijke vragen via vraag id
        .filter(SchriftelijkeVragen.ingediend.isnot(None)) #weggooien van vragen zonder ingediend-datum (als dat een woord is)
        .filter(SchriftelijkeVragen.beantwoord.isnot(None)) #alleen vragen die beantwoord zijn
        .all() #all=verzamel alles dat hieraan voldoet
    ) #we hebben 3 tabellen thema, themakoppeling en schriftelijke vragen

    resultaten = {}
    for naam, ingediend, beantwoord in data: #loop door alle vragen
        try:
            # Zorg dat ook datetime.date objecten werken (niet enkel strings), we gaan ingediend omzetten naar een data() format
            if isinstance(ingediend, datetime): #controle: is het een datatime object
                d1 = ingediend.date() #ja : haal datum eruit
            else: #nee:: parse de string naar een dateobject
                d1 = datetime.strptime(str(ingediend), "%Y-%m-%d").date()

            if isinstance(beantwoord, datetime): #hier doe je zelfde maar dan voor beantwoordigsdata
                d2 = beantwoord.date()
            else:
                d2 = datetime.strptime(str(beantwoord), "%Y-%m-%d").date()

            dagen = (d2 - d1).days #bereken tijd tussen ingediend en beantwoord
            if dagen >= 0:  # geen negatieve waarden
                resultaten.setdefault(naam, []).append(dagen) #voeg toe aan resultaten dict met key= thema naam en value=lijst van alle wachttijden voor dat thema
        except Exception: #als iets misgaat: skip rij
            continue

    resultaten = [
        {"thema": k, "gem_dagen": round(sum(v) / len(v), 1)}
        for k, v in resultaten.items()
        if len(v) > 0
    ] #maakt dictionary met met de naam vh thema en als value de gemiddelde beantwoordingstijd

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
    ) #haal alle thema's per vraago op

    combinaties = {} #vind alle thema paren
    for _, ids in koppelingen:
        ids = list(set(ids)) #zet lijst om naar set om duplicaten te verwijderen: voorkomen dat we themas dubbel tellen in dezelfde vraav
        if len(ids) > 1: #alleen als er 2+ themas zijn kunnen we paren maken
            for i in range(len(ids)): #nested loop want we willen elk uniek paar(geen duplicaten,geen omgekeerde
                for j in range(i + 1, len(ids)):
                    paar = tuple(sorted([ids[i], ids[j]]))
                    combinaties[paar] = combinaties.get(paar, 0) + 1 

    id_to_naam = {t.id: t.naam for t in db.session.query(Thema).all()} #zet thema id terug om naar thema namen
    resultaten = [
        {"thema1": id_to_naam.get(a, "?"), "thema2": id_to_naam.get(b, "?"), "aantal": n}
        for (a, b), n in sorted(combinaties.items(), key=lambda x: x[1], reverse=True) #zet paren van IDs om naar paren van namen en sorteer vanv veel naar weinig(grootste netwerken eerst)
    ]

    return render_template("statistieken_thema_netwerk.html", resultaten=resultaten)



# --- STATISTIEKEN PER FRACTIE ---
@main.route('/statistieken/fractie', methods=['GET'])
def statistieken_fractie():
    from app.models import Fractie, Thema, Persoonfunctie

    # dropdowndata
    fracties = db.session.query(Fractie).order_by(Fractie.naam.asc()).all() #haal fracties op alfabeettisch gesorteerd (voor drop down)
    themas = db.session.query(Thema).order_by(Thema.naam.asc()).all() #idem als bij fracties

    fractie_id = request.args.get("fractie") #lezen waarde die gebruiker in de URL zet (via dropdowns)
    thema_id = request.args.get("thema")

    resultaat = None

    if fractie_id and thema_id:
        # totaal aantal vragen van deze fractie
        totaal_vragen_fractie = (
            db.session.query(SchriftelijkeVragen)
            .join(Persoonfunctie, SchriftelijkeVragen.id_prsfnc_vs == Persoonfunctie.id)
            .filter(Persoonfunctie.id_frc == fractie_id)
            .count()
        ) #Wat? Hoeveel vragen heeft deze fractie in TOTAAL gesteld
#hoe? query alle schriftelijke vragen, join: koppel schriftelijke vragen aan persoonsfunctie,filter:waar die persoon in deze fractie zit, count om ze te tellen
        # aantal vragen van fractie over dit thema
        thema_vragen_fractie = (
            db.session.query(SchriftelijkeVragen)
            .join(Persoonfunctie, SchriftelijkeVragen.id_prsfnc_vs == Persoonfunctie.id) #koppel aan persoonsfunctie(wie stelde de vraag?)
            .join(ThemaKoppeling, ThemaKoppeling.id_schv == SchriftelijkeVragen.id) #koppel aan themakoppeling(welke thema's heeft deze vraag?)
            .filter(Persoonfunctie.id_frc == fractie_id) #alleen deze fractie
            .filter(ThemaKoppeling.id_thm == thema_id) #alleen dit thema
            .count() #tel ze
        ) #Wat? Hoeveel vragen heeft de fractie over dit thema gesteld

        # totaal aantal vragen over dit thema (alle fracties)
        totaal_vragen_thema = (
            db.session.query(SchriftelijkeVragen)
            .join(ThemaKoppeling, ThemaKoppeling.id_schv == SchriftelijkeVragen.id) #koppel aan themakoppeling
            .filter(ThemaKoppeling.id_thm == thema_id) #alleen dit thema
            .count() #tel ze
        ) #Wat? Hoeveel vragen gaan over dit thema (van IEDEREEN)?

        perc_van_fractie = round((thema_vragen_fractie / totaal_vragen_fractie) * 100, 2) if totaal_vragen_fractie else 0 #van alle vragen over deze fractie, welk % is over dit thema?
        perc_van_thema = round((thema_vragen_fractie / totaal_vragen_thema) * 100, 2) if totaal_vragen_thema else 0 #van alle vragen van deze fractie, welk % komt van deze fractie?

        resultaat = {
            "totaal_vragen_fractie": totaal_vragen_fractie,
            "thema_vragen_fractie": thema_vragen_fractie,
            "totaal_vragen_thema": totaal_vragen_thema,
            "perc_van_fractie": perc_van_fractie,
            "perc_van_thema": perc_van_thema
        }

    return render_template(
        "statistieken_fracties.html",
        fracties=fracties,
        themas=themas,
        fractie_id=fractie_id,
        thema_id=thema_id,
        resultaat=resultaat
    ) #pak alles in resultaat en stuur naar template

#statistieken per volksvertegenwoordiger
@main.route("/statistieken/vv/themas")
def statistieken_vv_themas():
    sort = request.args.get("sort", "asc") #leest de sorteer-richting uit de query string
    kolom = request.args.get("kolom", "naam")  #leest op welke kolom gesorteerd moet worden: default:naam

    # Haal in één keer alle niet-minister functies met personen en thema’s op
    data = (
        db.session.query(
            Persoon.id,
            Persoon.voornaam,
            Persoon.naam,
            Thema.naam.label("thema"),
            func.count(SchriftelijkeVragen.id).label("aantal"),
            func.max(SchriftelijkeVragen.ingediend).label("laatste_vraag")
        )
        .join(Persoonfunctie, Persoonfunctie.id_prs == Persoon.id) #join om functies te kennen
        .join(Functies, Persoonfunctie.id_fnc == Functies.id) #join om functies te kennen
        .outerjoin(SchriftelijkeVragen, SchriftelijkeVragen.id_prsfnc_vs == Persoonfunctie.id)
        .outerjoin(ThemaKoppeling, ThemaKoppeling.id_schv == SchriftelijkeVragen.id) #outer join om ook personen zonder vragen te behouden
        .outerjoin(Thema, Thema.id == ThemaKoppeling.id_thm) #outer join om ook personen zonder thema te behouden
        .filter(~func.lower(Functies.naam).like("%minister%")) #sluit alle ministers uit
        .group_by(Persoon.id, Persoon.voornaam, Persoon.naam, Thema.naam) #groepeer op persoon+themanaam,zodat de count per persoon per thema komt
        .all()
    )

    # Groepeer resultaten per persoon
    personen_dict = {} #hadiger om mee te werken dan de 'raw query' resultaten want die bevatten nog duplicaten enz
    for r in data:
        if r.id not in personen_dict:
            personen_dict[r.id] = {
                "naam": f"{r.voornaam} {r.naam}",
                "themas": {},
                "laatste_vraag": r.laatste_vraag
            }
        if r.thema:
            personen_dict[r.id]["themas"][r.thema] = personen_dict[r.id]["themas"].get(r.thema, 0) + r.aantal #als r.thema bestaat, verhoog teller voor dat thema met r.aantal
        if r.laatste_vraag and (
            not personen_dict[r.id]["laatste_vraag"]
            or r.laatste_vraag > personen_dict[r.id]["laatste_vraag"]
        ):
            personen_dict[r.id]["laatste_vraag"] = r.laatste_vraag #update laatste_vraag als deze rij een latere datum heeft

    # Bepaal top 3 thema’s
    resultaat = []
    for persoon_id, info in personen_dict.items():
        the_dict = info["themas"]
        top3 = sorted(the_dict.items(), key=lambda x: x[1], reverse=True)[:3]
        resultaat.append({
            "naam": info["naam"],
            "populair": top3[0][0] if len(top3) >= 1 else None,
            "pop_count": top3[0][1] if len(top3) >= 1 else 0,
            "tweede": top3[1][0] if len(top3) >= 2 else None,
            "tweede_count": top3[1][1] if len(top3) >= 2 else 0,
            "derde": top3[2][0] if len(top3) >= 3 else None,
            "derde_count": top3[2][1] if len(top3) >= 3 else 0,
            "laatste_vraag": info["laatste_vraag"].strftime("%Y-%m-%d") if info["laatste_vraag"] else "-"
        })

    #  Dynamisch sorteren op kolom + richting
    reverse = sort == "desc"
    try: #probeer te sorteren op kolom die gebruiker koos in drop down
        resultaat.sort(
            key=lambda x: (x[kolom] or "").lower() if isinstance(x[kolom], str) else (x[kolom] or 0),
            reverse=reverse
        )
    except KeyError:
        # fallback als kolom niet bestaat, val dan terug op sorteren op naam
        resultaat.sort(key=lambda x: x["naam"].lower(), reverse=reverse)

    return render_template(
        "statistieken_vv_themas.html",
        data=resultaat,
        sort=sort,
        kolom=kolom
    ) #stuurt resultaat + sort parameters naar template




# --- ACTIEFSTE VOLKSVERTEGENWOORDIGERS PER THEMA & KIESKRING ---


# Caching initialiseren (zet dit in je __init__.py of bovenaan routes-bestand)
from app import db, cache  # gebruik de cache die in __init__.py is geïnitialiseerd


@main.route('/statistieken/actiefste', methods=['GET']) #politici in jou regio die meest actief zijn?
@cache.cached(timeout=3600, query_string=True)   # cache 1 uur per combinatie van parameters
def actiefste_per_thema_en_kieskring():
    try:
        # Alle kieskringen en thema's voor dropdowns
        kieskringen = [
            k[0] for k in (
                db.session.query(Persoon.kieskring)
                .distinct() #verwijder duplicaten
                .order_by(Persoon.kieskring) #sorteer automatisch
                .all()
            )
            if k[0] is not None
        ]
        themas = [{"id": t.id, "naam": t.naam} for t in Thema.query.order_by(Thema.naam).all()] #query alle thema's met id en naam
    #map naar lijst van dicts bv [{"id":1, "naam"= 'klimaat'},'{"id":2,"naam":'gezondheid'}

        geselecteerde_kieskring = request.args.get('kieskring') #lees filters uit query string, dus wat gebruiker koos
        geselecteerd_thema_id = request.args.get('thema') #idem
        data = []

        if geselecteerde_kieskring and geselecteerd_thema_id: #voor enkel query uit als beide filters zijn geselecteerd
            # 🔹 Subquery: enkel persoonfuncties in gekozen kieskring
            subq_pf = (
                db.session.query(Persoonfunctie.id) # doel:haal alle persoonfunctie_id's van persoon uit geselelecteerde kieskring
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
                    Persoon.kieskring, #welke persoon is het?
                    Fractie.naam.label("fractie_naam"), #van welke partij?
                    func.count(SchriftelijkeVragen.id).label("aantal_vragen"),
                ) #hoeveel vragen?
                .join(Persoonfunctie, Persoonfunctie.id_prs == Persoon.id) #wie heeft welke functie?
                .join(Fractie, Fractie.id == Persoonfunctie.id_frc) #welke partij
                .join(SchriftelijkeVragen, SchriftelijkeVragen.id_prsfnc_vs == Persoonfunctie.id) #welke vragen stelde deze persoon
                .join(ThemaKoppeling, ThemaKoppeling.id_schv == SchriftelijkeVragen.id) #over welke themas stelde hij vragen
                .filter(Persoonfunctie.id.in_(subq_pf))  # alleen uit door gebruiker geselecteerde kieskring
                .filter(ThemaKoppeling.id_thm == geselecteerd_thema_id) #alleen dit thema
                .group_by(
                    Persoon.id,
                    Persoon.voornaam,
                    Persoon.naam,
                    Persoon.kieskring,
                    Fractie.naam,
                ) #group by per persoon zodat je totaal aantal vragen per persoon voor dit thema krijgt
                .order_by(func.count(SchriftelijkeVragen.id).desc()) #aflopend op aantal vragen (MEEST ACTIEF EERST)
                .all()
            )

            for idx, r in enumerate(rows, start=1): #enumarate om een rangnummer toe te voegen(1,2,etc)
                data.append({
                    "rang": idx,
                    "naam": f"{r.voornaam} {r.naam}",
                    "fractie": r.fractie_naam,
                    "kieskring": r.kieskring,
                    "aantal_vragen": r.aantal_vragen,
                }) #hier bouwen we schone dictionaries  voor de template

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
#dus deze functie zegt:"Wie zijn de meest actieve politici in [kieskring X] op thema [Y]?"







# Zorg dat cache in __init__.py staat, bijvoorbeeld:
# cache = Cache(config={'CACHE_TYPE': 'simple'})
# cache.init_app(app)

# --- STATISTIEKEN PRIORITY SCORE SCHRIFTELIJKE VRAGEN ----
#merk op we beginnen hier te tellen vanaf 2025-10-15. Dit is omdat tot dan de data loopt. 
#Dit is makkelijk aan te passen in de toekomst indien nodig, wanneer er nieuwe data wordt ingeladen.
@main.route('/statistieken/priority')
@cache.cached(timeout=1800, query_string=True) #cache 30 min per query-string combinatie
def statistieken_priority():
    try:
        geselecteerd_thema_id = request.args.get('thema') #lees geselecteerd thema
        themas = db.session.query(Thema).order_by(Thema.naam.asc()).all() #haal alle thema's op voor dropdown

        # --- Basisquery ---, bouwt resultaat per vraag met aantal gekoppelde thema's en info over indiener
        query = ( 
            db.session.query(
                SchriftelijkeVragen.id,
                SchriftelijkeVragen.onderwerp,
                SchriftelijkeVragen.ingediend,
                SchriftelijkeVragen.tekst,  # bevat eventueel pdf-link
                Persoon.voornaam,
                Persoon.naam,
                func.count(ThemaKoppeling.id_thm).label("aantal_themas") #geeft aantal thema's per vraag
            )
            .outerjoin(ThemaKoppeling, ThemaKoppeling.id_schv == SchriftelijkeVragen.id) #behoud vragen zonder thema's
            .outerjoin(Persoonfunctie, Persoonfunctie.id == SchriftelijkeVragen.id_prsfnc_vs) #behoud vragen zonder personen
            .outerjoin(Persoon, Persoon.id == Persoonfunctie.id_prs) #behoud vragen waar persoonsfuncitie ontbreekt in dataset
            .group_by(SchriftelijkeVragen.id, Persoon.voornaam, Persoon.naam)
        ) #group by per vraag (tel thema's)

        # --- Filter op gekozen thema ---
        if geselecteerd_thema_id: #als gebruiker thema kies filter op vragen met dat thema
            query = query.filter( 
                SchriftelijkeVragen.id.in_(
                    db.session.query(ThemaKoppeling.id_schv)
                    .filter(ThemaKoppeling.id_thm == geselecteerd_thema_id)
                )
            ) #subquery haal alle vraag ID's op die dit thema hebben

        rows = query.all()
        data = []
        referentie = date(2025, 10, 15)  # aanpasbaar bij nieuwe dataset

        for r in rows:
            # --- RECENCY SCORE (max 70) ---
            if r.ingediend:
                dagen_verschil = (referentie - r.ingediend).days
                if dagen_verschil <= 0:
                    recency_score = 70 #vraag van vandaag:70 punten
                elif dagen_verschil <= 60:
                    recency_score = max(15, 70 - (dagen_verschil * 0.9)) #vraag van 30 dagen geleden
                else:
                    recency_score = 15 #vraag van 60+ dagen geleden
            else:
                recency_score = 0 #geen datum

            # --- THEMA SCORE (max 30) ---
            thema_score = min(30, r.aantal_themas * 6)

            # --- TOTAAL ---
            total_score = round(max(0, recency_score + thema_score), 1)
            total_score = min(total_score, 100) #sore optellen en op 100 zetten

            # --- PDF-link ---
            pdf_link = r.tekst if r.tekst and isinstance(r.tekst, str) and r.tekst.startswith("http") else None #kijk of tekst veld een url bevat, zo ja pak deze als pdf_link

            data.append({
                "onderwerp": r.onderwerp,
                "indiener": f"{r.voornaam or ''} {r.naam or ''}".strip(),
                "ingediend": r.ingediend.strftime("%Y-%m-%d") if r.ingediend else "-",
                "aantal_themas": r.aantal_themas,
                "priority_score": total_score,
                "pdf_url": pdf_link
            })

        data.sort(key=lambda x: x["priority_score"], reverse=True) #sorteer op prioriry score: van HOOG NAAR LAAG
        data = data[:200] #pak alleen top 200 (sneller,performance)

    except OperationalError:
        data, themas, geselecteerd_thema_id = [], [], None

    return render_template(
        "statistieken_priority.html",
        data=data,
        themas=themas,
        geselecteerd_thema_id=geselecteerd_thema_id
    )



#2e algoritme
#--- SAMENGESTELDE ACTIVITEITSSCORE VOLKSVERTEGENWOORDIGERS ---
def bereken_activiteitsscore(aantal_vragen, unieke_themas, gemiddelde_maanden_oud): #helper functie
    """
    Combineer aantal vragen, themadiversiteit en actualiteit in één samengestelde score.
    """
    # Recenter = hogere actualiteitsscore
    actualiteit_score = max(0, 1 - (gemiddelde_maanden_oud / 12))
    # Weging: 60% aantal vragen, 30% diversiteit, 10% recentheid
    return round((aantal_vragen * 0.6) + (unieke_themas * 0.3) + (actualiteit_score * 10), 2)


@main.route("/statistieken/vv")
def statistieken_vv():
    return render_template("statistieken_vv.html")


@main.route("/statistieken/activiteit")
@cache.cached(timeout=3600)
def activiteitsscore():
    """
    Toont de samengestelde activiteitsscore per volksvertegenwoordiger.
    Componenten:
    - Aantal schriftelijke vragen (volume)
    - Aantal unieke thema’s (diversiteit)
    - Gemiddelde ouderdom van vragen (actualiteit, in dagen)
    """
#query om per persoon aantal vragen, unieke thema's en alle indien datums op te halen
    rows = (
        db.session.query(
            Persoon.id.label("id"),
            Persoon.voornaam,
            Persoon.naam,
            Fractie.naam.label("fractie_naam"),
            func.count(func.distinct(SchriftelijkeVragen.id)).label("aantal_vragen"), #totaal unieke vragen per persoon
            func.count(func.distinct(ThemaKoppeling.id_thm)).label("unieke_themas"), #hoeveel verschillende thema's
            func.array_agg(func.distinct(SchriftelijkeVragen.ingediend)).label("alle_datums") #alle indien datums
        )
        .join(Persoonfunctie, Persoonfunctie.id_prs == Persoon.id) #vind functies van persoon
        .join(Fractie, Fractie.id == Persoonfunctie.id_frc) #vind partij van persoon (partij naam)
        .join(SchriftelijkeVragen, SchriftelijkeVragen.id_prsfnc_vs == Persoonfunctie.id) #vindt vragen van persoon, join is inner niet outer zodat personen zonder vragen verdwijnen
        .join(ThemaKoppeling, ThemaKoppeling.id_schv == SchriftelijkeVragen.id) #om thema gerelateerde aggregaten te kunnen berekenen
        .group_by(Persoon.id, Persoon.voornaam, Persoon.naam, Fractie.naam) #groepeer op persoon+partij zodat de aggregaten per persoon worden berekend
        .having(func.count(func.distinct(SchriftelijkeVragen.id)) > 3) #filter personen met minder dan 4 vragen (niet interessant)
        .all()
    ) #query per vv

    vandaag = date.today()
    data = []
#bereken gem aantal dagen oud
    for r in rows:
        datums = [d for d in (r.alle_datums or []) if d is not None]
        if datums:
            gemiddelde_dagen = sum((vandaag - d).days for d in datums) / len(datums)
        else:
            gemiddelde_dagen = 0

        score = bereken_activiteitsscore(r.aantal_vragen, r.unieke_themas, gemiddelde_dagen / 30) #roep helper functie aan om score te berekenen
        data.append({
            "naam": f"{r.voornaam} {r.naam}",
            "fractie": r.fractie_naam,
            "aantal_vragen": r.aantal_vragen,
            "unieke_themas": r.unieke_themas,
            "gem_dagen": round(gemiddelde_dagen, 1),
            "score": score,
        })

    data.sort(key=lambda x: x["score"], reverse=True) #meest actieve politicie eerst

    return render_template("statistieken_vv_activiteit.html", data=data)






# --- VOLKSVERTEGENWOORDIGERS MET PYTHON-SORTERING ---
@main.route('/volksvertegenwoordigers') #verkozenen pagina
def volksvertegenwoordigers():
    # Sorteervolgorde (asc of desc) en kolom via queryparameters
    sort = request.args.get("sort", "asc")
    kolom = request.args.get("kolom", "naam")  # standaard op naam

    try:
        # Query: haal alle gegevens in één keer op per persoon
        rows = (
            db.session.query(
                Persoon.id,
                Persoon.voornaam,
                Persoon.naam,
                Persoon.kieskring,
                Persoon.geboortedatum,
                Fractie.naam.label("fractie"), #partij naam
                Functies.naam.label("functie") #functieomschrijving
            )
            .join(Persoonfunctie, Persoonfunctie.id_prs == Persoon.id) #koppel persoon met persoonsfunctie(een persoon kan meerdere functies hebben)
            .join(Fractie, Fractie.id == Persoonfunctie.id_frc, isouter=True) #outerjoins zodat ook records zonder gekoppelde fractie/functie behouden worden
            .join(Functies, Functies.id == Persoonfunctie.id_fnc, isouter=True)
            .all()
        )

        # Leeftijd berekenen
        def bereken_leeftijd(geboortedatum):
            if geboortedatum: #als geboortedatum bestaat bereken dan de leeftijd
                vandaag = date.today()
                leeftijd = (
                    vandaag.year - geboortedatum.year -
                    ((vandaag.month, vandaag.day) < (geboortedatum.month, geboortedatum.day)) #check of al verjaard is dit jaar zo nee trek dan 1 af
                )
                return leeftijd
            return None

        # Structureren, door aanmaken LIJST VAN DICTS, gebruik van or om lege waarden te vervangen door "-"
        data = [
            {
                "id": r.id,
                "naam": f"{r.voornaam} {r.naam}",
                "leeftijd": bereken_leeftijd(r.geboortedatum),
                "fractie": r.fractie or "-",
                "kieskring": r.kieskring or "-",
                "functie": r.functie or "-"
            }
            for r in rows
        ]

        # Sorteren in Python (A–Z of Z–A op gekozen kolom)
        reverse = sort == "desc"
        data.sort(key=lambda x: (x[kolom] or "").lower() if isinstance(x[kolom], str) else (x[kolom] or 0), reverse=reverse) #sorteerd op door gebruiker gekozen kolom

    except OperationalError: #is er een fout zet data=[] om 500 te voorkomen
        data = []

    # Doorsturen naar template
    return render_template("volksvertegenwoordigers.html", volksvertegenwoordigers=data, sort=sort, kolom=kolom)



from uuid import UUID as UUIDType

@main.route('/vv/<uuid:vv_id>/vragen') #dit stukje code levert de pagina met schriftelijke vragen van één volksvertegenwoordiger
def vv_vragen(vv_id):
    """
    Toont schriftelijke vragen voor een persoon:
    - Als het een minister is: alle vragen die deze minister heeft BEANTWOORD (id_prsfnc_min)
    - Als het een gewone persoon is: alle vragen die deze persoon heeft INGEDIEND (id_prsfnc_vs)
    """
    try:
        # Haal persoon op
        persoon = Persoon.query.get_or_404(vv_id)
        
        # Check of persoon een minister is (functie bevat "minister" of code bevat "min")
        is_minister = (
            db.session.query(Persoonfunctie)
            .join(Functies, Functies.id == Persoonfunctie.id_fnc) #join om functies te kunnen checken
            .filter(Persoonfunctie.id_prs == vv_id) #beperk je tot persoonsfuncties voor de persoon met id=vv_id
            .filter(
                (func.lower(Functies.naam).like("%minister%")) |
                (func.lower(Functies.code).like("%min%"))
            ) #match met functienamen die de string 'minister' of 'min' bevatten
            .first() #first=haal de eerset match op, retourneert None als er geen match is
        ) is not None  # hiermee zet je resultaten om naar BOOLEAN: TRUE ALS MINISTER
        
        if is_minister:
            # Minister: toon vragen die deze persoon heeft BEANTWOORD
            persoonfuncties = (
                db.session.query(Persoonfunctie.id)
                .filter(Persoonfunctie.id_prs == vv_id) #haal alle persoonsfunctie id's op die bij deze minister horen
                .all()
            ) #verzameld dus alle functie id's van de gegeven persoon
            pf_ids = [pf.id for pf in persoonfuncties] #hier zitten alle vragen in die de minister heeft beantwoord
            
            if not pf_ids:
                vragen_rows = []
            else:
                vragen_rows = (
                    db.session.query(
                        SchriftelijkeVragen,
                        Persoon.voornaam,
                        Persoon.naam,
                        Fractie.naam.label("fractie_naam")
                    )
                    .filter(SchriftelijkeVragen.id_prsfnc_min.in_(pf_ids)) #hpud enkel vragen waarvan het veld id_prsfnc_min(de functie id vd beantwoordder) in de lijst pf_ids zit
                    .join(
                        Persoonfunctie,
                        SchriftelijkeVragen.id_prsfnc_vs == Persoonfunctie.id
                    ) #verbind de vraag met de persoonsfunctie die de vraag indiendee(indiener)
                    .join(Persoon, Persoon.id == Persoonfunctie.id_prs) #om voornaam en achernaam van indiener op te halen
                    .outerjoin(Fractie, Fractie.id == Persoonfunctie.id_frc) #om partij van indiener te tonen (outerjoin om te voorkomen dat een ontbrekende fractie de rij wegfiltert)
                    .order_by(SchriftelijkeVragen.ingediend.desc()) #sorteer op indien datum, nieuwste vragen eerst
                    .all()
                ) #vind alle vragen die deze minister heeft beantwoord
            
            title = f"Beantwoorde vragen - {persoon.voornaam} {persoon.naam}"
            
        else:
            # Gewone persoon: toon vragen die deze persoon heeft INGEDIEND
            persoonfuncties = (
                db.session.query(Persoonfunctie.id)
                .filter(Persoonfunctie.id_prs == vv_id)
                .all()
            ) #haal alle persoonsfunctie_id voor deze persoon op, resultaat een lijst van functie_id's
            pf_ids = [pf.id for pf in persoonfuncties] #zet query resultaat om naar python lijst van integers
            
            if not pf_ids:
                vragen_rows = [] #controleer of persoon uberhaupt functies heeft
            else:
                vragen_rows = (
                    db.session.query(
                        SchriftelijkeVragen,
                        Persoon.voornaam,
                        Persoon.naam,
                        Fractie.naam.label("fractie_naam")
                    )
                    .filter(SchriftelijkeVragen.id_prsfnc_vs.in_(pf_ids)) #houd vragen waarvan de indiener_functie in pf_ids staat
                    .join(  #we tonen de minister!
                        Persoonfunctie,
                        SchriftelijkeVragen.id_prsfnc_min == Persoonfunctie.id
                    ) #join om de functie van de minister te vinden die antoordde
                    .join(Persoon, Persoon.id == Persoonfunctie.id_prs) #haal voornaam en achternaam op van minister
                    .outerjoin(Fractie, Fractie.id == Persoonfunctie.id_frc) #outerjoin om partij van de beantwoorder te tonen(outer om geen rijen te verliezen indien geen fractie)
                    .order_by(SchriftelijkeVragen.ingediend.desc()) #sorteer op indien datum, nieuwste eerst
                    .all()
                )
            
            title = f"Ingediende vragen - {persoon.voornaam} {persoon.naam}"
        
        # Verwerk vragen in het formaat van de template
        data = []
        for row in vragen_rows:
            vraag = row.SchriftelijkeVragen
            indiener = f"{row.voornaam} {row.naam}" #maak volledige naam van persoon
            fractie = row.fractie_naam or "-" #haal fractie naam op
            
            # Probeer link uit tekst te extraheren
            link = vraag.tekst if vraag.tekst and vraag.tekst.startswith("http") else None
            
            data.append({
                "onderwerp": vraag.onderwerp,
                "indiener": indiener, #volledige naam van wie vraag stelde (normaal case), of beantwoorde(minister case)
                "fractie": fractie,
                "datum": vraag.ingediend.strftime("%Y-%m-%d") if vraag.ingediend else "-",
                "link": link
            })
        
        # Bepaal het type (minister of volksvertegenwoordiger) voor de info-sectie
        vv_type = "minister" if is_minister else "volksvertegenwoordiger" #zet of minister of volksvertegenwoordiger afhankelijk van de boleaan waarde is_minister
        vv_name = f"{persoon.voornaam} {persoon.naam}" #volledige naam van persoon waarvan je pagina bekijkt
        vraag_count = len(data) #tel hoeveel vragen er zijn
        
        return render_template(
            "schriftelijke_vragen.html",
            vragen=data, #lijst van vraag-dicts
            title=title,
            vv_type=vv_type,
            vv_name=vv_name,
            vraag_count=vraag_count
        )
        
    except OperationalError as e:
        print("❌ Databasefout:", e)
        return render_template("schriftelijke_vragen.html", vragen=[], title="Fout")



@main.route('/zoeken', methods=['GET', 'POST']) #zoek schriftelijke vragen
def zoeken(): #functie die zoekpagina en zoekactie afhandelt
    resultaten = [] #lege lijst om zoekresultaten in op te slaan
    trefwoord = "" #zoekterm,standaar leeg

    if request.method == 'POST': #alleen bij formulier verzending verwerken we de zoekterm
        trefwoord = request.form.get('trefwoord', '').strip() #haal trefwoord uit het POST formulier, verwijder eventuele leading/trailing spaces

        if trefwoord: #alleen zoeken als de gebruiker iets invulde
            #  Fuzzy + LIKE search gecombineerd,fuzzy vangt spelfouten en nabije matches, Like vangt impliciete substring op
            vragen = (
                db.session.query(SchriftelijkeVragen)
                .filter(
                    (func.similarity(SchriftelijkeVragen.onderwerp, trefwoord) > 0.1) | #vind fuzzy overeenkomsten tussen onderwerp en trerfwoord
                    (func.similarity(SchriftelijkeVragen.tekst, trefwoord) > 0.1) | #idem fuzzy-vergelijking maar dan voor het tekstveld
                    (SchriftelijkeVragen.onderwerp.ilike(f"%{trefwoord}%")) | #case-insensitive substring match op onderwerp
                    (SchriftelijkeVragen.tekst.ilike(f"%{trefwoord}%")) #case insensitive substring-match op tekst
                ) #deze 4 condities zijn OR gecombineerd: een vraag matcht als 1 van de 4 condities waar is
                .order_by(
                    func.greatest( #neem hoogste van 2 similarity scores (onderwerp of tekst)
                        func.similarity(SchriftelijkeVragen.onderwerp, trefwoord),
                        func.similarity(SchriftelijkeVragen.tekst, trefwoord) #sorteer op grootste similarity score tussen onderwerp en tekst, aflopend => meest relevante matches bovenaan, daaarna sorter
                    ).desc(),
                    SchriftelijkeVragen.ingediend.desc() #sorteer bij gelijke score op datum (tie breaker)
                ) 
                .limit(100) #neem max 100 resultaten
                .all()
            ) #resultaat is lijst van schriftelijke vragen

            from app.models import Persoonfunctie, Persoon, Fractie

            #  Verrijk met indiener + fractie + link
            for v in vragen:
                pf = db.session.query(Persoonfunctie).get(v.id_prsfnc_vs) #haal de persoonsfunctie rij op die de indiener van deze vraag representeert
                indiener = "-" #default
                fractie = "-" #default
                if pf: #als persoonsfunctie bestaat
                    persoon = db.session.query(Persoon).get(pf.id_prs) #haal de persoon op
                    fractie_obj = db.session.query(Fractie).get(pf.id_frc) #haal de partij op
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
    #Vaste periode: van april t.e.m. oktober 2025. Bij inladen nieuwe data, pas dit aan indien nodig. 
    #nog makkelijker: in de afgewerkte versie (dus niet-mvp) zal de data hele zitjaren bevatten, dus kunnen deze data weg.
    #hier is dit nu enkel om de grafiek te tonen met de huidige, beperkte data waarvoor wij gekozen hebben in de mvp
    begin_datum = date(2025, 4, 1)
    eind_datum = date(2025, 10, 31)

    resultaten = (
        db.session.query(
            func.date_trunc("month", SchriftelijkeVragen.ingediend).label("maand"),
            func.count(SchriftelijkeVragen.id)
        )
        .join(ThemaKoppeling, ThemaKoppeling.id_schv == SchriftelijkeVragen.id)
        .filter(ThemaKoppeling.id_thm == thema_id)
        .filter(SchriftelijkeVragen.ingediend >= begin_datum)
        .filter(SchriftelijkeVragen.ingediend <= eind_datum)
        .group_by(func.date_trunc("month", SchriftelijkeVragen.ingediend))
        .order_by(func.date_trunc("month", SchriftelijkeVragen.ingediend))
        .all()
    )

    maand_dict = {r[0].strftime("%Y-%m"): r[1] for r in resultaten}

    labels, values = [], []
    huidige = begin_datum
    maanden = ["jan", "feb", "mrt", "apr", "mei", "jun", "jul", "aug", "sep", "okt", "nov", "dec"]

    while huidige <= eind_datum:
        key = huidige.strftime("%Y-%m")
        labels.append(f"{maanden[huidige.month - 1]} {huidige.year}")
        values.append(maand_dict.get(key, 0))
        huidige += relativedelta(months=1)

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
@main.route("/grafieken/vv_data/<uuid:vv_id>")
def vv_data(vv_id):
    from app.models import Persoonfunctie

    # ✅ Zelfde vaste periode: april → oktober
    begin_datum = date(2025, 4, 1)
    eind_datum = date(2025, 10, 31)

    resultaten = (
        db.session.query(
            func.date_trunc("month", SchriftelijkeVragen.ingediend).label("maand"),
            func.count(SchriftelijkeVragen.id)
        )
        .join(Persoonfunctie, SchriftelijkeVragen.id_prsfnc_vs == Persoonfunctie.id)
        .filter(Persoonfunctie.id_prs == vv_id)
        .filter(SchriftelijkeVragen.ingediend >= begin_datum)
        .filter(SchriftelijkeVragen.ingediend <= eind_datum)
        .group_by(func.date_trunc("month", SchriftelijkeVragen.ingediend))
        .order_by(func.date_trunc("month", SchriftelijkeVragen.ingediend))
        .all()
    )

    maand_dict = {r[0].strftime("%Y-%m"): r[1] for r in resultaten}

    labels, values = [], []
    huidige = begin_datum
    maanden = ["jan", "feb", "mrt", "apr", "mei", "jun", "jul", "aug", "sep", "okt", "nov", "dec"]

    while huidige <= eind_datum:
        key = huidige.strftime("%Y-%m")
        labels.append(f"{maanden[huidige.month - 1]} {huidige.year}")
        values.append(maand_dict.get(key, 0))
        huidige += relativedelta(months=1)

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

