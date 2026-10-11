from contextlib import closing

import pytest

from app.db import connect
from data.seed import seed


@pytest.fixture
def db_path(tmp_path):
    path = tmp_path / "orders.db"
    seed(path)
    return path


@pytest.fixture
def conn(db_path):
    with closing(connect(db_path)) as conn:
        yield conn
