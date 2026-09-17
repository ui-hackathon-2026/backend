from app.core.security import hash_password, verify_password


def test_register_ok(client):
    r = client.post(
        "/api/v1/auth/register",
        json={"username": "formulator1", "password": "secret123"},
    )
    assert r.status_code == 201
    body = r.json()
    assert body["username"] == "formulator1"
    assert isinstance(body["id"], int)
    assert "created_at" in body
    assert "password_hash" not in body
    assert "password" not in body


def test_register_duplicate_username(client):
    payload = {"username": "labchem", "password": "secret123"}
    assert client.post("/api/v1/auth/register", json=payload).status_code == 201
    r = client.post("/api/v1/auth/register", json=payload)
    assert r.status_code == 409
    assert r.json() == {"detail": "username already taken"}


def test_register_short_password_rejected(client):
    r = client.post(
        "/api/v1/auth/register",
        json={"username": "labchem", "password": "12345"},
    )
    assert r.status_code == 422


def test_register_short_username_rejected(client):
    r = client.post(
        "/api/v1/auth/register",
        json={"username": "ab", "password": "secret123"},
    )
    assert r.status_code == 422


def test_login_ok_returns_bearer_token(client):
    client.post(
        "/api/v1/auth/register",
        json={"username": "formulator2", "password": "secret123"},
    )
    r = client.post(
        "/api/v1/auth/login",
        json={"username": "formulator2", "password": "secret123"},
    )
    assert r.status_code == 200
    assert r.json()["token_type"] == "bearer"
    assert len(r.json()["access_token"]) > 20


def test_login_wrong_password(client):
    client.post(
        "/api/v1/auth/register",
        json={"username": "formulator3", "password": "secret123"},
    )
    r = client.post(
        "/api/v1/auth/login",
        json={"username": "formulator3", "password": "wrongpass"},
    )
    assert r.status_code == 401
    assert r.json() == {"detail": "invalid username or password"}


def test_login_unknown_user(client):
    r = client.post(
        "/api/v1/auth/login",
        json={"username": "nobody", "password": "secret123"},
    )
    assert r.status_code == 401


def test_me_ok(client):
    client.post(
        "/api/v1/auth/register",
        json={"username": "formulator4", "password": "secret123"},
    )
    token = client.post(
        "/api/v1/auth/login",
        json={"username": "formulator4", "password": "secret123"},
    ).json()["access_token"]
    r = client.get(
        "/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"}
    )
    assert r.status_code == 200
    assert r.json()["username"] == "formulator4"


def test_me_without_token_rejected(client):
    assert client.get("/api/v1/auth/me").status_code == 401


def test_me_with_bad_token_rejected(client):
    r = client.get(
        "/api/v1/auth/me", headers={"Authorization": "Bearer not-a-token"}
    )
    assert r.status_code == 401


def test_password_is_hashed_not_plaintext():
    hashed = hash_password("secret123")
    assert hashed != "secret123"
    assert verify_password("secret123", hashed)
    assert not verify_password("wrongpass", hashed)
