from __future__ import annotations

from sqlalchemy import or_, select
from sqlalchemy.orm import Session
from sqlalchemy.sql import ColumnElement

from app import models


def shared_partner_ids(db: Session, user_id: int, bauvorhaben: str) -> set[int]:
    """User-IDs, mit denen das Bauvorhaben geteilt ist (in beide Richtungen)."""
    name = bauvorhaben.strip()
    rows = db.execute(
        select(
            models.BauvorhabenShare.owner_id,
            models.BauvorhabenShare.shared_with_user_id,
        ).where(models.BauvorhabenShare.bauvorhaben == name)
    ).all()
    partners: set[int] = set()
    for owner_id, shared_with in rows:
        if owner_id == user_id:
            partners.add(shared_with)
        elif shared_with == user_id:
            partners.add(owner_id)
    return partners


def invoice_visibility_filter(db: Session, user_id: int) -> ColumnElement[bool]:
    """SQL-Filter: eigene Rechnungen oder solche aus geteilten Bauvorhaben."""
    # (bauvorhaben, owner_id) der Owner, die mit mir geteilt haben
    shared_to_me = select(
        models.BauvorhabenShare.bauvorhaben,
        models.BauvorhabenShare.owner_id,
    ).where(models.BauvorhabenShare.shared_with_user_id == user_id)

    # (bauvorhaben, shared_with) – Rechnungen der Empfänger meiner Freigaben
    shared_by_me = select(
        models.BauvorhabenShare.bauvorhaben,
        models.BauvorhabenShare.shared_with_user_id.label("owner_id"),
    ).where(models.BauvorhabenShare.owner_id == user_id)

    shared_pairs = shared_to_me.union(shared_by_me).subquery()

    return or_(
        models.Invoice.owner_id == user_id,
        select(1)
        .where(
            shared_pairs.c.bauvorhaben == models.Invoice.bauvorhaben,
            shared_pairs.c.owner_id == models.Invoice.owner_id,
        )
        .exists(),
    )


def user_can_access_invoice(db: Session, user: models.User, invoice: models.Invoice) -> bool:
    if invoice.owner_id == user.id:
        return True
    if invoice.owner_id is None:
        return False
    partners = shared_partner_ids(db, user.id, invoice.bauvorhaben)
    return invoice.owner_id in partners


def user_can_manage_invoice(user: models.User, invoice: models.Invoice) -> bool:
    """Bearbeiten/Löschen nur für den Eigentümer der Rechnung."""
    return invoice.owner_id == user.id


def user_can_share_bauvorhaben(db: Session, user_id: int, bauvorhaben: str) -> bool:
    """Freigeben darf, wer eigene Rechnungen unter diesem Bauvorhaben hat
    oder bereits Owner einer Freigabe ist.
    """
    name = bauvorhaben.strip()
    own = db.execute(
        select(models.Invoice.id)
        .where(
            models.Invoice.owner_id == user_id,
            models.Invoice.bauvorhaben == name,
        )
        .limit(1)
    ).scalar_one_or_none()
    if own is not None:
        return True
    existing_share = db.execute(
        select(models.BauvorhabenShare.id)
        .where(
            models.BauvorhabenShare.owner_id == user_id,
            models.BauvorhabenShare.bauvorhaben == name,
        )
        .limit(1)
    ).scalar_one_or_none()
    return existing_share is not None
