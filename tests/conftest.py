"""pytest fixtures for the TripMindAI test suite.

Environment constraints of this sandbox (deliberate, see task brief):
* pytest's ``tmp_path`` / ``tmp_path_factory`` are NOT used, because tempfile
  cannot create directories under the current Windows sandbox.  Every test gets
  its own directory under ``tests/.tmp/`` created with ``os.makedirs`` and
  removed in the fixture teardown.
* ``TRIPMIND_SKIP_DEFAULT_APP`` must be set *before* any ``app.*`` module is
  imported, otherwise ``app.main`` instantiates the production application on
  import and connects to the real database from ``.env``.
* Every test application uses its own throw-away SQLite file; the real
  ``tripmind.sqlite3`` and the running server on :8000 are never touched.
"""
from __future__ import annotations

import os
import shutil
import uuid
from dataclasses import replace
from pathlib import Path

# Must run before the ``app`` imports below (see module docstring).
os.environ.setdefault('TRIPMIND_SKIP_DEFAULT_APP', '1')

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app import legs  # noqa: E402
from app.config import Settings  # noqa: E402
from app.main import create_app  # noqa: E402

TESTS_DIR = Path(__file__).resolve().parent
TMP_ROOT = TESTS_DIR / '.tmp'


def make_settings(work_dir: Path, db_name: str = 'tripmind-test.sqlite3', **overrides) -> Settings:
    """Replacement Settings pointing at a throw-away SQLite file.

    As required by the brief: no AMap key (no real outbound calls) and a dummy
    DashScope key (so /api/health and /api/models report "configured").
    """
    database_url = f'sqlite:///{(work_dir / db_name).as_posix()}'
    values = {
        'database_url': database_url,
        'initialize_database': True,
        'dashscope_api_key': 'test-key',
        'amap_api_key': '',
    }
    values.update(overrides)
    return replace(Settings(), **values)


@pytest.fixture()
def work_dir():
    """Per-test writable directory under tests/.tmp (no pytest tmp_path)."""
    os.makedirs(TMP_ROOT, exist_ok=True)
    path = TMP_ROOT / f'case-{uuid.uuid4().hex[:12]}'
    os.makedirs(path, exist_ok=True)
    try:
        yield path
    finally:
        shutil.rmtree(path, ignore_errors=True)


@pytest.fixture(autouse=True)
def _clear_legs_cache():
    """app.legs keeps a process-wide cache; never let it leak between tests."""
    legs.clear_cache()
    yield
    legs.clear_cache()


@pytest.fixture()
def settings(work_dir):
    return make_settings(work_dir)


@pytest.fixture()
def app_instance(settings):
    application = create_app(settings)
    try:
        yield application
    finally:
        # Release the SQLite file handle before tests/.tmp cleanup.
        application.state.engine.dispose()


@pytest.fixture()
def client(app_instance):
    test_client = TestClient(app_instance)
    try:
        yield test_client
    finally:
        test_client.close()


@pytest.fixture()
def session_factory(app_instance):
    return app_instance.state.session_factory


@pytest.fixture()
def settings_with_amap(work_dir):
    """Same isolated app, but with a dummy AMap web key.

    Only used for branches that must not perform network I/O (e.g. the empty
    ``segments`` early return of /api/route-geometry).
    """
    return make_settings(work_dir, db_name='tripmind-test-amap.sqlite3',
                         amap_api_key='test-amap-key')


@pytest.fixture()
def client_with_amap_key(settings_with_amap):
    application = create_app(settings_with_amap)
    test_client = TestClient(application)
    try:
        yield test_client
    finally:
        test_client.close()
        application.state.engine.dispose()
