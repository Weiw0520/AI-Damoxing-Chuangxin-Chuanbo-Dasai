"""Opt-in B integration entry; the existing mock app is not changed."""
import os

from backend.main import create_app
from backend.real_generator import generate

app = create_app(db_path=os.getenv("B_DRAFT_DB_PATH", "data/b-real.sqlite3"), generator=generate)
