import requests
import json

BASE_URL = "http://localhost:8000/api/v1/assistant/query"
PROJECT_ID = "92534d7c-3d0f-4cbe-96af-2449f320b470"

QUERIES = [
    "How many authoritative unified records were created?",
    "Explain why Parcel #104 was quarantined",
    "Which parcels have geometry conflicts?",
    "Show the provenance chain for ULR-PUN-HAV-0012"
]

print("=== TESTING AI COPILOT 4 REQUIRED QUERIES ===")
for q in QUERIES:
    payload = {
        "query": q,
        "project_id": PROJECT_ID
    }
    r = requests.post(BASE_URL, json=payload)
    print(f"\n--- QUERY: '{q}' ---")
    print(f"Status Code: {r.status_code}")
    if r.status_code == 200:
        data = r.json()
        print(f"Intent: {data.get('intent')}")
        print(f"Latency: {data.get('latency_ms')} ms")
        print(f"Grounded Score: {data.get('grounded_score')}")
        print(f"Evidence Sources Count: {len(data.get('evidence_sources', []))}")
        for i, ev in enumerate(data.get('evidence_sources', [])[:2]):
            print(f"  Source {i+1}: {ev.get('title')} ({ev.get('source_type')})")
        print(f"Response Preview: {data.get('response', '')[:250]}...")
    else:
        print(f"Error: {r.text}")
