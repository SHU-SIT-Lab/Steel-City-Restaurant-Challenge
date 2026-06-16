"""Firestore client initialization."""

from __future__ import annotations

import os
from typing import Optional

import firebase_admin
from firebase_admin import credentials, firestore

from config import credentials_path, database_config

_app: Optional[firebase_admin.App] = None
_db: Optional[firestore.Client] = None


def get_firestore_client() -> firestore.Client:
    """Return a singleton Firestore client."""
    global _app, _db

    if _db is not None:
        return _db

    cred_file = credentials_path()
    if not cred_file.is_file():
        raise FileNotFoundError(
            f"Firebase credentials not found at {cred_file}. "
            "Add your service account JSON as configs/security_key.json."
        )

    os.environ.setdefault("GOOGLE_APPLICATION_CREDENTIALS", str(cred_file))

    if not firebase_admin._apps:
        cred = credentials.Certificate(str(cred_file))
        _app = firebase_admin.initialize_app(cred)

    database_id = database_config().get("database_id", "(default)")
    _db = firestore.client(database_id=database_id)
    return _db
