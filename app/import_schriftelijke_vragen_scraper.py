import os
import re
import uuid
import time
import requests
import xml.etree.ElementTree as ET
from io import BytesIO
from PyPDF2 import PdfReader
from dotenv import load_dotenv
from supabase import create_client

# === CONFIG ===
load_dotenv()
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# === CONSTANTEN ===
FUNCTIE_VV = "11111111-aaaa-4bbb-cccc-000000000001"  # Volksvertegenwoordiger
FUNCTIE_MIN = "11111111-aaaa-4bbb-cccc-000000000003"  # Minister
BASE_DETAIL_URL = "https://ws.vlpar.be/e/opendata/schv/"
BASE_API_URL = (
    "https://ws.vlpar.be/api/search/query/"
    "+inmeta:legislatuur=2024-2029"
    "&requiredfields=paginatype:Parlementair%20document."
    "aggregaat:Vraag%20of%20interpellatie."
    "aggregaattype:Schriftelijke%20vraag"
    "?collection=vp_collection&sort=date&order=desc&max=25&page={page}"
)

# === HELPERS ===
def extract_text_from_pdf(pdf_bytes: bytes) -> str:
    """Haalt tekst uit een PDF."""
    text = ""
    try:
        reader = PdfReader(BytesIO(pdf_bytes))
        for page in reader.pages:
            text += page.extract_text() or ""
    except Exception as e:
        print(f"⚠️ PDF extractie mislukt: {e}")
    return text.strip()


def get_persoonfunctie_id(voornaam: str, naam: str, functie_uuid: str):
    """Zoekt de juiste persoonfunctie-id op basis van naam/voornaam."""
    if not voornaam or not naam:
        return None
    res = supabase.table("persoon") \
        .select("id, naam, voornaam") \
        .ilike("naam", f"%{naam}%") \
        .ilike("voornaam", f"%{voornaam}%") \
        .execute().data
    if not res:
        print(f"⚠️ Geen persoon gevonden: {voornaam} {naam}")
        return None
    id_prs = res[0]["id"]
    pf = supabase.table("persoonfunctie") \
        .select("id") \
        .eq("id_prs", id_prs) \
        .eq("id_fnc", functie_uuid) \
        .execute().data
    if not pf:
        print(f"⚠️ Geen functie gevonden voor {voornaam} {naam}")
        return None
    return pf[0]["id"]


# === DETAIL-VERWERKING ===
def process_detail(schv_id: str):
    """Haalt detaildata op van één schriftelijke vraag."""
    url = f"{BASE_DETAIL_URL}{schv_id}"
    r = requests.get(url)
    if r.status_code != 200:
        print(f"⚠️ Detail niet gevonden: {schv_id}")
        return None
    try:
        root = ET.fromstring(r.content)

        onderwerp = root.findtext("onderwerp", "").strip()
        vs_node = root.find("vraagsteller")
        vs_voornaam = vs_node.findtext("voornaam", "").strip() if vs_node is not None else ""
        vs_naam = vs_node.findtext("naam", "").strip() if vs_node is not None else ""
        min_node = root.find("minister")
        min_voornaam = min_node.findtext("voornaam", "").strip() if min_node is not None else ""
        min_naam = min_node.findtext("naam", "").strip() if min_node is not None else ""

        # === procedureverloop uitlezen ===
        datum_ingediend = None
        datum_beantwoord = None
        for pv in root.findall(".//procedureverloop"):
            status = pv.findtext("status", "")
            datum = pv.findtext("datum", "")
            if "Vraag gesteld aan de minister" in status:
                datum_ingediend = datum.split("T")[0]
            elif "Tijdig beantwoord" in status:
                datum_beantwoord = datum.split("T")[0]

        # === PDF ophalen ===
        pdf_url = root.findtext(".//bestand-ordered/URL")
        tekst = ""
        if pdf_url:
            try:
                pdf_resp = requests.get(pdf_url)
                if pdf_resp.status_code == 200:
                    tekst = extract_text_from_pdf(pdf_resp.content)
                else:
                    print(f"⚠️ Geen PDF voor {schv_id}")
            except Exception as e:
                print(f"⚠️ Fout bij PDF download {schv_id}: {e}")

        return {
            "id": str(uuid.uuid5(uuid.NAMESPACE_DNS, f"schv_{schv_id}")),
            "ingediend": datum_ingediend or "1900-01-01",
            "onderwerp": onderwerp,
            "tekst": tekst,
            "id_prsfnc_vs": get_persoonfunctie_id(vs_voornaam, vs_naam, FUNCTIE_VV),
            "id_prsfnc_min": get_persoonfunctie_id(min_voornaam, min_naam, FUNCTIE_MIN),
            "beantwoord": datum_beantwoord,
        }
    except Exception as e:
        print(f"❌ Fout bij verwerken detail {schv_id}: {e}")
        return None


# === MAIN ===
print("🔄 Recente schriftelijke vragen ophalen (eerste 50)...")
all_records = []
count = 0

for page in [1, 2]:
    url = BASE_API_URL.format(page=page)
    print(f"\n📥 Ophalen van {url}")
    resp = requests.get(url)
    if resp.status_code != 200:
        print(f"❌ Fout bij pagina {page}: {resp.status_code}")
        break

    try:
        data = resp.json()
    except Exception as e:
        print(f"❌ JSON parse fout: {e}")
        break

    results = data.get("result", [])
    print(f"📋 {len(results)} resultaten ontvangen.")
    for item in results:
        id_text = item.get("id", "")
        match = re.search(r"/(\d+)/pfls", id_text)
        if not match:
            continue
        schv_id = match.group(1)
        rec = process_detail(schv_id)
        if rec:
            all_records.append(rec)
            count += 1
            print(f"✅ [{count}] {rec['onderwerp'][:80]}")

        time.sleep(0.4)

print(f"\n⬆️ Uploaden van {len(all_records)} records naar Supabase...")
supabase.table("schriftelijke_vragen").upsert(all_records).execute()

print("✅ Klaar! Eerste 50 schriftelijke vragen succesvol gekoppeld en ingevoerd.")
