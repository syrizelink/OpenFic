"""PostgreSQL tests create and drop only uniquely named databases they own."""
import os
from uuid import uuid4

import pytest
from sqlalchemy import create_engine
from sqlalchemy.engine import make_url

from app.storage.urls import normalize_postgres_url


@pytest.fixture
def postgres_database_factory():
    configured_url = os.getenv("OPENFIC_POSTGRES_TEST_URL")
    if not configured_url:
        pytest.skip("OPENFIC_POSTGRES_TEST_URL is not configured")
    url = make_url(normalize_postgres_url(configured_url))
    admin = create_engine(url, isolation_level="AUTOCOMMIT")
    databases = []

    def create_database():
        name = "openfic_test_" + uuid4().hex
        with admin.connect() as conn:
            conn.exec_driver_sql(f'CREATE DATABASE "{name}"')
            conn.exec_driver_sql(f'ALTER DATABASE "{name}" SET timezone TO \'Asia/Shanghai\'')
        databases.append(name)
        return url.set(database=name).render_as_string(hide_password=False)

    try:
        yield create_database
    finally:
        with admin.connect() as conn:
            for name in reversed(databases):
                conn.exec_driver_sql(f'DROP DATABASE "{name}" WITH (FORCE)')
        admin.dispose()
