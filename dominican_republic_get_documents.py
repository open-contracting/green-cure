import json
import os

import requests
from bs4 import BeautifulSoup

greep_procurement_list_url = (
    "https://wabi-us-east-a-primary-api.analysis.windows.net/public/reports/querydata?synchronous=true"
)

headers = {
    "X-PowerBI-ResourceKey": "6d07fc9a-46df-4b72-9509-ea5c80c85178",
}

documents_path = "data"

base_url = "https://comunidad.comprasdominicana.gob.do/"

with open("dominican_republic_post_json.json") as f:
    post_data = json.loads(f.read())

data = requests.post(greep_procurement_list_url, json=post_data, headers=headers)

data_entries = data.json()["results"][0]["result"]["data"]["dsr"]["DS"][0]["PH"][0]["DM0"]

os.makedirs(documents_path, exist_ok=True)

for entry in data_entries:
    if "C" in entry:
        for process_url in filter(lambda text: "https" in str(text), entry["C"]):
            request = requests.get(process_url, headers={"Accept-Language": "es-ES,es;q=0.9,en;q=0.8"})
            soup = BeautifulSoup(request.content, "html.parser")
            tender_title = soup.find(id="fdsRequestSummaryInfo_tblDetail_trRowName_tdCell2_spnRequestName").text
            process_id = soup.find(id="fdsRequestSummaryInfo_tblDetail_trRowRef_tdCell2_spnRequestReference").text
            print(f"Downloading files for {tender_title} from {process_url}")
            for row in soup.find(id="grdGridDocumentList_tbl").find_all("tr"):
                if row.find("th"):
                    continue
                document_name = row.find("td", id="grdGridDocumentListtd_thColumnDocumentName").text
                document_type = row.find("td", id="grdGridDocumentListtd_thColumnDocumentType").text
                document_url = (
                    row.find("td", id="grdGridDocumentListtd_thColumnDownloadDocument")
                    .find("a")["onclick"]
                    .replace("javascript:getAction('", "")
                    .replace("',true);", "")
                    .replace("' + '", "")
                )
                final_url = f"{base_url}/{document_url}"
                if document_type == "Especificaciones/Ficha Técnica":
                    pdf_document_final_url = (
                        BeautifulSoup(requests.get(final_url).content, "html.parser")
                        .find("script")
                        .text.replace("window.location.href = ", "")
                        .replace("'", "")
                    )
                    pdf_document = requests.get(f"{base_url}{pdf_document_final_url}")
                    final_document_name = os.path.join(
                        documents_path,
                        f"{process_id}-{tender_title[:100]}-{document_name}".replace(" ", "-")
                        .replace("/", "-")
                        .replace('"', ""),
                    )
                    with open(final_document_name, "wb") as f:
                        f.write(pdf_document.content)
