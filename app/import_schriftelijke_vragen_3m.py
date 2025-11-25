import os
import re
import uuid
import time
import requests
import xml.etree.ElementTree as ET
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
def get_persoonfunctie_id(voornaam: str, naam: str, functie_uuid: str):
    if not voornaam or not naam:
        return None
    res = supabase.table("persoon") \
        .select("id, naam, voornaam") \
        .ilike("naam", f"%{naam}%") \
        .ilike("voornaam", f"%{voornaam}%") \
        .execute().data
    if not res:
        return None
    id_prs = res[0]["id"]
    pf = supabase.table("persoonfunctie") \
        .select("id") \
        .eq("id_prs", id_prs) \
        .eq("id_fnc", functie_uuid) \
        .execute().data
    if not pf:
        return None
    return pf[0]["id"]


def process_detail(schv_id: str):
    url = f"{BASE_DETAIL_URL}{schv_id}"
    try:
        r = requests.get(url, timeout=10)
        r.raise_for_status()
    except requests.RequestException:
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

        datum_ingediend = None
        datum_beantwoord = None
        for pv in root.findall(".//procedureverloop"):
            status = pv.findtext("status", "")
            datum = pv.findtext("datum", "")
            if any(x in status for x in ["Vraag gesteld", "Vraag ingediend"]):
                datum_ingediend = datum.split("T")[0]
            elif any(x in status for x in [
                "Beantwoord",
                "Antwoord",
                "Laattijdig beantwoord",
                "Tijdig beantwoord",
                "Antwoord ontvangen",
                "Antwoord gepubliceerd"
            ]):
                datum_beantwoord = datum.split("T")[0]

        pdf_url = root.findtext(".//bestand-ordered/URL") or ""

        return {
            "id": str(uuid.uuid5(uuid.NAMESPACE_DNS, f"schv_{schv_id}")),
            "ingediend": datum_ingediend or "1900-01-01",
            "onderwerp": onderwerp,
            "tekst": pdf_url.strip(),
            "id_prsfnc_vs": get_persoonfunctie_id(vs_voornaam, vs_naam, FUNCTIE_VV),
            "id_prsfnc_min": get_persoonfunctie_id(min_voornaam, min_naam, FUNCTIE_MIN),
            "beantwoord": datum_beantwoord,
        }
    except Exception as e:
        print(f"❌ Fout bij verwerken detail {schv_id}: {e}")
        return None


# === MAIN ===
print("🔄 Schriftelijke vragen 3001–4000 ophalen...")
all_records = []
count = 0

for page in range(121, 161):  # Pagina’s 121–160 ≈ 1000 vragen (3001–4000)
    url = BASE_API_URL.format(page=page)
    resp = requests.get(url)
    if resp.status_code != 200:
        print(f"❌ Fout bij pagina {page}: {resp.status_code}")
        break

    data = resp.json()
    results = data.get("result", [])
    if not results:
        break

    print(f"📋 Pagina {page}: {len(results)} resultaten.")
    for item in results:
        id_text = item.get("id", "")
        match = re.search(r"/(\d+)/pfls", id_text)
        if not match:
            continue
        schv_id = match.group(1)

        rec = process_detail(schv_id)
        if rec:
            if not any(r["id"] == rec["id"] for r in all_records):  # Geen dubbels
                all_records.append(rec)
                count += 1
                print(f"✅ [{count}] {rec['onderwerp'][:80]}")

        time.sleep(0.2)

# Upsert in batches van 100
batch_size = 100
for i in range(0, len(all_records), batch_size):
    batch = all_records[i:i + batch_size]
    supabase.table("schriftelijke_vragen").upsert(batch).execute()
    print(f"Batch {i//batch_size + 1} ({len(batch)} records) geüpload.")

print(f"Klaar! {len(all_records)} schriftelijke vragen (3001–4000) ingevoerd.")
