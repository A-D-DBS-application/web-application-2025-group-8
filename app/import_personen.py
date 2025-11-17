import os
import uuid
import time
import requests
import xml.etree.ElementTree as ET
from supabase import create_client
from dotenv import load_dotenv

# --- .env laden ---
load_dotenv()
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# --- Basislijst ophalen ---
LIST_URL = "https://ws.vlpar.be/e/opendata/vv/huidige"
DETAIL_URL_BASE = "https://ws.vlpar.be/e/opendata/vv/"

print("🔄 Volksvertegenwoordigers aan het ophalen...")
response = requests.get(LIST_URL)
if response.status_code != 200:
    print(f"❌ Fout bij ophalen lijst: {response.status_code}")
    exit()

root = ET.fromstring(response.content)
vv_elements = root.findall(".//volksvertegenwoordiger")
print(f"📋 {len(vv_elements)} volksvertegenwoordigers gevonden.")

personen_data = []

# --- Loop over elk element ---
for i, vv in enumerate(vv_elements, start=1):
    id_vv = vv.attrib.get("id")  # ✅ ID als attribuut!
    if not id_vv:
        continue

    voornaam = vv.find("voornaam").text.strip() if vv.find("voornaam") is not None else ""
    naam = vv.find("naam").text.strip() if vv.find("naam") is not None else ""
    kieskring = vv.find("kieskring").text.strip() if vv.find("kieskring") is not None else "Onbekend"

    # --- Tweede request: detailpagina ---
    detail_url = f"{DETAIL_URL_BASE}{id_vv}?lang=nl"
    detail_resp = requests.get(detail_url)

    geslacht = None
    geboortedatum = None
    if detail_resp.status_code == 200:
        try:
            detail_root = ET.fromstring(detail_resp.content)
            geslacht_el = detail_root.find("geslacht")
            geboortedatum_el = detail_root.find("geboortedatum")

            geslacht = geslacht_el.text.strip()[0].upper() if geslacht_el is not None and geslacht_el.text else None
            geboortedatum = (
                geboortedatum_el.text.strip().split("T")[0] if geboortedatum_el is not None and geboortedatum_el.text else None
            )
        except Exception as e:
            print(f"⚠️ Fout bij parsen detail van ID {id_vv}: {e}")

    # --- UUID consistent genereren ---
    id_uuid = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"vlaams_{id_vv}"))

    persoon = {
        "id": id_uuid,
        "voornaam": voornaam,
        "naam": naam,
        "geboortedatum": geboortedatum,
        "geslacht": geslacht if geslacht in ["M", "V", "X"] else None,
        "roepnaam": voornaam,
        "kieskring": kieskring,
    }
    personen_data.append(persoon)

    print(f"✅ {i}/{len(vv_elements)} - {voornaam} {naam} verwerkt.")
    time.sleep(0.3)  # kleine pauze om de API niet te overbelasten

print(f"\n📦 {len(personen_data)} volksvertegenwoordigers succesvol verzameld.")
print("⏳ Data wordt ingevoerd in Supabase...")

# --- Batch uploaden ---
batch_size = 20
for i in range(0, len(personen_data), batch_size):
    batch = personen_data[i : i + batch_size]
    supabase.table("persoon").upsert(batch).execute()

print("✅ Import volledig voltooid!")
