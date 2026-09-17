from app.core.security import hash_password, verify_password


def register(client, name="Andi Wibowo", email="andi@example.com"):
    return client.post(
        "/api/v1/auth/register",
        json={"name": name, "email": email, "password": "secret123"},
    )


def test_register_ok_shape(client):
    r = register(client)
    assert r.status_code == 201
    body = r.json()
    assert body["user"]["name"] == "Andi Wibowo"
    assert body["user"]["email"] == "andi@example.com"
    assert body["user"]["role"] == "formulator"
    assert body["user"]["avatarInitials"] == "AW"
    assert isinstance(body["user"]["id"], str)
    assert body["tokens"]["expiresIn"] == 900
    assert len(body["tokens"]["accessToken"]) > 20
    assert len(body["tokens"]["refreshToken"]) > 20
    assert "password_hash" not in r.text
    assert "password" not in body["user"]


def test_register_duplicate_email(client):
    assert register(client).status_code == 201
    r = register(client)
    assert r.status_code == 409
    assert r.json() == {"detail": "email already registered"}


def test_register_validation(client):
    short = client.post(
        "/api/v1/auth/register",
        json={"name": "A", "email": "a@b.co", "password": "12345"},
    )
    assert short.status_code == 422
    bad_email = client.post(
        "/api/v1/auth/register",
        json={"name": "Andi", "email": "not-an-email", "password": "secret123"},
    )
    assert bad_email.status_code == 422


def test_login_ok_and_me(client):
    register(client)
    r = client.post(
        "/api/v1/auth/login",
        json={"email": "andi@example.com", "password": "secret123"},
    )
    assert r.status_code == 200
    token = r.json()["tokens"]["accessToken"]
    me = client.get(
        "/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"}
    )
    assert me.status_code == 200
    assert me.json()["email"] == "andi@example.com"
    assert "createdAt" in me.json()


def test_login_wrong_credentials(client):
    register(client)
    r = client.post(
        "/api/v1/auth/login",
        json={"email": "andi@example.com", "password": "wrongpass"},
    )
    assert r.status_code == 401
    assert r.json() == {"detail": "invalid credentials"}
    unknown = client.post(
        "/api/v1/auth/login",
        json={"email": "nobody@example.com", "password": "secret123"},
    )
    assert unknown.status_code == 401


def test_refresh_rotates_and_old_rejected(client):
    tokens = register(client).json()["tokens"]
    r = client.post(
        "/api/v1/auth/refresh", json={"refreshToken": tokens["refreshToken"]}
    )
    assert r.status_code == 200
    fresh = r.json()
    assert fresh["refreshToken"] != tokens["refreshToken"]
    assert fresh["expiresIn"] == 900
    me = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {fresh['accessToken']}"},
    )
    assert me.status_code == 200
    replay = client.post(
        "/api/v1/auth/refresh", json={"refreshToken": tokens["refreshToken"]}
    )
    assert replay.status_code == 401


def test_logout_revokes(client):
    tokens = register(client).json()["tokens"]
    r = client.post(
        "/api/v1/auth/logout", json={"refreshToken": tokens["refreshToken"]}
    )
    assert r.status_code == 204
    again = client.post(
        "/api/v1/auth/refresh", json={"refreshToken": tokens["refreshToken"]}
    )
    assert again.status_code == 401


def test_refresh_bad_token(client):
    r = client.post(
        "/api/v1/auth/refresh", json={"refreshToken": "garbage-token-value"}
    )
    assert r.status_code == 401


def test_me_rejects_refresh_token(client):
    tokens = register(client).json()["tokens"]
    r = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {tokens['refreshToken']}"},
    )
    assert r.status_code == 401


def test_password_is_hashed_not_plaintext():
    hashed = hash_password("secret123")
    assert hashed != "secret123"
    assert verify_password("secret123", hashed)
    assert not verify_password("wrongpass", hashed)
