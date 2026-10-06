import json
from pathlib import Path

import pytest

from inkbound.realm.models import RealmSpec


@pytest.fixture(params=["fantasy", "horror", "science_fiction"])
def spec(request):
    return RealmSpec.model_validate_json(Path(f"fixtures/{request.param}.json").read_bytes())


@pytest.fixture
def fantasy_data():
    return json.loads(Path("fixtures/fantasy.json").read_text())
