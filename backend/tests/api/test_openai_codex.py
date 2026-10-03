import asyncio
import shutil
from dataclasses import replace
from datetime import UTC, datetime, timedelta
import base64
from urllib.parse import parse_qs, urlencode, urlsplit

import httpx
import jwt
import pytest
import pytest_asyncio
import respx
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlmodel import SQLModel
from cryptography.hazmat.primitives.asymmetric import rsa

from app.core.encryption import EncryptionService
from app.models.services.openai_codex_service import (
    OPENAI_CODEX_API_BASE_URL,
    OPENAI_CODEX_PROVIDER_TYPE,
    OPENAI_CODEX_JWKS_URI,
    OPENAI_CODEX_TOKEN_ENDPOINT,
    OpenAICodexCredentials,
    OpenAICodexCredentialStore,
)
from app.models.repos import model_provider_repo
from app.settings import settings
from app.storage.database import get_session


@pytest_asyncio.fixture(scope="module")
async def credential_database_template(tmp_path_factory):
    """Build an empty schema once; each test gets an independent database copy."""
    from tests.model_registry import register_sqlmodel_models

    register_sqlmodel_models()
    required_tables = [SQLModel.metadata.tables[name] for name in (
        "model_providers", "model_provider_oauth_registrations", "tasks", "agent_child_runs",
    )]
    path = tmp_path_factory.mktemp("oauth-schema") / "template.db"
    engine = create_async_engine(f"sqlite+aiosqlite:///{path}")
    try:
        async with engine.begin() as connection:
            await connection.run_sync(lambda sync_connection: SQLModel.metadata.create_all(sync_connection, tables=required_tables))
    finally:
        await engine.dispose()
    return path


@pytest_asyncio.fixture
async def credential_runtime(tmp_path, credential_database_template):
    from app.api.routers.openai_codex import router
    from app.api.routers.model_providers import router as provider_router

    path = tmp_path / "credentials.db"
    shutil.copyfile(credential_database_template, path)
    engine = create_async_engine(f"sqlite+aiosqlite:///{path}")
    try:
        async with AsyncSession(engine, expire_on_commit=False) as session:
            async def runtime_session():
                yield session

            app = FastAPI()
            app.include_router(router, prefix="/api/v1")
            app.include_router(provider_router, prefix="/api/v1")
            app.dependency_overrides[get_session] = runtime_session
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
                yield client, session
    finally:
        await engine.dispose()


def _credentials():
    return OpenAICodexCredentials(
        client_id="oaiapp_test",
        ext_agent_host_id="urn:uuid:11111111-1111-4111-8111-111111111111",
        issuer="https://auth.openai.com",
        subject="subject",
        email="user@example.com",
        id_token="id-token",
        access_token="access-token",
        refresh_token="refresh-token",
        token_type="Bearer",
        expires_at=datetime.now(UTC) + timedelta(hours=1),
        scopes=frozenset({"chatgpt.tokens.use.direct"}),
    )


@pytest.mark.asyncio
async def test_openai_codex_auth_start_uses_loopback_redirect(client):
    response = await client.post("/api/v1/openai-codex/auth/start", json={})

    assert response.status_code == 200
    payload = response.json()
    assert payload["provider_id"] is None
    redirect_uri = parse_qs(urlsplit(payload["authorization_url"]).query)["redirect_uri"][0]
    assert redirect_uri.startswith("http://127.0.0.1:")
    assert "localhost" not in redirect_uri
    assert "access_token" not in payload["authorization_url"]
    progress = await client.get(f"/api/v1/openai-codex/auth/status/{payload['authorization_id']}")
    assert progress.json()["status"] == "pending"


@pytest.mark.asyncio
@pytest.mark.parametrize("manual", [False, True])
@respx.mock
async def test_openai_codex_callback_validates_and_stores_new_registration(client, session, manual):
    start = await client.post("/api/v1/openai-codex/auth/start", json={})
    authorize_params = parse_qs(urlsplit(start.json()["authorization_url"]).query)
    state = authorize_params["state"][0]
    client_id = "oaiapp_issued"

    signing_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public_numbers = signing_key.public_key().public_numbers()
    jwk = {
        "kty": "RSA",
        "kid": f"test-key-api-{manual}",
        "use": "sig",
        "alg": "RS256",
        "n": base64.urlsafe_b64encode(
            public_numbers.n.to_bytes((public_numbers.n.bit_length() + 7) // 8, "big")
        ).rstrip(b"=").decode(),
        "e": base64.urlsafe_b64encode(
            public_numbers.e.to_bytes((public_numbers.e.bit_length() + 7) // 8, "big")
        ).rstrip(b"=").decode(),
    }
    id_token = jwt.encode(
        {
            "iss": "https://auth.openai.com",
            "aud": client_id,
            "sub": "subject",
            "email": "user@example.com",
            "nonce": authorize_params["nonce"][0],
            "iat": datetime.now(UTC),
            "exp": datetime.now(UTC) + timedelta(minutes=5),
        },
        signing_key,
        algorithm="RS256",
        headers={"kid": f"test-key-api-{manual}"},
    )
    respx.get(OPENAI_CODEX_JWKS_URI).mock(
        return_value=httpx.Response(200, json={"keys": [jwk]})
    )
    exchange = respx.post(OPENAI_CODEX_TOKEN_ENDPOINT).mock(
        return_value=httpx.Response(
            200,
            json={
                "access_token": "access-token",
                "refresh_token": "refresh-token",
                "id_token": id_token,
                "token_type": "Bearer",
                "expires_in": 3600,
                "scope": "openid profile email offline_access resource.invoke chatgpt.tokens.use.direct",
            },
        )
    )

    params = {"code": "authorization-code", "state": state, "client_id": client_id}
    if manual:
        callback = await client.post("/api/v1/openai-codex/auth/complete", json={
            "authorization_id": state,
            "callback_url": authorize_params["redirect_uri"][0] + "?" + urlencode(params),
        })
    else:
        callback = await client.get("/api/v1/openai-codex/auth/callback", params=params)

    assert callback.status_code == 200
    assert "access-token" not in callback.text
    exchange_form = parse_qs(exchange.calls[0].request.content.decode())
    assert exchange_form["code"] == ["authorization-code"]
    assert "authorization_code" not in exchange_form
    providers = await model_provider_repo.get_all(session)
    assert len(providers) == 1
    assert providers[0].provider_type == OPENAI_CODEX_PROVIDER_TYPE
    assert providers[0].name.startswith("OpenAI Codex (user@example.com,")
    assert providers[0].credentials_encrypted != ""
    progress = await client.get(f"/api/v1/openai-codex/auth/status/{state}")
    assert progress.json() == {"status": "success", "provider_id": providers[0].id, "registration_id": client_id}
    replay = await client.get("/api/v1/openai-codex/auth/callback", params={"state": state, "code": "replay"})
    assert replay.status_code == 400
    assert exchange.call_count == 1
    replay_manual = await client.post("/api/v1/openai-codex/auth/complete", json={
        "authorization_id": state,
        "callback_url": authorize_params["redirect_uri"][0] + "?" + urlencode(params),
    })
    assert replay_manual.status_code == 400
    assert exchange.call_count == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("revocation_status", [200, 503])
@respx.mock
async def test_openai_codex_delete_revokes_and_removes_provider(credential_runtime, revocation_status, monkeypatch):
    original_sleep = asyncio.sleep
    backoff_delays = []

    async def simulated_backoff(delay):
        backoff_delays.append(delay)
        await original_sleep(0)

    monkeypatch.setattr("app.models.services.openai_codex_service.asyncio.sleep", simulated_backoff)
    client, session = credential_runtime
    provider = await model_provider_repo.create(
        session=session,
        name="user@example.com",
        url=OPENAI_CODEX_API_BASE_URL,
        api_key_encrypted="",
        provider_type=OPENAI_CODEX_PROVIDER_TYPE,
    )
    store = OpenAICodexCredentialStore(EncryptionService(settings.encryption_key))
    store.write(provider, _credentials())
    session.add(provider)
    await session.commit()

    respx.get("https://auth.openai.com/.well-known/openid-configuration").mock(
        return_value=httpx.Response(
            200,
            json={"revocation_endpoint": "https://auth.openai.com/revoke"},
        )
    )
    revoke = respx.post("https://auth.openai.com/revoke").mock(
        return_value=httpx.Response(revocation_status)
    )

    provider_id = provider.id
    response = await client.delete(f"/api/v1/model-providers/{provider_id}")

    assert response.status_code == 204
    assert revoke.call_count == (1 if revocation_status == 200 else 3)
    assert [delay for delay in backoff_delays if delay] == ([] if revocation_status == 200 else [1, 2])
    assert response.headers["X-OAuth-Revocation-Confirmed"] == str(revocation_status == 200).lower()
    assert revoke.calls[0].request.content.find(b"access-token") == -1
    assert await model_provider_repo.get_by_id(session, provider_id) is None


@pytest.mark.asyncio
@pytest.mark.parametrize("credential_state", ["missing", "disconnected", "corrupt"])
@respx.mock
async def test_delete_oauth_provider_without_usable_credentials(credential_runtime, credential_state):
    client, session = credential_runtime
    provider = await model_provider_repo.create(session, "Codex", OPENAI_CODEX_API_BASE_URL, "", OPENAI_CODEX_PROVIDER_TYPE)
    if credential_state == "disconnected":
        OpenAICodexCredentialStore(EncryptionService(settings.encryption_key)).write(provider, _credentials().without_tokens())
    elif credential_state == "corrupt":
        provider.credentials_encrypted = "invalid-ciphertext"
    await session.commit()
    provider_id = provider.id
    response = await client.delete(f"/api/v1/model-providers/{provider_id}")
    assert response.status_code == 204
    assert response.headers["X-OAuth-Revocation-Confirmed"] == str(credential_state != "corrupt").lower()
    assert await model_provider_repo.get_by_id(session, provider_id) is None


@pytest.mark.asyncio
@respx.mock
async def test_openai_codex_model_endpoint_uses_account_models(monkeypatch, client, session):
    provider = await model_provider_repo.create(
        session=session,
        name="user@example.com",
        url=OPENAI_CODEX_API_BASE_URL,
        api_key_encrypted="",
        provider_type=OPENAI_CODEX_PROVIDER_TYPE,
    )
    store = OpenAICodexCredentialStore(EncryptionService(settings.encryption_key))
    store.write(provider, _credentials())
    session.add(provider)
    await session.commit()

    monkeypatch.setattr(
        "app.models.services.model_provider_service.get_openai_codex_access_token",
        lambda _provider_id: _async_access_token(),
    )
    route = respx.get("https://api.openai.com/v1/models").mock(
        return_value=httpx.Response(
            200,
            json={
                "models": [
                    {"slug": "gpt-1", "display_name": "GPT 1", "visibility": "list"}
                ]
            },
        )
    )

    response = await client.get(f"/api/v1/model-providers/{provider.id}/models")

    assert response.status_code == 200
    assert response.json()["models"][0]["id"] == "gpt-1"
    assert route.calls[0].request.headers["authorization"] == "Bearer access-token"


async def _async_access_token() -> str:
    return "access-token"


@pytest.mark.asyncio
async def test_openai_codex_declined_consent_updates_auth_status(client):
    start = await client.post("/api/v1/openai-codex/auth/start", json={})
    state = parse_qs(urlsplit(start.json()["authorization_url"]).query)["state"][0]
    callback = await client.get("/api/v1/openai-codex/auth/callback", params={"state": state, "error": "access_denied"})
    assert callback.status_code == 400
    progress = await client.get(f"/api/v1/openai-codex/auth/status/{state}")
    assert progress.json()["status"] == "error"


@pytest.mark.asyncio
@pytest.mark.parametrize("invalid_part", ["host", "scheme", "port", "path", "state", "duplicate", "fragment", "userinfo"])
@respx.mock
async def test_manual_callback_rejects_unexpected_url_without_consuming_attempt(client, invalid_part):
    start = await client.post("/api/v1/openai-codex/auth/start", json={})
    authorization = start.json()
    params = parse_qs(urlsplit(authorization["authorization_url"]).query)
    state = authorization["authorization_id"]
    base = params["redirect_uri"][0]
    query = urlencode({"state": state, "code": "secret-code", "client_id": "oaiapp_test"})
    url = base + "?" + query
    if invalid_part == "host":
        url = url.replace("127.0.0.1", "example.com")
    elif invalid_part == "scheme":
        url = url.replace("http:", "https:")
    elif invalid_part == "port":
        url = url.replace(f":{urlsplit(base).port}", ":1")
    elif invalid_part == "path":
        url = url.replace("/auth/callback", "/other")
    elif invalid_part == "state":
        url = base + "?" + urlencode({"state": "another-attempt", "code": "secret-code"})
    elif invalid_part == "duplicate":
        url += "&code=another-code"
    elif invalid_part == "fragment":
        url += "#fragment"
    else:
        url = url.replace("127.0.0.1", "user@127.0.0.1")
    response = await client.post("/api/v1/openai-codex/auth/complete", json={
        "authorization_id": state, "callback_url": url,
    })
    assert response.status_code == 400
    assert "secret-code" not in response.text
    progress = await client.get(f"/api/v1/openai-codex/auth/status/{state}")
    assert progress.json()["status"] == "pending"


@pytest.mark.asyncio
@respx.mock
async def test_refresh_rotation_is_serialized_across_database_sessions(credential_runtime):
    _client, session = credential_runtime
    provider = await model_provider_repo.create(
        session, "Plan", OPENAI_CODEX_API_BASE_URL, "", OPENAI_CODEX_PROVIDER_TYPE,
    )
    store = OpenAICodexCredentialStore(EncryptionService(settings.encryption_key))
    store.write(provider, replace(_credentials(), expires_at=datetime.now(UTC) - timedelta(minutes=1)))
    await session.commit()
    provider_id = provider.id

    async def refresh_response(request):
        params = parse_qs(request.content.decode())
        assert params["refresh_token"] == ["refresh-token"]
        await asyncio.sleep(0)
        return httpx.Response(200, json={
            "access_token": "new-access", "refresh_token": "new-refresh", "expires_in": 3600,
        })

    refresh = respx.post(OPENAI_CODEX_TOKEN_ENDPOINT).mock(side_effect=refresh_response)
    async with AsyncSession(session.bind, expire_on_commit=False) as first:
        async with AsyncSession(session.bind, expire_on_commit=False) as second:
            results = await asyncio.gather(
                store._refresh_with_database_lock(first, provider_id),
                store._refresh_with_database_lock(second, provider_id),
            )
    assert refresh.call_count == 1
    assert [result.refresh_token for result in results] == ["new-refresh", "new-refresh"]


@pytest.mark.asyncio
@respx.mock
async def test_deleted_provider_sign_in_reuses_registration(credential_runtime):
    client, session = credential_runtime
    provider = await model_provider_repo.create(session, "Codex", OPENAI_CODEX_API_BASE_URL, "", OPENAI_CODEX_PROVIDER_TYPE)
    store = OpenAICodexCredentialStore(EncryptionService(settings.encryption_key))
    store.write(provider, _credentials())
    await session.commit()
    provider_id = provider.id
    before = await client.post("/api/v1/openai-codex/auth/start", json={"provider_id": provider_id})
    previous_query = parse_qs(urlsplit(before.json()["authorization_url"]).query)
    respx.get("https://auth.openai.com/.well-known/openid-configuration").mock(return_value=httpx.Response(200, json={"revocation_endpoint": "https://auth.openai.com/revoke"}))
    respx.post("https://auth.openai.com/revoke").mock(return_value=httpx.Response(200))
    assert (await client.delete(f"/api/v1/model-providers/{provider_id}")).status_code == 204
    await session.close()
    start = await client.post("/api/v1/openai-codex/auth/start", json={})
    query = parse_qs(urlsplit(start.json()["authorization_url"]).query)
    assert query["client_id"] == ["oaiapp_test"]
    assert query["ext_agent_host_id"] == previous_query["ext_agent_host_id"]
    assert "id_token_hint" not in query
    assert "agent_name_hint" not in query
    assert await model_provider_repo.get_by_id(session, provider_id) is None


@pytest.mark.asyncio
@respx.mock
async def test_failed_code_exchange_retains_registration_for_retry(credential_runtime):
    client, session = credential_runtime
    start = await client.post("/api/v1/openai-codex/auth/start", json={})
    previous_query = parse_qs(urlsplit(start.json()["authorization_url"]).query)
    respx.post(OPENAI_CODEX_TOKEN_ENDPOINT).mock(return_value=httpx.Response(400, json={"error": "invalid_grant"}))
    state = previous_query["state"][0]
    response = await client.get("/api/v1/openai-codex/auth/callback", params={"state": state, "code": "expired-code", "client_id": "oaiapp_retry"})
    assert response.status_code == 400
    await session.close()
    retry = await client.post("/api/v1/openai-codex/auth/start", json={})
    query = parse_qs(urlsplit(retry.json()["authorization_url"]).query)
    assert query["client_id"] == ["oaiapp_retry"]
    assert query["state"] != previous_query["state"]
    assert query["code_challenge"] != previous_query["code_challenge"]
    assert await model_provider_repo.get_all(session) == []
    progress = await client.get(f"/api/v1/openai-codex/auth/status/{state}")
    assert progress.json()["registration_id"] == "oaiapp_retry"


@pytest.mark.asyncio
async def test_saved_registrations_are_selected_explicitly_without_email_merging(credential_runtime):
    client, session = credential_runtime
    store = OpenAICodexCredentialStore(EncryptionService(settings.encryption_key))
    for client_id in ("oaiapp_first", "oaiapp_second"):
        provider = await model_provider_repo.create(session, "Codex", OPENAI_CODEX_API_BASE_URL, "", OPENAI_CODEX_PROVIDER_TYPE)
        store.write(provider, replace(_credentials(), client_id=client_id))
    await session.commit()
    response = await client.get("/api/v1/openai-codex/registrations")
    assert response.status_code == 200
    assert {item["client_id"] for item in response.json()} == {"oaiapp_first", "oaiapp_second"}
    assert "access-token" not in response.text and "id-token" not in response.text
    assert (await client.post("/api/v1/openai-codex/auth/start", json={})).status_code == 409
    selected = await client.post("/api/v1/openai-codex/auth/start", json={"registration_id": "oaiapp_first"})
    assert parse_qs(urlsplit(selected.json()["authorization_url"]).query)["client_id"] == ["oaiapp_first"]
    fresh = await client.post("/api/v1/openai-codex/auth/start", json={"new_registration": True})
    assert parse_qs(urlsplit(fresh.json()["authorization_url"]).query)["client_id"] == ["dynamic_agent_client"]


@pytest.mark.asyncio
@pytest.mark.parametrize("returned_subject", ["subject", "different-subject"])
@respx.mock
async def test_deleted_registration_reauthorization_keeps_verified_identity(credential_runtime, monkeypatch, returned_subject):
    from app.models.repos import model_provider_oauth_registration_repo

    client, session = credential_runtime
    provider = await model_provider_repo.create(session, "Codex", OPENAI_CODEX_API_BASE_URL, "", OPENAI_CODEX_PROVIDER_TYPE)
    store = OpenAICodexCredentialStore(EncryptionService(settings.encryption_key))
    store.write(provider, _credentials())
    await session.commit()
    respx.get("https://auth.openai.com/.well-known/openid-configuration").mock(return_value=httpx.Response(200, json={"revocation_endpoint": "https://auth.openai.com/revoke"}))
    respx.post("https://auth.openai.com/revoke").mock(return_value=httpx.Response(200))
    assert (await client.delete(f"/api/v1/model-providers/{provider.id}")).status_code == 204

    async def verify_identity(*_args, **_kwargs):
        return {"sub": returned_subject, "email": "user@example.com"}

    monkeypatch.setattr("app.models.services.openai_codex_service.verify_openai_codex_id_token", verify_identity)
    respx.post(OPENAI_CODEX_TOKEN_ENDPOINT).mock(return_value=httpx.Response(200, json={
        "access_token": "new-access", "refresh_token": "new-refresh", "id_token": "new-id",
        "expires_in": 3600, "scope": "chatgpt.tokens.use.direct",
    }))
    start = await client.post("/api/v1/openai-codex/auth/start", json={})
    query = parse_qs(urlsplit(start.json()["authorization_url"]).query)
    response = await client.get("/api/v1/openai-codex/auth/callback", params={"state": query["state"][0], "code": "new-code"})
    assert response.status_code == (200 if returned_subject == "subject" else 400)
    providers = await model_provider_repo.get_all(session)
    assert len(providers) == (1 if returned_subject == "subject" else 0)
    registration = await model_provider_oauth_registration_repo.get_by_client_id(
        session, provider_type=OPENAI_CODEX_PROVIDER_TYPE, issuer="https://auth.openai.com", client_id="oaiapp_test",
    )
    assert registration.subject == "subject"
    assert not {"access_token", "refresh_token", "id_token"} & registration.model_dump().keys()
    if providers:
        assert registration.provider_id == providers[0].id
    else:
        assert registration.provider_id is None
