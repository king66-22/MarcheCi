"""Tests du service utilisateurs : inscription, connexion, JWT, rôles, rate-limit."""

import pytest

from conftest import create_user_api

ADMIN = {"Authorization": "Bearer admin-jwt"}  # remplacé par vrai JWT en fixtures


# -------------------------------- health --------------------------------


def test_health_ok(client):
    assert client.get("/health").status_code == 200


# ------------------------------ inscription ------------------------------


def test_register_success(client):
    resp = create_user_api(client, "koffi@example.ci")
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["role"] == "CLIENT"
    assert "password_hash" not in body


def test_register_duplicate_email_409(client):
    create_user_api(client, "dup@example.ci")
    resp = create_user_api(client, "dup@example.ci")
    assert resp.status_code == 409


def test_register_weak_password_422(client):
    for weak in ("abc12", "sanschiffres", "12345678"):
        resp = create_user_api(client, f"w{weak[:4]}@example.ci", password=weak)
        assert resp.status_code == 422, weak


# -------------------------------- connexion -------------------------------


@pytest.fixture()
def logged_in(client):
    create_user_api(client, "mariam@example.ci")
    resp = client.post("/auth/login", json={"email": "mariam@example.ci", "password": "MotDePasse123"})
    assert resp.status_code == 200
    return resp.json()


def test_login_success_and_token_shape(client, logged_in):
    body = logged_in
    assert body["token_type"] == "bearer"
    assert body["expires_in"] > 0
    assert body["role"] == "CLIENT"


def test_login_bad_password_401_generic_message(client):
    create_user_api(client, "ali@example.ci")
    resp = client.post("/auth/login", json={"email": "ali@example.ci", "password": "MotDePasse1234"})
    assert resp.status_code == 401
    assert resp.json()["detail"] == "Email ou mot de passe incorrect"


def test_rate_limit_after_5_failures(client, rate_limited):
    create_user_api(client, "muso@example.ci")
    for _ in range(5):
        client.post("/auth/login", json={"email": "muso@example.ci", "password": "FauxPassword1"})
    resp = client.post("/auth/login", json={"email": "muso@example.ci", "password": "MotDePasse123"})

    assert resp.status_code == 429


def test_rate_limit_counter_resets_on_success(client, rate_limited):
    email = "reset@example.ci"
    create_user_api(client, email)
    client.post("/auth/login", json={"email": email, "password": "FauxPassword1"})  # 1 échec
    assert client.post("/auth/login", json={"email": email, "password": "MotDePasse123"}).status_code == 200
    # Le compteur est remis à zéro : une seule nouvelle erreur ne bloque pas
    client.post("/auth/login", json={"email": email, "password": "FauxPassword1"})
    assert client.post("/auth/login", json={"email": email, "password": "MotDePasse123"}).status_code == 200


# --------------------------------- JWT -----------------------------------


def test_me_with_token(client, logged_in):
    headers = {"Authorization": f"Bearer {logged_in['access_token']}"}
    resp = client.get("/users/me", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["email"] == "mariam@example.ci"
    assert "password_hash" not in body


def test_me_without_token_401(client):
    assert client.get("/users/me").status_code == 401


def test_me_with_tampered_token_401(client, logged_in):
    token = logged_in["access_token"]
    tam = token[:-2] + ("aa" if token[-2:] != "aa" else "bb")
    headers = {"Authorization": f"Bearer {tam}"}
    assert client.get("/users/me", headers=headers).status_code == 401


# -------------------------------- profil ---------------------------------


def test_update_profile(client, logged_in):
    headers = {"Authorization": f"Bearer {logged_in['access_token']}"}
    resp = client.put("/users/me", json={"full_name": "Mariam Konaté", "phone": "07 07 07 07 07"}, headers=headers)
    assert resp.status_code == 200
    assert resp.json()["full_name"] == "Mariam Konaté"


def test_change_password_requires_current(client, logged_in):
    headers = {"Authorization": f"Bearer {logged_in['access_token']}"}
    resp = client.put(
        "/users/me",
        json={"new_password": "NouveauMdp123", "current_password": "FAUX"},
        headers=headers,
    )
    assert resp.status_code == 422


def test_change_password_full_flow(client, logged_in):
    headers = {"Authorization": f"Bearer {logged_in['access_token']}"}
    resp = client.put(
        "/users/me",
        json={"new_password": "NouveauMdp123", "current_password": "MotDePasse123"},
        headers=headers,
    )
    assert resp.status_code == 200
    # L'ancien mot de passe ne fonctionne plus, le nouveau oui
    assert client.post("/auth/login", json={"email": "mariam@example.ci", "password": "MotDePasse123"}).status_code == 401
    assert client.post("/auth/login", json={"email": "mariam@example.ci", "password": "NouveauMdp123"}).status_code == 200


# --------------------------------- admin ---------------------------------


@pytest.fixture()
def admin_logged(client):
    create_user_api(client, "admin@marcheci.ci", role="ADMIN")
    resp = client.post("/auth/login", json={"email": "admin@marcheci.ci", "password": "MotDePasse123"})
    return resp.json()


def test_users_list_requires_admin(client, logged_in):
    headers = {"Authorization": f"Bearer {logged_in['access_token']}"}
    assert client.get("/users", headers=headers).status_code == 403


def test_users_list_admin(client, logged_in, admin_logged):
    headers = {"Authorization": f"Bearer {admin_logged['access_token']}"}
    resp = client.get("/users", headers=headers)
    assert resp.status_code == 200
    emails = [row["email"] for row in resp.json()]
    assert "admin@marcheci.ci" in emails
