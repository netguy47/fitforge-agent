import json
import httpx

def main():
    print("--- 1. Health check ---")
    r = httpx.get("http://127.0.0.1:8000/health")
    print("GET /health ->", r.status_code, r.json())
    assert r.status_code == 200

    print("\n--- 2. POST /api/workflows ---")
    with open("samples/restaurant_district_manager.json", "r", encoding="utf-8") as f:
        payload = json.load(f)
    r = httpx.post("http://127.0.0.1:8000/api/workflows", json=payload)
    print("POST /api/workflows ->", r.status_code)
    assert r.status_code == 200
    data = r.json()
    wf_id = data["workflow_id"]
    print("Created Workflow ID:", wf_id)
    print("State:", data["state"])
    print("Fit Score:", data["fit_assessment"]["fit_score"])
    print("Recommendation:", data["fit_assessment"]["recommendation"])

    print("\n--- 3. GET /api/workflows/{workflow_id} ---")
    r = httpx.get(f"http://127.0.0.1:8000/api/workflows/{wf_id}")
    print(f"GET /api/workflows/{wf_id} ->", r.status_code)
    assert r.status_code == 200
    wf_data = r.json()

    print("\n--- 4. Recorded State Transitions Audit Trail ---")
    for event in wf_data["audit_trail"]:
        from_st = event.get("from_state") or "None"
        to_st = event.get("to_state")
        agent = event.get("agent_name")
        msg = event.get("message")
        ts = event.get("timestamp")
        print(f"[{ts}] {from_st} -> {to_st} | Agent: {agent} | {msg}")

    expected = [
        "created",
        "normalizing",
        "mapping_evidence",
        "scoring_fit",
        "planning_actions",
        "validating",
        "completed",
    ]
    observed = [e["to_state"] for e in wf_data["audit_trail"]]
    assert observed == expected, f"Expected {expected}, got {observed}"
    print("\nAll state sequence assertions passed perfectly!")

if __name__ == "__main__":
    main()
