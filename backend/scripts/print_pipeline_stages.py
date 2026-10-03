import requests

url = "http://localhost:8000/api/v1/projects/92534d7c-3d0f-4cbe-96af-2449f320b470/pipeline/status"
resp = requests.get(url).json()

print(f"Total stages returned: {len(resp['stages'])}")
for s in resp['stages']:
    print(f"Stage {s['stage_number']:02d}: {s['name']} -> {s['status']}")
