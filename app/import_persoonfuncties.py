import os
import uuid
import requests
import xml.etree.ElementTree as ET
from supabase import create_client
from dotenv import load_dotenv

# --- Config ---
load_dotenv()
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# --- Functie UUID’s ---
FUNCTIE_VV = "11111111-aaaa-4bbb-cccc-000000000001"  # Volksvertegenwoordiger
FUNCTIE_MP = "11111111-aaaa-4bbb-cccc-000000000002"  # Minister-president
FUNCTIE_MIN = "11111111-aaaa-4bbb-cccc-000000000003"  # Minister
FUNCTIE_VZ = "11111111-aaaa-4bbb-cccc-000000000005"  # Voorzitter

# --- Fractie UUID’s (moeten exact overeenkomen met jouw Supabase) ---
FRACTIES = {
    "N-VA": "3aee93f8-3fd6-59e5-841f-26f1866f6691",
    "Vooruit": "3c8796ce-a68b-57b0-a4e6-43d32928ee08",
    "cd&v": "501b98dd-0314-5685-bd71-ad9be7381c99",
    "PVDA": "552e767d-404d-5701-98b4-6cd789504315",
    "Groen": "953e1d4b-b5dd-5d30-b6d9-ba93a5c5026a",
    "Open Vld": "a2bdf651-737f-5c91-b33f-2247867e61e8",
    "Vlaams Belang": "ad1c2939-40b6-507f-876a-a48a7eab3489",
    "Team Fouad Ahidar": "bcc9a6fb-3e67-54b5-a6eb-5c61dad83d52",
    "Onafhankelijke": "be0ac643-387b-53dd-9d19-971cd1017601",
}

# --- Handmatige IDs ministers ---
MINISTERS = {
    "annick": "0c7eac1a-905e-4820-81b5-7ae1d6f43a9b",
    "ben": "4c8b2a07-8c14-4f7a-8c89-0e99b8a1e9f3",
    "caroline": "f1b8c0b3-21f1-4e53-a3df-f6de782a8a9f",
    "cieltje": "59b27b7d-1c03-4cc5-b8b0-0b124e5e9085",
    "crevits": "2d6f5e7a-5417-4d85-b512-1772fce8e93a",
    "diependaele": "5f34a86a-3b3e-4b51-8b99-93b2b6e8759f",
    "jo": "a20fd3e3-5091-4d42-bb3a-3d1ab5a87c7a",
    "melissa": "2e73f01a-b6c3-4d78-b6f7-9275e928b3c1",
    "zuhal": "7de3a14c-3b0f-4825-8ab1-17d3479c05f8",
    "freya": "4881d2a6-c81e-545f-ae0a-751c13f021fe"
}

# --- XML ophalen ---
URL = "https://ws.vlpar.be/e/opendata/vv/huidige"
print("🔄 Volksvertegenwoordigers ophalen...")
response = requests.get(URL)
response.raise_for_status()
root = ET.fromstring(response.content)

# --- Personen ophalen uit database ---
personen = supabase.table("persoon").select("id, naam, voornaam").execute().data
persoonfuncties = []

# --- Voeg VV-functie toe voor alle personen ---
for p in personen:
    id_prs = p["id"]

    # Zoek fractie op basis van naam en voornaam
    fractieNaam = "Onafhankelijke"
    for vv in root.findall(".//volksvertegenwoordiger"):
        voornaam_xml = vv.find("voornaam").text.strip().lower()
        naam_xml = vv.find("naam").text.strip().lower()
        fractie_el = vv.find("fractie/naam")
        if (p["voornaam"].strip().lower() == voornaam_xml
            and p["naam"].strip().lower() == naam_xml):
            if fractie_el is not None and fractie_el.text:
                fractieNaam = fractie_el.text.strip()
            break

    # Case-insensitive fractie lookup
    id_frc = None
    for naam, uuid_frc in FRACTIES.items():
        if naam.lower() == fractieNaam.lower():
            id_frc = uuid_frc
            break
    if not id_frc:
        id_frc = FRACTIES["Onafhankelijke"]

    persoonfuncties.append({
        "id": str(uuid.uuid4()),
        "id_prs": id_prs,
        "id_fnc": FUNCTIE_VV,
        "id_frc": id_frc,
        "van": "2024-07-03",
        "tot": None
    })

# --- Functie om ministers toe te voegen ---
def add_minister(id_prs, fractieNaam):
    id_frc = None
    for naam, uuid_frc in FRACTIES.items():
        if naam.lower() == fractieNaam.lower():
            id_frc = uuid_frc
            break
    if not id_frc:
        id_frc = FRACTIES["Onafhankelijke"]

    persoonfuncties.append({
        "id": str(uuid.uuid4()),
        "id_prs": id_prs,
        "id_fnc": FUNCTIE_MIN,
        "id_frc": id_frc,
        "van": "2024-07-03",
        "tot": None
    })

# --- Voeg ministers + MP + voorzitter toe ---
add_minister(MINISTERS["annick"], "NV-A")
add_minister(MINISTERS["ben"], "N-VA")
add_minister(MINISTERS["caroline"], "Vooruit")
add_minister(MINISTERS["jo"], "cd&v")
add_minister(MINISTERS["melissa"], "Vooruit")
add_minister(MINISTERS["zuhal"], "N-VA")
add_minister(MINISTERS["crevits"], "cd&v")
add_minister(MINISTERS["cieltje"], "NV-A")

# MP (ook minister)
persoonfuncties.append({
    "id": str(uuid.uuid4()),
    "id_prs": MINISTERS["diependaele"],
    "id_fnc": FUNCTIE_MP,
    "id_frc": FRACTIES["N-VA"],
    "van": "2024-07-03",
    "tot": None
})
add_minister(MINISTERS["diependaele"], "N-VA")

# Voorzitter
persoonfuncties.append({
    "id": str(uuid.uuid4()),
    "id_prs": MINISTERS["freya"],
    "id_fnc": FUNCTIE_VZ,
    "id_frc": FRACTIES["Vooruit"],
    "van": "2024-07-03",
    "tot": None
})

# --- Upload naar Supabase ---
print(f"⏳ Uploaden van {len(persoonfuncties)} records...")
batch_size = 50
for i in range(0, len(persoonfuncties), batch_size):
    batch = persoonfuncties[i:i + batch_size]
    cleaned_batch = []
    for row in batch:
        for key in ["id_frc", "id_fnc", "id_prs"]:
            if row[key]:
                row[key] = row[key].strip()
        cleaned_batch.append(row)
    supabase.table("persoonfunctie").upsert(cleaned_batch).execute()

print("✅ Alle persoon-functie-relaties succesvol ingevoerd!")
