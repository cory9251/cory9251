"""
Iter56 helper: create CRMTEST-drag leads via API and advance one to 'completed'.
Prints their lead IDs so the Playwright script can pick them up.
"""
import os
import time
import uuid
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://work-connect-147.preview.emergentagent.com").rstrip("/")


def _login(email, password):
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/login", json={"email": email, "password": password}, timeout=30)
    assert r.status_code == 200, f"login failed for {email}: {r.status_code} {r.text[:200]}"
    return s


def create_and_advance_drag_leads():
    va = _login("va.demo@hcobcleaners.com", "VaDemo2026!")
    admin = _login("admin@hcobcleaners.com", "HcobAdmin2026!")

    created = {}
    # Lead 1: stays in new_lead (for the two "new_lead" drag tests)
    for tag in ("newlead", "completed"):
        suffix = uuid.uuid4().hex[:6]
        payload = {
            "prospect_name": f"CRMTEST-drag-{tag}-{suffix}",
            "prospect_phone": f"+15005{int(time.time()) % 100000}{suffix[:2]}",
            "service_type": "web_development",
            "property_size": "2br",
            "source": "other",
            "notes": "iter56 drag test",
        }
        r = va.post(f"{BASE_URL}/api/va/leads", json=payload, timeout=30)
        assert r.status_code in (200, 201), f"va lead create failed: {r.status_code} {r.text[:300]}"
        lead = r.json()
        lead_id = lead.get("lead_id") or lead.get("id")
        created[tag] = lead_id
        print(f"created {tag}: {lead_id}")

    # Advance the 'completed' one through contacted → quoted → booked → completed
    for stage in ("contacted", "quoted", "booked", "completed"):
        r = admin.put(
            f"{BASE_URL}/api/pm/leads/{created['completed']}/stage",
            json={"stage": stage},
            timeout=30,
        )
        assert r.status_code == 200, f"advance to {stage} failed: {r.status_code} {r.text[:300]}"
        print(f"advanced {created['completed']} → {stage}")

    print(f"NEWLEAD_ID={created['newlead']}")
    print(f"COMPLETED_ID={created['completed']}")
    return created


def cleanup_drag_leads(lead_ids):
    admin = _login("admin@hcobcleaners.com", "HcobAdmin2026!")
    for lid in lead_ids:
        try:
            r = admin.delete(f"{BASE_URL}/api/pm/leads/{lid}", json={"reason": "iter56 cleanup"}, timeout=30)
            print(f"cleanup {lid}: {r.status_code}")
        except Exception as e:
            print(f"cleanup {lid} error: {e}")


if __name__ == "__main__":
    ids = create_and_advance_drag_leads()
    # Write to a temp file so the playwright step can read them without re-running
    with open("/tmp/iter56_drag_ids.txt", "w") as f:
        f.write(f"{ids['newlead']}\n{ids['completed']}\n")
    print("Wrote /tmp/iter56_drag_ids.txt")
