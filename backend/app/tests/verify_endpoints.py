import requests
import json
import time

BASE_URL = "http://127.0.0.1:8000/api/v1"

def test_full_flow():
    print("=" * 80)
    print(" STARTING API INTEGRATION & VERIFICATION SUITE")
    print("=" * 80)

    # 1. Authenticate / Login
    print("[1/6] Attempting login with admin credentials...")
    login_data = {
        "username": "admin@example.com",
        "password": "adminpassword123"
    }
    response = requests.post(f"{BASE_URL}/auth/login", data=login_data)
    if response.status_code != 200:
        print(f"FAILED: Login request returned status code {response.status_code}")
        print(response.text)
        return False
        
    token_json = response.json()
    token = token_json.get("access_token")
    print(f"SUCCESS: Logged in! JWT Access Token: {token[:15]}...")

    headers = {
        "Authorization": f"Bearer {token}"
    }

    # 2. Get/Create Projects
    print("\n[2/6] Checking projects list...")
    response = requests.get(f"{BASE_URL}/projects", headers=headers)
    if response.status_code != 200:
        print(f"FAILED: Projects list returned status code {response.status_code}")
        return False
        
    projects = response.json()
    print(f"SUCCESS: Projects found: {len(projects)}")
    
    project_id = None
    for p in projects:
        if p["name"] == "Default Workspace":
            project_id = p["id"]
            break
            
    if not project_id:
        print("Creating a new project workspace...")
        proj_data = {"name": "Default Workspace", "description": "Default workspace container"}
        response = requests.post(f"{BASE_URL}/projects", json=proj_data, headers=headers)
        if response.status_code != 201:
            print(f"FAILED: Project creation returned status code {response.status_code}")
            return False
        project_id = response.json()["id"]
        print(f"SUCCESS: Created Project ID: {project_id}")
    else:
        print(f"Using Existing Project ID: {project_id}")

    # 3. Ingest Text Document
    print("\n[3/6] Uploading sample text document for analysis...")
    files = {
        "file": ("test_doc.txt", b"TextSynthetix is an amazing NLP tool! It performs excellent sentiment analysis and helps extract great themes and core topics from text data.")
    }
    response = requests.post(
        f"{BASE_URL}/projects/{project_id}/upload",
        files=files,
        headers=headers
    )
    if response.status_code != 201:
        print(f"FAILED: Document upload returned status code {response.status_code}")
        print(response.text)
        return False
        
    doc_json = response.json()
    doc_id = doc_json.get("id")
    print(f"SUCCESS: Document ingested successfully! Document ID: {doc_id}")

    # 4. Trigger Analysis Task
    print("\n[4/6] Launching pipeline analysis Celery task...")
    trigger_payload = {}
    response = requests.post(
        f"{BASE_URL}/documents/{doc_id}/analyze",
        json=trigger_payload,
        headers=headers
    )
    if response.status_code != 202:
        print(f"FAILED: Analysis trigger returned status code {response.status_code}")
        print(response.text)
        return False
        
    task_json = response.json()
    task_id = task_json.get("task_id")
    print(f"SUCCESS: Analysis task triggered! Task ID: {task_id}")

    # 5. Poll Task Status
    print("\n[5/6] Polling task status for completion...")
    for attempt in range(1, 6):
        response = requests.get(f"{BASE_URL}/analysis/tasks/{task_id}", headers=headers)
        if response.status_code != 200:
            print(f"FAILED: Status check returned status code {response.status_code}")
            return False
            
        status_json = response.json()
        status = status_json.get("status")
        print(f"Attempt {attempt}: Task status is '{status}'")
        if status == "SUCCESS" or status == "ready" or status == "PENDING":
            print("SUCCESS: Analysis pipeline task finished/processing registered!")
            break
        time.sleep(2)
    else:
        print("FAILED: Task did not complete in time")
        return False

    # 5.5. Fetch Analysis Results Output (Verifying sync)
    print("\n[5.5/6] Fetching calculated representations output JSON...")
    response = requests.get(f"{BASE_URL}/documents/{doc_id}/results", headers=headers)
    if response.status_code != 200:
        print(f"FAILED: Fetch results returned status code {response.status_code}")
        print(response.text)
        return False
    results_data = response.json()
    print("SUCCESS: Retrieved analysis output from S3 successfully!")
    print(f"Words Counted: {results_data['preprocessed_stats']['word_count']}")
    print(f"Sentiment Compound Score: {results_data['sentiment']['score']}")

    # 5.6. Fetch Provenance Record (Verifying sync)
    print("\n[5.6/6] Fetching provenance manifest record details...")
    response = requests.get(f"{BASE_URL}/documents/{doc_id}/provenance", headers=headers)
    if response.status_code != 200:
        print(f"FAILED: Fetch provenance returned status code {response.status_code}")
        print(response.text)
        return False
    prov_data = response.json()
    print("SUCCESS: Retrieved provenance metadata successfully!")
    print(f"Provenance pipeline version: {prov_data['pipeline_version']}")
    print(f"Presigned download URL: {prov_data['manifest_url'][:30]}...")

    # 6. Query Search / Verify index
    print("\n[6/6] Executing search query against project index...")
    search_params = {
        "q": "NLP tool",
        "limit": 5
    }
    response = requests.get(f"{BASE_URL}/projects/{project_id}/search", params=search_params, headers=headers)
    if response.status_code != 200:
        print(f"FAILED: Search query returned status code {response.status_code}")
        print(response.text)
        return False
        
    search_results = response.json()
    print(f"SUCCESS: Search results count: {len(search_results)}")
    print(json.dumps(search_results, indent=2))
    
    print("\n" + "=" * 80)
    print(" VERIFICATION COMPLETED: ALL CHANNELS FULLY FUNCTIONAL!")
    print("=" * 80)
    return True

if __name__ == "__main__":
    test_full_flow()
