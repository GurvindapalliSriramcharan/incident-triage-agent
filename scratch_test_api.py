import urllib.request
import urllib.error
import json
import sys

def test_url(url, data=None):
    try:
        payload = json.dumps(data).encode('utf-8') if data else None
        headers = {'Content-Type': 'application/json'} if data else {}
        req = urllib.request.Request(url, data=payload, headers=headers)
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = resp.read().decode('utf-8')
            print(f"[SUCCESS] {url} -> {resp.status}")
            print(body[:500])
            return json.loads(body)
    except urllib.error.HTTPError as e:
        err_body = e.read().decode('utf-8')
        print(f"[HTTP ERROR] {url} -> {e.code}")
        print(err_body)
        return None
    except Exception as e:
        print(f"[EXCEPTION] {url} -> {e}")
        return None

print("--- Testing /health ---")
test_url("http://localhost:8000/health")

print("\n--- Testing POST /api/v1/incidents ---")
res = test_url("http://localhost:8000/api/v1/incidents", {
    "title": "Auth latency spike test",
    "description": "Users are encountering 504 timeouts on auth service.",
    "service": "auth",
    "source": "manual"
})

if res and "incident_id" in res:
    inc_id = res["incident_id"]
    print(f"\n--- Testing GET /api/v1/incidents/{inc_id} ---")
    test_url(f"http://localhost:8000/api/v1/incidents/{inc_id}")

    print(f"\n--- Testing POST /api/v1/incidents/{inc_id}/approve ---")
    test_url(f"http://localhost:8000/api/v1/incidents/{inc_id}/approve", {
        "approved": True,
        "reason": "Verified safe to execute"
    })
