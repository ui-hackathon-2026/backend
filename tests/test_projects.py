def make_pdf(line: bytes) -> bytes:
    stream = b"BT /F1 12 Tf 10 10 Td (" + line + b") Tj ET"
    objs = [
        b"<</Type/Catalog/Pages 2 0 R>>",
        b"<</Type/Pages/Kids[3 0 R]/Count 1>>",
        b"<</Type/Page/Parent 2 0 R/MediaBox[0 0 200 200]/Contents 4 0 R/Resources<</Font<</F1 5 0 R>>>>>>",
        b"<</Length %d>>stream\n" % len(stream) + stream + b"\nendstream",
        b"<</Type/Font/Subtype/Type1/BaseFont/Helvetica>>",
    ]
    out = b"%PDF-1.4\n"
    offsets = []
    for i, body in enumerate(objs, start=1):
        offsets.append(len(out))
        out += b"%d 0 obj\n" % i + body + b"\nendobj\n"
    xref_at = len(out)
    out += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objs) + 1)
    for pos in offsets:
        out += b"%010d 00000 n \n" % pos
    out += (
        b"trailer\n<</Size %d/Root 1 0 R>>\nstartxref\n%d\n%%%%EOF\n"
        % (len(objs) + 1, xref_at)
    )
    return out


MINIMAL_PDF = make_pdf(b"Sunscreen SPF 30 brief")


def test_create_project_new(client):
    r = client.post(
        "/api/v1/projects",
        json={"name": "Sunscreen Serum", "brief_text": "SPF 50 watery light"},
    )
    assert r.status_code == 201
    body = r.json()
    assert body["project_id"].startswith("proj_")
    assert body["mode"] == "new"


def test_create_project_enhance_requires_ref(client):
    r = client.post(
        "/api/v1/projects",
        json={"name": "Enhance", "mode": "enhance", "instruction": "raise tkdn"},
    )
    assert r.status_code == 422


def test_create_project_enhance_ok_and_list(client):
    formula = client.post(
        "/api/v1/formulas",
        json={
            "name": "Base",
            "phases": {"phase_b": [{"inci": "Aqua", "weight_pct": 100.0}]},
        },
    ).json()
    r = client.post(
        "/api/v1/projects",
        json={
            "name": "Enhance",
            "mode": "enhance",
            "ref_formula_id": formula["formula_id"],
            "instruction": "raise tkdn",
        },
    )
    assert r.status_code == 201
    pid = r.json()["project_id"]
    assert client.get(f"/api/v1/projects/{pid}").status_code == 200
    listing = client.get("/api/v1/projects").json()
    assert any(p["project_id"] == pid for p in listing)
    assert client.get("/api/v1/projects/proj_nope").status_code == 404


def test_upload_brief_pdf(client):
    r = client.post(
        "/api/v1/uploads/brief",
        files={"file": ("brief.pdf", MINIMAL_PDF, "application/pdf")},
    )
    assert r.status_code == 201
    body = r.json()
    assert body["brief_id"].startswith("brief_")
    assert "Sunscreen SPF 30 brief" in body["preview"]
    assert body["char_count"] > 0


def test_upload_brief_rejects_non_pdf(client):
    r = client.post(
        "/api/v1/uploads/brief",
        files={"file": ("notes.txt", b"hello", "text/plain")},
    )
    assert r.status_code == 422
