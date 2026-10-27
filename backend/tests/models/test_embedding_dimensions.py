"""The form button reads dimensions without changing saved model configurations."""

import json

from httpx import Response
import pytest
import respx

from app.background.jobs.definitions import retrieval_chapter_index_batch as worker
from app.core.encryption import EncryptionService
from app.models.repos import model_provider_repo, model_repo
from app.retrieval.chapter_index import ChapterIndexIntegrationService
from app.retrieval.service import OpenFicRetrievalService
from app.settings import settings


async def _model(session, dimensions=None):
    provider = await model_provider_repo.create(
        session,
        name="Embedding provider",
        provider_type="cohere",
        url="https://embedding.test/v1",
        api_key_encrypted=EncryptionService(settings.encryption_key).encrypt(
            "test-key"
        ),
    )
    return await model_repo.create(
        session,
        name="Embedding model",
        provider_id=provider.id,
        model_id="test-embedding",
        task_type="embedding",
        dimensions=dimensions,
    )


@pytest.mark.asyncio
@respx.mock
async def test_form_probes_unsaved_model_and_saves_dimensions_in_existing_field(
    session, client
):
    existing = await _model(session, 1536)
    requests = []

    def respond(request):
        payload = json.loads(request.content)
        assert payload["model"] == "unsaved-model"
        assert request.headers["authorization"] == "Bearer test-key"
        requests.append(payload)
        return Response(
            200,
            json={
                "data": [
                    {"object": "embedding", "index": 0, "embedding": [0.1] * 6144}
                ],
                "model": "unsaved-model",
            },
        )

    respx.post("https://embedding.test/v1/embeddings").mock(side_effect=respond)
    response = await client.post(
        "/api/v1/models/embedding-dimensions",
        json={
            "provider_id": existing.provider_id,
            "model_id": "unsaved-model",
        },
    )
    assert response.status_code == 200
    assert response.json() == {"dimensions": 6144}
    assert "dimensions" not in requests[0]
    await session.refresh(existing)
    assert existing.dimensions == 1536
    assert len(await model_repo.get_all(session)) == 1

    response = await client.post(
        "/api/v1/models",
        json={
            "provider_id": existing.provider_id,
            "model_id": "unsaved-model",
            "name": "New embedding model",
            "task_type": "embedding",
            "dimensions": response.json()["dimensions"],
        },
    )
    assert response.status_code == 201
    saved = response.json()
    assert saved["dimensions"] == 6144
    embedding_client = await worker._build_embedding_client(session, saved["id"])
    assert embedding_client.config.dimensions == 6144
    assert len(await embedding_client.embed_single("query")) == 6144
    assert requests[1]["dimensions"] == 6144
    assert len(requests) == 2


@pytest.mark.asyncio
@respx.mock
@pytest.mark.parametrize("vector", [[], [float("nan")], [float("inf")]])
async def test_invalid_probe_keeps_saved_configuration(session, client, vector):
    model = await _model(session, 1536)
    respx.post("https://embedding.test/v1/embeddings").mock(
        return_value=Response(
            200,
            headers={"content-type": "application/json"},
            content=json.dumps(
                {
                    "data": [{"object": "embedding", "index": 0, "embedding": vector}],
                    "model": model.model_id,
                }
            ),
        )
    )
    response = await client.post(
        "/api/v1/models/embedding-dimensions",
        json={
            "provider_id": model.provider_id,
            "model_id": model.model_id,
        },
    )
    assert response.status_code == 400
    await session.refresh(model)
    assert model.dimensions == 1536


@pytest.mark.asyncio
@respx.mock
async def test_form_detection_failure_keeps_saved_configuration(session, client):
    model = await _model(session, 1536)
    respx.post("https://embedding.test/v1/embeddings").mock(
        return_value=Response(401, json={"error": {"message": "Invalid API key"}})
    )
    response = await client.post(
        "/api/v1/models/embedding-dimensions",
        json={
            "provider_id": model.provider_id,
            "model_id": model.model_id,
        },
    )
    assert response.status_code == 400
    assert "Invalid API key" in response.json()["detail"]
    await session.refresh(model)
    assert model.dimensions == 1536


@pytest.mark.asyncio
async def test_form_detection_rejects_unknown_provider(client):
    response = await client.post(
        "/api/v1/models/embedding-dimensions",
        json={
            "provider_id": "missing",
            "model_id": "model",
        },
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_omitting_dimensions_preserves_value_and_null_clears_it(session, client):
    model = await _model(session, 3)
    response = await client.put(f"/api/v1/models/{model.id}", json={"name": "Renamed"})
    assert response.status_code == 200
    assert response.json()["dimensions"] == 3
    response = await client.put(f"/api/v1/models/{model.id}", json={"dimensions": None})
    assert response.status_code == 200
    assert response.json()["dimensions"] is None


@pytest.mark.asyncio
@pytest.mark.parametrize("dimensions", [None, 4])
async def test_bound_index_dimensions_cannot_be_cleared_or_changed(
    session, client, tmp_path, dimensions
):
    model = await _model(session, 3)
    contract = ChapterIndexIntegrationService().build_contract(model)
    await OpenFicRetrievalService(base_dir=tmp_path / "lancedb").register_index(
        session,
        "bound-index",
        contract,
    )
    await session.commit()
    response = await client.put(
        f"/api/v1/models/{model.id}", json={"dimensions": dimensions}
    )
    assert response.status_code == 400
    await session.refresh(model)
    assert model.dimensions == 3
