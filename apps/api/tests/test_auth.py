from tests.conftest import auth_headers, register


def test_register_returns_token(client):
    resp = client.post("/auth/register", json={"email": "a@farm.com", "password": "password123"})
    assert resp.status_code == 201
    assert resp.json()["token_type"] == "bearer"


def test_duplicate_email_rejected(client):
    client.post("/auth/register", json={"email": "a@farm.com", "password": "password123"})
    resp = client.post("/auth/register", json={"email": "a@farm.com", "password": "password123"})
    assert resp.status_code == 409


def test_short_password_rejected(client):
    resp = client.post("/auth/register", json={"email": "a@farm.com", "password": "short"})
    assert resp.status_code == 422


def test_login_wrong_password(client):
    client.post("/auth/register", json={"email": "a@farm.com", "password": "password123"})
    resp = client.post("/auth/login", json={"email": "a@farm.com", "password": "wrongpass123"})
    assert resp.status_code == 401


def test_me_requires_auth(client):
    assert client.get("/auth/me").status_code == 403  # no bearer header


def test_me_returns_current_user(client):
    token = register(client, "a@farm.com")
    resp = client.get("/auth/me", headers=auth_headers(token))
    assert resp.status_code == 200
    assert resp.json()["email"] == "a@farm.com"
