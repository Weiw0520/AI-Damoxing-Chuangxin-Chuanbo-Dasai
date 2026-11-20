"""Explicit local browser-test model. Not a production entry or live AI evidence."""
import os
from backend.a_ai_main import create_ai_app
from backend.tests.test_refiner import Scripted


def transform(segments, payload):
    return segments[:1] if '删除第二段' in payload['instruction'] else segments


model = Scripted(transform=transform)
model.label = model.verify_label = 'async-edit-regression-fixture-NOT-LIVE'
app = create_ai_app(os.environ['DRAFT_DB_PATH'], model_factory=lambda: model)
