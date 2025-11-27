import requests
import re
import xml.etree.ElementTree as ET

url = "https://ws.vlpar.be/api/search/query/+inmeta:legislatuur=2024-2029&requiredfields=paginatype:Parlementair%20document.aggregaat:Vraag%20of%20interpellatie.aggregaattype:Schriftelijke%20vraag?collection=vp_collection&sort=date&order=desc&max=25&page=1"

r = requests.get(url)
print("Status:", r.status_code)

if r.status_code == 200:
    data = r.json()
    results = data.get("result", [])
    print(f"Gevonden resultaten: {len(results)}")

    if results:
        first = results[0]
        match = re.search(r"/(\d+)/pfls", first.get("id", ""))
        if match:
            schv_id = match.group(1)
            print("Schriftelijke vraag ID:", schv_id)

            xml_url = f"https://ws.vlpar.be/e/opendata/schv/{schv_id}"
            xml_resp = requests.get(xml_url)
            print("XML-status:", xml_resp.status_code)
            if xml_resp.status_code == 200:
                root = ET.fromstring(xml_resp.content)
                pdfs = [url.text for url in root.findall(".//bestand-ordered/URL")]
                print("PDF-links gevonden:", pdfs)
