from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import models
from app.database import Base
from app.main import app
from app.security import get_db, hash_password


@pytest.fixture()
def client():
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

    with TestClient(app) as test_client:
        yield test_client, TestingSessionLocal

    app.dependency_overrides.clear()


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _make_user(db, username: str, role: str = "user") -> models.User:
    user = models.User(
        username=username,
        display_name=username.title(),
        password_hash=hash_password("geheim123"),
        role=role,
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _login(client, username: str) -> str:
    res = client.post(
        "/api/auth/login",
        json={"username": username, "password": "geheim123"},
    )
    assert res.status_code == 200
    return res.json()["access_token"]


def _add_invoice(db, owner_id: int, bauvorhaben: str, filename: str = "a.pdf") -> models.Invoice:
    inv = models.Invoice(
        owner_id=owner_id,
        filename=filename,
        stored_filename=f"{owner_id}-{filename}-{bauvorhaben}",
        bauvorhaben=bauvorhaben,
        rechnungsbetrag=10,
        waehrung="EUR",
    )
    db.add(inv)
    db.commit()
    db.refresh(inv)
    return inv


def test_users_only_see_own_invoices(client):
    test_client, SessionLocal = client
    db = SessionLocal()
    alice = _make_user(db, "alice")
    bob = _make_user(db, "bob")
    alice_id = alice.id
    _add_invoice(db, alice_id, "Haus A", "alice.pdf")
    _add_invoice(db, bob.id, "Haus B", "bob.pdf")
    db.close()

    alice_token = _login(test_client, "alice")
    res = test_client.get("/api/invoices", headers=_auth(alice_token))
    assert res.status_code == 200
    data = res.json()
    assert len(data) == 1
    assert data[0]["filename"] == "alice.pdf"
    assert data[0]["owner_id"] == alice_id


def test_share_bauvorhaben_grants_mutual_visibility(client):
    test_client, SessionLocal = client
    db = SessionLocal()
    alice = _make_user(db, "alice")
    bob = _make_user(db, "bob")
    alice_id = alice.id
    bob_id = bob.id
    alice_inv = _add_invoice(db, alice_id, "Gemeinsam", "alice.pdf")
    alice_inv_id = alice_inv.id
    bob_inv = _add_invoice(db, bob_id, "Gemeinsam", "bob.pdf")
    bob_inv_id = bob_inv.id
    _add_invoice(db, bob_id, "Nur Bob", "secret.pdf")
    db.close()

    alice_token = _login(test_client, "alice")
    bob_token = _login(test_client, "bob")

    # Vor dem Teilen: nur eigene
    assert len(test_client.get("/api/invoices", headers=_auth(alice_token)).json()) == 1

    share = test_client.post(
        "/api/shares",
        headers=_auth(alice_token),
        json={"bauvorhaben": "Gemeinsam", "user_id": bob_id},
    )
    assert share.status_code == 201

    # Alice sieht Bobs Rechnung unter „Gemeinsam“, nicht „Nur Bob“
    alice_list = test_client.get("/api/invoices", headers=_auth(alice_token)).json()
    names = {i["filename"] for i in alice_list}
    assert names == {"alice.pdf", "bob.pdf"}

    # Bob sieht Alices Rechnung unter „Gemeinsam“
    bob_list = test_client.get("/api/invoices", headers=_auth(bob_token)).json()
    bob_names = {i["filename"] for i in bob_list}
    assert "alice.pdf" in bob_names
    assert "bob.pdf" in bob_names
    assert "secret.pdf" in bob_names

    # Bob darf Alices Rechnung nicht löschen
    denied = test_client.delete(
        f"/api/invoices/{alice_inv_id}",
        headers=_auth(bob_token),
    )
    assert denied.status_code == 403

    get_ok = test_client.get(
        f"/api/invoices/{alice_inv_id}",
        headers=_auth(bob_token),
    )
    assert get_ok.status_code == 200

    # Freigabe entfernen → Isolation zurück
    revoke = test_client.delete(
        f"/api/shares/{share.json()['id']}",
        headers=_auth(alice_token),
    )
    assert revoke.status_code == 204
    alice_again = test_client.get("/api/invoices", headers=_auth(alice_token)).json()
    assert len(alice_again) == 1
    assert alice_again[0]["id"] == alice_inv_id
    assert bob_inv_id


def test_cannot_share_without_own_invoices(client):
    test_client, SessionLocal = client
    db = SessionLocal()
    _make_user(db, "alice")
    bob = _make_user(db, "bob")
    bob_id = bob.id
    _add_invoice(db, bob_id, "Fremd", "bob.pdf")
    db.close()

    alice_token = _login(test_client, "alice")
    res = test_client.post(
        "/api/shares",
        headers=_auth(alice_token),
        json={"bauvorhaben": "Fremd", "user_id": bob_id},
    )
    assert res.status_code == 403


def test_user_directory(client):
    test_client, SessionLocal = client
    db = SessionLocal()
    _make_user(db, "alice")
    _make_user(db, "bob")
    db.close()

    token = _login(test_client, "alice")
    res = test_client.get("/api/users/directory", headers=_auth(token))
    assert res.status_code == 200
    data = res.json()
    assert len(data) == 1
    assert data[0]["username"] == "bob"
    assert "password_hash" not in data[0]
