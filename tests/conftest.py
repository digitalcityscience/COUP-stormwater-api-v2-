import pytest
from fastapi.testclient import TestClient

from stormwater_api.api.main import app


@pytest.fixture
def unauthorized_api_test_client():
    yield TestClient(app)
