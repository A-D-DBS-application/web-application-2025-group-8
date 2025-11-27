import os
import re
import time
import requests
import xml.etree.ElementTree as ET
from dotenv import load_dotenv
from supabase import create_client
from tqdm import tqdm
import uuid

# === CONFIG ===
load_dotenv()
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

BATCH_SIZE = 500   # aantal vragen per batch
MAX_PAGES = 200    # genoeg voor ~5000 schriftelijke vragen (200 * 25)

# === HELPERS ===
def get_thema_id(thema_naam):
    """Zoek thema-id in Supabase op basis van naam (case-insensitive)."""
    res = supabase.table("thema").select("id").ilike("naam", f"%{thema_naam}%").execute().data
    if res:
        return res[0]["id"]
    return None


def fetch_themas_and_pdfs(schv_id):
    """Haalt themas en PDF-links op voor één schriftelijke vraag."""
    xml_url = f"https://ws.vlpar.be/e/opendata/schv/{schv_id}"
    r = requests.get(xml_url, timeout=10)
    if r.status_code != 200:
        return [], []
    root = ET.fromstring(r.content)
    themas = [t.text.strip() for t in root.findall(".//themas/thema") if t.text]
    pdfs = [u.text.strip() for u in root.findall(".//bestand-ordered/URL") if u.text]
    return themas, pdfs


# === STAP 1: XML-index bouwen ===
print("📥 XML-index opbouwen van schriftelijke vragen... (dit duurt even)")
xml_index = {}

for page in tqdm(range(1, MAX_PAGES + 1), desc="XML-index opbouwen"):
    url = (
        "https://ws.vlpar.be/api/search/query/"
        "+inmeta:legislatuur=2024-2029"
        "&requiredfields=paginatype:Parlementair%20document."
        "aggregaat:Vraag%20of%20interpellatie."
        "aggregaattype:Schriftelijke%20vraag"
        f"?collection=vp_collection&sort=date&order=desc&max=25&page={page}"
    )
    r = requests.get(url)
    if r.status_code != 200:
        continue
    data = r.json()
    if not data.get("result"):
        break

    for item in data["result"]:
        match = re.search(r"/(\d+)/pfls", item.get("id", ""))
        if not match:
            continue
        schv_id = match.group(1)
        themas, pdfs = fetch_themas_and_pdfs(schv_id)
        for pdf in pdfs:
            if "id=" in pdf:
                pfile_id = pdf.split("id=")[1]
                xml_index[pfile_id] = {"schv_id": schv_id, "themas": themas}
        time.sleep(0.25)

print(f"✅ XML-index opgebouwd ({len(xml_index)} pdf-links gevonden)")


# === STAP 2: ALLE schriftelijke vragen ophalen ===
print("\n📊 Schriftelijke vragen ophalen uit Supabase...")
alle_vragen = []
offset = 0
page_size = 1000  # Supabase geeft max 1000 per request

while True:
    batch = supabase.table("schriftelijke_vragen").select("id, tekst, onderwerp").range(offset, offset + page_size - 1).execute().data
    if not batch:
        break
    alle_vragen.extend(batch)
    offset += page_size
    print(f"   ➕ Batch geladen — totaal {len(alle_vragen)} vragen...")
    if len(batch) < page_size:
        break

aantal = len(alle_vragen)
print(f"✅ {aantal} schriftelijke vragen opgehaald.\n")


# === STAP 3: Thema’s koppelen in batches ===
for start in range(0, aantal, BATCH_SIZE):
    batch_vragen = alle_vragen[start:start + BATCH_SIZE]
    print(f"\n🔄 Verwerken batch {start//BATCH_SIZE + 1}/{(aantal-1)//BATCH_SIZE + 1} "
          f"({len(batch_vragen)} vragen) ...")

    koppelingen = []
    onbekende_themas = set()

    for v in tqdm(batch_vragen, desc="Verwerken", unit="vraag"):
        pdf_url = v.get("tekst", "")
        if "id=" not in pdf_url:
            continue
        pfile_id = pdf_url.split("id=")[1]
        if pfile_id not in xml_index:
            continue

        entry = xml_index[pfile_id]
        themas = entry["themas"]

        for t in themas:
            thema_id = get_thema_id(t)
            if thema_id:
                koppelingen.append({
                    "id": str(uuid.uuid4()),
                    "id_schv": v["id"],
                    "id_thm": thema_id
                })
            else:
                onbekende_themas.add(t)
        time.sleep(0.05)

    if koppelingen:
        supabase.table("thema_koppeling").upsert(koppelingen).execute()
        print(f"✅ {len(koppelingen)} koppelingen toegevoegd in deze batch.")
    else:
        print("⚠️ Geen koppelingen gevonden in deze batch.")

    if onbekende_themas:
        print(f"⚠️ Onbekende thema’s (batch): {onbekende_themas}")

print("\n🎉 Alle batches verwerkt — koppeling van thema’s volledig voltooid.")
