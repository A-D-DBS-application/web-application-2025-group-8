from app.models import SchriftelijkeVragen, ThemaKoppeling, Thema, Persoon, Persoonfunctie
from app import db
from sqlalchemy import func
from datetime import datetime
import math


# ----------------------
# Helper: haal thema's per vraag op
# ----------------------
def get_themas_for_vraag(vraag_id):
    rows = (
        db.session.query(Thema.naam)
        .join(ThemaKoppeling, ThemaKoppeling.id_thm == Thema.id)
        .filter(ThemaKoppeling.id_schv == vraag_id)
        .all()
    )
    return [r[0] for r in rows]


# ----------------------
# HELPER: eenvoudige tekstsimilariteit
# ----------------------
def text_similarity(a, b):
    if not a or not b:
        return 0

    words_a = set(a.lower().split())
    words_b = set(b.lower().split())

    overlap = len(words_a & words_b)
    total = len(words_a | words_b)

    return overlap / total if total else 0


# ----------------------
# 1) GELIJKAARDIGE VRAGEN
# ----------------------
def vergelijkbare_vragen(vraag_id, limit=5):
    originele = SchriftelijkeVragen.query.get(vraag_id)
    if not originele:
        return []

    originele_themas = set(get_themas_for_vraag(vraag_id))

    alle_vragen = SchriftelijkeVragen.query.filter(
        SchriftelijkeVragen.id != vraag_id
    ).all()

    scores = []

    for v in alle_vragen:
        # thema-overlap
        v_themas = set(get_themas_for_vraag(v.id))
        thema_overlap = len(originele_themas & v_themas)

        # tekstgelijkenis
        tekst_score = text_similarity(originele.onderwerp, v.onderwerp)

        # recency
        dagen = (datetime.now().date() - v.ingediend).days if v.ingediend else 999
        recency = max(0, 1 - (dagen / 365))

        # totale score
        total = thema_overlap * 3 + tekst_score * 2 + recency

        scores.append((total, v))

    scores.sort(reverse=True, key=lambda x: x[0])

    return [v for _, v in scores[:limit]]


# ----------------------
# 2) ACTIEVE VOLKSVERTEGENWOORDIGERS PER THEMA
# ----------------------
def actieve_politici_for_thema(thema_id, limit=5):
    rows = (
        db.session.query(
            Persoon,
            func.count(SchriftelijkeVragen.id).label("aantal"),
            Fractie.naam.label("fractie")
        )
        .join(Persoonfunctie, Persoonfunctie.id_prs == Persoon.id)
        .join(SchriftelijkeVragen, SchriftelijkeVragen.id_prsfnc_vs == Persoonfunctie.id)
        .join(ThemaKoppeling, ThemaKoppeling.id_schv == SchriftelijkeVragen.id)
        .join(Fractie, Fractie.id == Persoonfunctie.id_frc)
        .filter(ThemaKoppeling.id_thm == thema_id)
        .group_by(Persoon.id, Fractie.naam)
        .order_by(func.count(SchriftelijkeVragen.id).desc())
        .limit(limit)
        .all()
    )

    data = []
    for persoon, aantal, fractie in rows:
        data.append({
            "naam": f"{persoon.voornaam} {persoon.naam}",
            "fractie": fractie,
            "kieskring": persoon.kieskring,
            "aantal_vragen": aantal
        })

    return data
