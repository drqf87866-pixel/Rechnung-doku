from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.main import app
from app.security import get_db, hash_password
from app import models


@pytest.fixture()
def client(tmp_path, monkeypatch):
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    monkeypatch.setattr(
        "app.config.settings.jwt_secret",
        "test-secret-at-least-32-bytes-long!!",
    )

    with TestClient(app) as test_client:
        yield test_client, TestingSessionLocal

    app.dependency_overrides.clear()


def _auth_header(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_setup_status_and_first_admin(client):
    test_client, _ = client
    status = test_client.get("/api/auth/setup-status")
    assert status.status_code == 200
    assert status.json()["needs_setup"] is True

    created = test_client.post(
        "/api/auth/setup",
        json={
            "username": "Admin",
            "password": "geheim123",
            "display_name": "Chef",
        },
    )
    assert created.status_code == 201
    body = created.json()
    assert body["user"]["username"] == "admin"
    assert body["user"]["role"] == "admin"
    assert body["access_token"]

    again = test_client.post(
        "/api/auth/setup",
        json={"username": "other", "password": "geheim123"},
    )
    assert again.status_code == 409
    assert test_client.get("/api/auth/setup-status").json()["needs_setup"] is False


def test_login_and_protect_invoices(client):
    test_client, SessionLocal = client
    db = SessionLocal()
    db.add(
        models.User(
            username="alice",
            display_name="Alice",
            password_hash=hash_password("geheim123"),
            role="user",
            is_active=True,
        )
    )
    db.commit()
    db.close()

    denied = test_client.get("/api/invoices")
    assert denied.status_code == 401

    bad = test_client.post(
        "/api/auth/login",
        json={"username": "alice", "password": "wrong"},
    )
    assert bad.status_code == 401

    ok = test_client.post(
        "/api/auth/login",
        json={"username": "alice", "password": "geheim123"},
    )
    assert ok.status_code == 200
    token = ok.json()["access_token"]

    listed = test_client.get("/api/invoices", headers=_auth_header(token))
    assert listed.status_code == 200
    assert listed.json() == []


def test_admin_user_crud(client):
    test_client, SessionLocal = client
    db = SessionLocal()
    db.add(
        models.User(
            username="boss",
            display_name="Boss",
            password_hash=hash_password("geheim123"),
            role="admin",
            is_active=True,
        )
    )
    db.commit()
    db.close()

    login = test_client.post(
        "/api/auth/login",
        json={"username": "boss", "password": "geheim123"},
    )
    token = login.json()["access_token"]
    headers = _auth_header(token)

    created = test_client.post(
        "/api/users",
        headers=headers,
        json={
            "username": "bob",
            "display_name": "Bob",
            "password": "passwort1",
            "role": "user",
        },
    )
    assert created.status_code == 201
    user_id = created.json()["id"]

    patched = test_client.patch(
        f"/api/users/{user_id}",
        headers=headers,
        json={"is_active": False},
    )
    assert patched.status_code == 200
    assert patched.json()["is_active"] is False

    users = test_client.get("/api/users", headers=headers)
    assert users.status_code == 200
    assert len(users.json()) == 2

    deleted = test_client.delete(f"/api/users/{user_id}", headers=headers)
    assert deleted.status_code == 204


def test_non_admin_cannot_list_users(client):
    test_client, SessionLocal = client
    db = SessionLocal()
    db.add(
        models.User(
            username="alice",
            display_name="Alice",
            password_hash=hash_password("geheim123"),
            role="user",
            is_active=True,
        )
    )
    db.commit()
    db.close()

    login = test_client.post(
        "/api/auth/login",
        json={"username": "alice", "password": "geheim123"},
    )
    token = login.json()["access_token"]
    res = test_client.get("/api/users", headers=_auth_header(token))
    assert res.status_code == 403
