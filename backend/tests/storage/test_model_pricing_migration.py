import importlib
import json

from sqlalchemy import create_engine, text


migration = importlib.import_module(
    "app.storage.migrations.versions.1019_add_model_pricing_and_task_cost"
)


def _create_model_schema(connection) -> None:
    connection.execute(
        text(
            "CREATE TABLE model_providers ("
            "id TEXT PRIMARY KEY, provider_type TEXT NOT NULL, url TEXT NOT NULL"
            ")"
        )
    )
    connection.execute(
        text(
            "CREATE TABLE models ("
            "id TEXT PRIMARY KEY, provider_id TEXT NOT NULL, model_id TEXT NOT NULL, "
            "task_type TEXT NOT NULL, context_length INTEGER NOT NULL, "
            "input_price FLOAT NOT NULL, output_price FLOAT NOT NULL, "
            "cache_read_price FLOAT NOT NULL, cache_write_price FLOAT NOT NULL"
            ")"
        )
    )


def test_backfill_model_metadata_from_bundled_catalog(tmp_path) -> None:
    snapshot_path = tmp_path / "modelsdev-catalog.snapshot.json"
    snapshot_path.write_text(
        json.dumps(
            {
                "providers": [
                    {
                        "provider_type": "openai",
                        "api": "https://api.openai.com/v1",
                        "models": [
                            {
                                "model_id": "gpt-4o",
                                "task_type": "llm",
                                "metadata": {
                                    "limit": {"context": 200000},
                                    "cost": {
                                        "input": 2.5,
                                        "output": 10,
                                        "cache_read": 1.25,
                                        "cache_write": 3,
                                    },
                                },
                            }
                        ],
                    },
                    {
                        "provider_type": "cerebras",
                        "models": [
                            {
                                "model_id": "llama-3.1-8b",
                                "task_type": "llm",
                                "metadata": {
                                    "limit": {"context": 128000},
                                    "cost": {
                                        "input": 0.6,
                                        "output": 0.8,
                                    },
                                },
                            }
                        ],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    engine = create_engine("sqlite:///:memory:")

    with engine.begin() as connection:
        _create_model_schema(connection)
        connection.execute(
            text(
                "INSERT INTO model_providers (id, provider_type, url) VALUES "
                "('openai-provider', 'openai', 'https://api.openai.com/v1'), "
                "('compatible-provider', 'openai-compatible', 'https://api.openai.com/v1'), "
                "('cerebras-provider', 'cerebras', 'https://api.cerebras.ai/v1'), "
                "('unknown-provider', 'openai-compatible', 'https://unknown.example/v1')"
            )
        )
        connection.execute(
            text(
                "INSERT INTO models "
                "(id, provider_id, model_id, task_type, context_length, input_price, "
                "output_price, cache_read_price, cache_write_price) VALUES "
                "('standard-model', 'openai-provider', 'gpt-4o', 'llm', 128000, 0, 0, 0, 0), "
                "('compatible-model', 'compatible-provider', 'gpt-4o', 'llm', 128000, 0, 0, 0, 0), "
                "('cerebras-model', 'cerebras-provider', 'llama-3.1-8b', 'llm', 128000, 0, 0, 0, 0), "
                "('unmatched-model', 'unknown-provider', 'gpt-4o', 'llm', 128000, 0, 0, 0, 0)"
            )
        )

        migration._backfill_model_metadata(connection, snapshot_path)

        rows = connection.execute(
            text(
                "SELECT id, context_length, input_price, output_price, "
                "cache_read_price, cache_write_price FROM models ORDER BY id"
            )
        ).mappings().all()

    assert rows == [
        {
            "id": "cerebras-model",
            "context_length": 128000,
            "input_price": 0.6,
            "output_price": 0.8,
            "cache_read_price": 0.0,
            "cache_write_price": 0.0,
        },
        {
            "id": "compatible-model",
            "context_length": 200000,
            "input_price": 2.5,
            "output_price": 10.0,
            "cache_read_price": 1.25,
            "cache_write_price": 3.0,
        },
        {
            "id": "standard-model",
            "context_length": 200000,
            "input_price": 2.5,
            "output_price": 10.0,
            "cache_read_price": 1.25,
            "cache_write_price": 3.0,
        },
        {
            "id": "unmatched-model",
            "context_length": 128000,
            "input_price": 0.0,
            "output_price": 0.0,
            "cache_read_price": 0.0,
            "cache_write_price": 0.0,
        },
    ]


def test_bundled_catalog_path_contains_provider_metadata() -> None:
    provider_urls, catalog_models = migration._load_catalog_index(
        migration._BUNDLED_SNAPSHOT_PATH
    )

    assert provider_urls["openai"] == "https://api.openai.com/v1"
    assert ("openai", "gpt-4o", "llm") in catalog_models
