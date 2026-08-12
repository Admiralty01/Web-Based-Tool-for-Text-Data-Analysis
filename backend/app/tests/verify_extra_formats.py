import requests
import json
import io
import zipfile
import xml.etree.ElementTree as ET

BASE_URL = "http://127.0.0.1:8000/api/v1"

def create_mock_docx() -> bytes:
    """Create a valid docx XML ZIP stream in-memory."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        # Minimal word document XML
        xml_content = (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
            '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">\n'
            '  <w:body>\n'
            '    <w:p>\n'
            '      <w:r>\n'
            '        <w:t>This is an automated DOCX parsing test. TextSynthetix extracts GPE values like Paris and London.</w:t>\n'
            '      </w:r>\n'
            '    </w:p>\n'
            '  </w:body>\n'
            '</w:document>'
        )
        z.writestr("word/document.xml", xml_content.encode("utf-8"))
    return buf.getvalue()

def run_extra_formats_test():
    print("=" * 80)
    print(" STARTING MULTI-FORMAT PARSER VERIFICATION")
    print("=" * 80)

    # 1. Log in
    print("[1/4] Authenticating with admin credentials...")
    login_data = {"username": "admin@example.com", "password": "adminpassword123"}
    res = requests.post(f"{BASE_URL}/auth/login", data=login_data)
    if res.status_code != 200:
        print("FAILED: Authentication failed.")
        return False
    token = res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    print("SUCCESS: Logged in!")

    # Get project ID 1
    project_id = 1

    # 2. Test CSV Ingestion
    print("\n[2/4] Uploading CSV file (with header and text row)...")
    csv_content = b"id,review,label\n101,TextSynthetix is an excellent organization located in London. We recommend it,positive"
    files = {"file": ("test_corpus.csv", csv_content)}
    res = requests.post(f"{BASE_URL}/projects/{project_id}/upload", files=files, headers=headers)
    if res.status_code != 201:
        print(f"FAILED: CSV upload failed with status code {res.status_code}: {res.text}")
        return False
    print("SUCCESS: CSV parsed and ingested! Document ID:", res.json()["id"])

    # 3. Test DOCX Ingestion
    print("\n[3/4] Uploading DOCX file (built in-memory)...")
    docx_content = create_mock_docx()
    files = {"file": ("test_corpus.docx", docx_content)}
    res = requests.post(f"{BASE_URL}/projects/{project_id}/upload", files=files, headers=headers)
    if res.status_code != 201:
        print(f"FAILED: DOCX upload failed with status code {res.status_code}: {res.text}")
        return False
    print("SUCCESS: DOCX parsed and ingested! Document ID:", res.json()["id"])

    # 4. Test PDF Ingestion
    print("\n[4/4] Uploading PDF file...")
    pdf_content = b"%PDF-1.4 ... (This GPE is Berlin and organization is Google) ..."
    files = {"file": ("test_corpus.pdf", pdf_content)}
    res = requests.post(f"{BASE_URL}/projects/{project_id}/upload", files=files, headers=headers)
    if res.status_code != 201:
        print(f"FAILED: PDF upload failed with status code {res.status_code}: {res.text}")
        return False
    print("SUCCESS: PDF parsed and ingested! Document ID:", res.json()["id"])

    print("\n" + "=" * 80)
    print(" ALL EXTRA FORMATS INGESTED & NORMALIZED SUCCESSFULLY!")
    print("=" * 80)
    return True

if __name__ == "__main__":
    run_extra_formats_test()
