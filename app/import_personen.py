import os
import uuid
import requests
import xml.etree.ElementTree as ET
from supabase import create_client
from dotenv import load_dotenv

# --- .env laden ---
load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# --- XML Data ophalen ---
URL = "https://ws.vlpar.be/e/opendata/vv/huidige"

print("🔄 Volksvertegenwoordigers aan het ophalen...")
response = requests.get(URL)

if response.status_code != 200:
    print(f"❌ Fout bij ophalen data: {response.status_code}")
    exit()

root = ET.fromstring(response.content)

# === Namespace verwijderen ===
for elem in root.iter():
    if "}" in elem.tag:
        elem.tag = elem.tag.split("}", 1)[1]

# === Volksvertegenwoordigers parsen ===
volksvertegenwoordigers = root.findall(".//volksvertegenwoordiger")
print(f"📋 Aantal gevonden <volksvertegenwoordiger>: {len(volksvertegenwoordigers)}")

personen_dict = {}

for vv in volksvertegenwoordigers:
    id_vv = vv.find("id").text.strip() if vv.find("id") is not None else None
    voornaam = vv.find("voornaam").text.strip() if vv.find("voornaam") is not None else ""
    naam = vv.find("naam").text.strip() if vv.find("naam") is not None else ""
    kieskring = vv.find("kieskring").text.strip() if vv.find("kieskring") is not None else "Onbekend"

    # Geslacht ophalen
    geslacht_raw = vv.find("geslacht")
    if geslacht_raw is not None and geslacht_raw.text:
        g = geslacht_raw.text.strip().lower()
        geslacht = "M" if g.startswith("m") else "V" if g.startswith("v") else "X" if g.startswith("x") else None
    else:
        geslacht = None

    # UUID genereren op basis van unieke info
    uuid_input = id_vv if id_vv else f"{voornaam}_{naam}_{kieskring}"
    id_uuid = str(uuid.uuid5(uuid.NAMESPACE_DNS, uuid_input))

    persoon = {
        "id": id_uuid,
        "voornaam": voornaam,
        "naam": naam,
        "geboortedatum": None,
        "geslacht": geslacht,
        "roepnaam": voornaam,
        "kieskring": kieskring
    }

    # toevoegen als nog niet bestaat
    personen_dict[id_uuid] = persoon

personen_data = list(personen_dict.values())

print(f"📦 {len(personen_data)} unieke volksvertegenwoordigers gevonden.")
print("⏳ Data wordt ingevoerd in Supabase...")

# --- Upload in batches ---
batch_size = 20
for i in range(0, len(personen_data), batch_size):
    batch = personen_data[i:i + batch_size]
    supabase.table("persoon").upsert(batch).execute()

print("✅ Import voltooid!")
