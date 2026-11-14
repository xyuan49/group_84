def test_health(client):
    assert client.get("/api/health").json() == {"status": "ok"}


def test_root_redirects_to_docs(client):
    r = client.get("/", follow_redirects=False)
    assert r.status_code == 307
    assert r.headers["location"] == "/docs"


def test_cors_allows_vite_dev_server(client):
    r = client.options("/api/health", headers={
        "Origin": "http://localhost:5173", "Access-Control-Request-Method": "GET"})
    assert r.headers["access-control-allow-origin"] == "http://localhost:5173"


def test_list_patients_sorted_by_last_name(client, patients):
    body = client.get("/api/patients").json()
    assert [p["id"] for p in body] == ["p-2", "p-1"]
    assert body[1] == {"id": "p-1", "first_name": "Maria", "last_name": "Lopez",
                       "gender": "female", "birth_date": "1968-03-02"}


def test_list_patients_paging(client, patients):
    assert [p["id"] for p in client.get("/api/patients", params={"limit": 1, "offset": 1}).json()] == ["p-1"]
    assert client.get("/api/patients", params={"limit": 0}).status_code == 422


def test_read_patient_and_404(client, patients):
    assert client.get("/api/patients/p-1").json()["last_name"] == "Lopez"
    assert client.get("/api/patients/missing").json() == {"detail": "Patient not found"}
    assert client.get("/api/patients/missing").status_code == 404
