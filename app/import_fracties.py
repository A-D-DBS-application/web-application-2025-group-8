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
print("🔄 Fracties aan het ophalen uit de API...")
response = requests.get(URL)

if response.status_code != 200:
    print(f"❌ Fout bij ophalen data: {response.status_code}")
    exit()

root = ET.fromstring(response.content)

# --- Fractienamen verzamelen (uit subelementen) ---
fracties_set = set()

for vv in root.findall(".//volksvertegenwoordiger"):
    fractie_elem = vv.find("fractie/naam")
    if fractie_elem is not None and fractie_elem.text:
        fracties_set.add(fractie_elem.text.strip())

print(f"📋 {len(fracties_set)} unieke fracties gevonden:")
for f in sorted(fracties_set):
    print(f"   • {f}")

# --- Data voorbereiden voor Supabase ---
fracties_data = []
for naam in sorted(fracties_set):
    id_uuid = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"fractie_{naam.lower()}"))
    fracties_data.append({
        "id": id_uuid,
        "naam": naam,
        "logo_url": None  # kunnen we later automatisch toevoegen
    })

if not fracties_data:
    print("⚠️ Geen fracties gevonden — controleer XML-structuur of tags.")
    exit()

# --- Data uploaden ---
print("⏳ Fracties aan het invoeren in Supabase...")
supabase.table("fractie").upsert(fracties_data).execute()

print("✅ Fracties succesvol ingevoerd!")
