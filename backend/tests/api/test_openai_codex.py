import asyncio
import shutil
from dataclasses import replace
from datetime import UTC, datetime, timedelta
import base64
from unittest.mock import patch
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
    OpenAICodexOAuthClient,
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
async def credential_runtime(tmp_path, credential_database_template, monkeypatch):
    from app.api.routers.openai_codex import router
    from app.api.routers.model_providers import router as provider_router

    monkeypatch.setattr("app.api.routers.openai_codex._PENDING_TRANSACTIONS_LOCK", asyncio.Lock())

    path = tmp_path / "credentials.db"
    shutil.copyfile(credential_database_template, path)
    engine = create_async_engine(f"sqlite+aiosqlite:///{path}")
    try:
        async with AsyncSession(engine, expire_on_commit=False) as session:
            async def runtime_session():
                async with AsyncSession(engine, expire_on_commit=False) as request_session:
                    yield request_session

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
    assert "prompt" not in parse_qs(urlsplit(payload["authorization_url"]).query)
    progress = await client.get(f"/api/v1/openai-codex/auth/status/{payload['authorization_id']}")
    assert progress.json()["status"] == "pending"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("environment_port", "arguments", "expected_port"),
    [
        ("49152", ["uvicorn", "--port", "8001"], 49152),
        (None, ["uvicorn", "--port", "8001"], 8001),
        (None, ["uvicorn", "--port=8002"], 8002),
        (None, ["uvicorn"], 8000),
    ],
)
async def test_auth_start_uses_server_binding_port(
    credential_runtime, monkeypatch, environment_port, arguments, expected_port,
):
    client, _session = credential_runtime
    monkeypatch.setattr(settings, "port", 8000)
    monkeypatch.setattr("sys.argv", arguments)
    if environment_port is None:
        monkeypatch.delenv("OPENFIC_SERVER_PORT", raising=False)
    else:
        monkeypatch.setenv("OPENFIC_SERVER_PORT", environment_port)

    response = await client.post("/api/v1/openai-codex/auth/start", json={})

    assert response.status_code == 200
    query = parse_qs(urlsplit(response.json()["authorization_url"]).query)
    assert query["redirect_uri"] == [
        f"http://127.0.0.1:{expected_port}/api/v1/openai-codex/auth/callback"
    ]


@pytest.mark.asyncio
@pytest.mark.parametrize("selection", ["provider", "registration", "automatic"])
@pytest.mark.parametrize("has_scope", [False, True])
async def test_reauthorization_requests_consent_only_for_missing_scope(
    credential_runtime, selection, has_scope,
):
    client, session = credential_runtime
    provider = await model_provider_repo.create(
        session, "Codex", OPENAI_CODEX_API_BASE_URL, "", OPENAI_CODEX_PROVIDER_TYPE,
    )
    credentials = _credentials()
    if not has_scope:
        credentials = replace(credentials, scopes=frozenset({"openid"}))
    OpenAICodexCredentialStore(EncryptionService(settings.encryption_key)).write(provider, credentials)
    await session.commit()
    request = {}
    if selection == "provider":
        request["provider_id"] = provider.id
    elif selection == "registration":
        request["registration_id"] = credentials.client_id

    with patch.object(
        OpenAICodexOAuthClient, "create_transaction",
        wraps=OpenAICodexOAuthClient().create_transaction,
    ) as create:
        response = await client.post("/api/v1/openai-codex/auth/start", json=request)

    assert response.status_code == 200
    assert create.call_args.kwargs.get("force_consent") is (not has_scope)
    query = parse_qs(urlsplit(response.json()["authorization_url"]).query)
    assert query["client_id"] == [credentials.client_id]
    assert "chatgpt.tokens.use.direct" in query["scope"][0].split()
    assert query.get("prompt") == (None if has_scope else ["consent"])


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
    cancelled = await client.delete(f"/api/v1/openai-codex/auth/{state}")
    assert cancelled.status_code == 200
    assert cancelled.json() == progress.json()
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
                store._refresh_with_account_lock(first, provider_id),
                store._refresh_with_account_lock(second, provider_id),
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


@pytest.mark.asyncio
@pytest.mark.parametrize("credential_state", ["orphan", "corrupt", "disconnected", "revoke-failed", "revoked"])
@respx.mock
async def test_forget_registration_removes_local_account(credential_runtime, credential_state):
    from app.models.repos import model_provider_oauth_registration_repo as registrations

    client, session = credential_runtime
    provider_id = None
    if credential_state != "orphan":
        provider = await model_provider_repo.create(session, "Codex", OPENAI_CODEX_API_BASE_URL, "", OPENAI_CODEX_PROVIDER_TYPE)
        provider_id = provider.id
        store = OpenAICodexCredentialStore(EncryptionService(settings.encryption_key))
        if credential_state == "corrupt":
            provider.credentials_encrypted = "invalid-ciphertext"
        else:
            store.write(provider, _credentials().without_tokens() if credential_state == "disconnected" else _credentials())
        await registrations.save_verified(session, provider_type=OPENAI_CODEX_PROVIDER_TYPE, issuer="https://auth.openai.com", client_id="oaiapp_test", subject="subject", email=None, provider_id=provider_id)
    else:
        await registrations.save_issued(session, provider_type=OPENAI_CODEX_PROVIDER_TYPE, issuer="https://auth.openai.com", client_id="oaiapp_test")
    await session.commit()
    start = await client.post("/api/v1/openai-codex/auth/start", json={"registration_id": "oaiapp_test"})
    state = start.json()["authorization_id"]
    if credential_state in {"revoke-failed", "revoked"}:
        respx.get("https://auth.openai.com/.well-known/openid-configuration").mock(return_value=httpx.Response(200, json={"revocation_endpoint": "https://auth.openai.com/revoke"}))
        respx.post("https://auth.openai.com/revoke").mock(return_value=httpx.Response(400 if credential_state == "revoke-failed" else 200))
    response = await client.delete("/api/v1/openai-codex/registrations/oaiapp_test")
    assert response.status_code == 204
    assert response.content == b""
    assert response.headers["X-OAuth-Revocation-Confirmed"] == str(credential_state in {"disconnected", "revoked"}).lower()
    assert (await client.get("/api/v1/openai-codex/registrations")).json() == []
    if provider_id:
        assert await model_provider_repo.get_by_id(session, provider_id) is None
    assert (await client.get(f"/api/v1/openai-codex/auth/status/{state}")).json()["status"] == "cancelled"
    assert (await client.get("/api/v1/openai-codex/auth/callback", params={"state": state, "code": "late"})).status_code == 400
    assert (await client.delete("/api/v1/openai-codex/registrations/oaiapp_test")).status_code == 204


@pytest.mark.asyncio
@respx.mock
async def test_interrupted_forgetting_clears_deleting_marker(credential_runtime):
    client, session = credential_runtime
    store = OpenAICodexCredentialStore(EncryptionService(settings.encryption_key))
    provider = await model_provider_repo.create(session, "Target", OPENAI_CODEX_API_BASE_URL, "", OPENAI_CODEX_PROVIDER_TYPE)
    store.write(provider, _credentials())
    await session.commit()
    start = await client.post("/api/v1/openai-codex/auth/start", json={"provider_id": provider.id})
    state = start.json()["authorization_id"]
    revoking = asyncio.Event()
    release = asyncio.Event()

    async def revoke(_request):
        revoking.set()
        await release.wait()
        return httpx.Response(200)

    respx.get("https://auth.openai.com/.well-known/openid-configuration").mock(return_value=httpx.Response(200, json={"revocation_endpoint": "https://auth.openai.com/revoke"}))
    respx.post("https://auth.openai.com/revoke").mock(side_effect=revoke)
    deleting = asyncio.create_task(client.delete("/api/v1/openai-codex/registrations/oaiapp_test"))
    try:
        await asyncio.wait_for(revoking.wait(), timeout=5)
        deleting.cancel()
        with pytest.raises(asyncio.CancelledError):
            await deleting
    finally:
        release.set()
        if not deleting.done():
            await deleting
    retry = await client.post("/api/v1/openai-codex/auth/start", json={"registration_id": "oaiapp_test"})
    assert retry.status_code == 200
    assert (await client.get(f"/api/v1/openai-codex/auth/status/{state}")).json()["status"] == "cancelled"
    assert (await client.delete("/api/v1/openai-codex/registrations/oaiapp_test")).status_code == 204


@pytest.mark.asyncio
@respx.mock
async def test_cancel_pending_is_idempotent_and_rejects_late_callbacks(credential_runtime, monkeypatch):
    client, session = credential_runtime
    start = await client.post("/api/v1/openai-codex/auth/start", json={})
    state = start.json()["authorization_id"]

    async def locked(_session):
        return True

    monkeypatch.setattr("app.api.agent_settings_lock.has_active_agent_sessions", locked)
    for _ in range(2):
        response = await client.delete(f"/api/v1/openai-codex/auth/{state}")
        assert response.status_code == 200
        assert response.json()["status"] == "cancelled"
    callback = await client.get("/api/v1/openai-codex/auth/callback", params={"state": state, "code": "late", "client_id": "oaiapp_test"})
    assert callback.status_code == 400
    assert await model_provider_repo.get_all(session) == []
    assert (await client.get(f"/api/v1/openai-codex/auth/status/{state}")).json()["status"] == "cancelled"
    assert (await client.delete("/api/v1/openai-codex/auth/unknown")).json()["status"] == "expired"


@pytest.mark.asyncio
async def test_forget_registration_respects_settings_lock(credential_runtime, monkeypatch):
    from app.models.repos import model_provider_oauth_registration_repo as registrations

    client, session = credential_runtime
    await registrations.save_issued(session, provider_type=OPENAI_CODEX_PROVIDER_TYPE, issuer="https://auth.openai.com", client_id="oaiapp_test")
    await session.commit()

    async def locked(_session):
        return True

    monkeypatch.setattr("app.api.agent_settings_lock.has_active_agent_sessions", locked)
    response = await client.delete("/api/v1/openai-codex/registrations/oaiapp_test")
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "agent_settings_locked"
    assert await registrations.get_by_client_id(session, provider_type=OPENAI_CODEX_PROVIDER_TYPE, issuer="https://auth.openai.com", client_id="oaiapp_test") is not None


@pytest.mark.asyncio
@pytest.mark.parametrize("action", ["cancel", "forget"])
@pytest.mark.parametrize("exchange_fails", [False, True])
@respx.mock
async def test_cancel_during_token_exchange_prevents_provider_commit(credential_runtime, monkeypatch, action, exchange_fails):
    client, session = credential_runtime
    started = asyncio.Event()
    release = asyncio.Event()

    async def exchange(_request):
        started.set()
        await release.wait()
        return httpx.Response(400 if exchange_fails else 200, json={"access_token": "access", "refresh_token": "refresh", "id_token": "id", "scope": "chatgpt.tokens.use.direct"})

    async def verify(*_args, **_kwargs):
        return {"sub": "subject"}

    monkeypatch.setattr("app.models.services.openai_codex_service.verify_openai_codex_id_token", verify)
    respx.post(OPENAI_CODEX_TOKEN_ENDPOINT).mock(side_effect=exchange)
    start = await client.post("/api/v1/openai-codex/auth/start", json={})
    state = start.json()["authorization_id"]
    callback = asyncio.create_task(client.get("/api/v1/openai-codex/auth/callback", params={"state": state, "code": "code", "client_id": "oaiapp_test"}))
    try:
        await asyncio.wait_for(started.wait(), timeout=5)
        path = f"auth/{state}" if action == "cancel" else "registrations/oaiapp_test"
        response = await client.delete(f"/api/v1/openai-codex/{path}")
        assert response.status_code == (200 if action == "cancel" else 204)
    finally:
        release.set()
        completed = await callback
    assert completed.status_code == 400
    assert await model_provider_repo.get_all(session) == []
    assert (await client.get(f"/api/v1/openai-codex/auth/status/{state}")).json()["status"] == "cancelled"
    if action == "forget":
        assert (await client.get("/api/v1/openai-codex/registrations")).json() == []


@pytest.mark.asyncio
@pytest.mark.parametrize("path", ["auth/unknown", "registrations/oaiapp_test"])
async def test_oauth_delete_endpoints_require_authentication(path):
    from app.api.routers.openai_codex import router
    from app.auth import AuthMiddleware, AuthService

    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    app.add_middleware(AuthMiddleware, auth_service=AuthService("password"), api_prefix="/api/v1")
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        assert (await client.delete(f"/api/v1/openai-codex/{path}")).status_code == 401


@pytest.mark.asyncio
@respx.mock
async def test_cancel_waits_for_final_commit_and_keeps_success(credential_runtime, monkeypatch):
    client, session = credential_runtime
    committing = asyncio.Event()
    release = asyncio.Event()
    original_commit = AsyncSession.commit
    callback = None
    callback_commits = 0

    async def controlled_commit(current):
        nonlocal callback_commits
        if asyncio.current_task() is callback:
            callback_commits += 1
            if callback_commits == 2:
                committing.set()
                await release.wait()
        await original_commit(current)

    async def verify(*_args, **_kwargs):
        return {"sub": "subject"}

    monkeypatch.setattr(AsyncSession, "commit", controlled_commit)
    monkeypatch.setattr("app.models.services.openai_codex_service.verify_openai_codex_id_token", verify)
    respx.post(OPENAI_CODEX_TOKEN_ENDPOINT).mock(return_value=httpx.Response(200, json={
        "access_token": "access", "refresh_token": "refresh", "id_token": "id", "scope": "chatgpt.tokens.use.direct",
    }))
    start = await client.post("/api/v1/openai-codex/auth/start", json={})
    state = start.json()["authorization_id"]
    callback = asyncio.create_task(client.get("/api/v1/openai-codex/auth/callback", params={"state": state, "code": "code", "client_id": "oaiapp_test"}))
    cancellation = None
    try:
        await asyncio.wait_for(committing.wait(), timeout=5)
        cancellation = asyncio.create_task(client.delete(f"/api/v1/openai-codex/auth/{state}"))
        await asyncio.sleep(0)
        assert not cancellation.done()
    finally:
        release.set()
        completed = await callback
        cancelled = await cancellation if cancellation else None
    assert completed.status_code == 200
    assert cancelled is not None and cancelled.status_code == 200
    assert cancelled.json()["status"] == "success"
    providers = await model_provider_repo.get_all(session)
    assert len(providers) == 1
    assert cancelled.json()["provider_id"] == providers[0].id


@pytest.mark.asyncio
@pytest.mark.parametrize("wait_at", ["revoke", "account-lock"])
@respx.mock
async def test_forgetting_account_does_not_block_other_authorizations(credential_runtime, monkeypatch, wait_at):
    from contextlib import asynccontextmanager
    from app.models.services import openai_codex_service

    client, session = credential_runtime
    store = OpenAICodexCredentialStore(EncryptionService(settings.encryption_key))
    target = await model_provider_repo.create(session, "Target", OPENAI_CODEX_API_BASE_URL, "", OPENAI_CODEX_PROVIDER_TYPE)
    store.write(target, _credentials())
    other = await model_provider_repo.create(session, "Other", OPENAI_CODEX_API_BASE_URL, "", OPENAI_CODEX_PROVIDER_TYPE)
    store.write(other, replace(_credentials(), client_id="oaiapp_other"))
    await session.commit()
    target_id = target.id
    before = await client.post("/api/v1/openai-codex/auth/start", json={"registration_id": "oaiapp_test"})
    target_state = before.json()["authorization_id"]
    other_start = await client.post("/api/v1/openai-codex/auth/start", json={"registration_id": "oaiapp_other"})
    other_state = other_start.json()["authorization_id"]
    fresh = await client.post("/api/v1/openai-codex/auth/start", json={"new_registration": True})
    fresh_state = fresh.json()["authorization_id"]
    waiting = asyncio.Event()
    release = asyncio.Event()
    original_lock = openai_codex_service.openai_codex_credential_lock

    @asynccontextmanager
    async def controlled_lock(client_id, subject):
        async with original_lock(client_id, subject):
            if client_id == "oaiapp_test":
                waiting.set()
                await release.wait()
            yield

    async def revoke(_request):
        if wait_at == "revoke":
            waiting.set()
            await release.wait()
        return httpx.Response(200)

    if wait_at == "account-lock":
        monkeypatch.setattr(openai_codex_service, "openai_codex_credential_lock", controlled_lock)
    respx.get("https://auth.openai.com/.well-known/openid-configuration").mock(return_value=httpx.Response(200, json={"revocation_endpoint": "https://auth.openai.com/revoke"}))
    respx.post("https://auth.openai.com/revoke").mock(side_effect=revoke)
    deleting = asyncio.create_task(client.delete("/api/v1/openai-codex/registrations/oaiapp_test"))
    try:
        await asyncio.wait_for(waiting.wait(), timeout=5)
        progress = await asyncio.wait_for(client.get(f"/api/v1/openai-codex/auth/status/{other_state}"), timeout=1)
        assert progress.json()["status"] == "pending"
        cancellation = await asyncio.wait_for(client.delete(f"/api/v1/openai-codex/auth/{other_state}"), timeout=1)
        assert cancellation.json()["status"] == "cancelled"
        start = await asyncio.wait_for(client.post("/api/v1/openai-codex/auth/start", json={"registration_id": "oaiapp_other"}), timeout=1)
        assert start.status_code == 200
        for selection in ({"registration_id": "oaiapp_test"}, {"provider_id": target_id}):
            rejected = await asyncio.wait_for(client.post("/api/v1/openai-codex/auth/start", json=selection), timeout=1)
            assert rejected.status_code == 409
        duplicate = await asyncio.wait_for(client.delete("/api/v1/openai-codex/registrations/oaiapp_test"), timeout=1)
        assert duplicate.status_code == 409
        callback = await asyncio.wait_for(client.get("/api/v1/openai-codex/auth/callback", params={"state": fresh_state, "code": "late", "client_id": "oaiapp_test"}), timeout=1)
        assert callback.status_code == 400
        assert (await client.get(f"/api/v1/openai-codex/auth/status/{fresh_state}")).json()["status"] == "cancelled"
        assert (await client.get(f"/api/v1/openai-codex/auth/status/{target_state}")).json()["status"] == "cancelled"
    finally:
        release.set()
        response = await deleting
    assert response.status_code == 204
    assert [item["client_id"] for item in (await client.get("/api/v1/openai-codex/registrations")).json()] == ["oaiapp_other"]


@pytest.mark.asyncio
@pytest.mark.parametrize("failed_token", [None, "refresh-first", "refresh-second"])
@respx.mock
async def test_forget_registration_removes_all_matching_providers(credential_runtime, failed_token):
    client, session = credential_runtime
    store = OpenAICodexCredentialStore(EncryptionService(settings.encryption_key))
    target_ids = []
    for token in ("refresh-first", "refresh-second"):
        provider = await model_provider_repo.create(session, token, OPENAI_CODEX_API_BASE_URL, "", OPENAI_CODEX_PROVIDER_TYPE)
        store.write(provider, replace(_credentials(), refresh_token=token))
        target_ids.append(provider.id)
    other = await model_provider_repo.create(session, "Other", OPENAI_CODEX_API_BASE_URL, "", OPENAI_CODEX_PROVIDER_TYPE)
    store.write(other, replace(_credentials(), client_id="oaiapp_other"))
    other_id = other.id
    await session.commit()
    assert len((await client.get("/api/v1/openai-codex/registrations")).json()) == 2
    respx.get("https://auth.openai.com/.well-known/openid-configuration").mock(return_value=httpx.Response(200, json={"revocation_endpoint": "https://auth.openai.com/revoke"}))

    async def revoke(request):
        token = parse_qs(request.content.decode())["token"][0]
        return httpx.Response(400 if token == failed_token else 200)

    revocation = respx.post("https://auth.openai.com/revoke").mock(side_effect=revoke)
    response = await client.delete("/api/v1/openai-codex/registrations/oaiapp_test")
    assert response.status_code == 204
    assert response.headers["X-OAuth-Revocation-Confirmed"] == str(failed_token is None).lower()
    assert revocation.call_count == 2
    assert {parse_qs(call.request.content.decode())["token"][0] for call in revocation.calls} == {"refresh-first", "refresh-second"}
    for provider_id in target_ids:
        assert await model_provider_repo.get_by_id(session, provider_id) is None
    assert await model_provider_repo.get_by_id(session, other_id) is not None
    for _ in range(2):
        registrations = (await client.get("/api/v1/openai-codex/registrations")).json()
        assert [item["client_id"] for item in registrations] == ["oaiapp_other"]


@pytest.mark.asyncio
@respx.mock
async def test_listing_during_deletion_does_not_restore_registration(credential_runtime, monkeypatch):
    client, session = credential_runtime
    store = OpenAICodexCredentialStore(EncryptionService(settings.encryption_key))
    provider = await model_provider_repo.create(session, "Target", OPENAI_CODEX_API_BASE_URL, "", OPENAI_CODEX_PROVIDER_TYPE)
    store.write(provider, _credentials())
    await session.commit()
    await client.get("/api/v1/openai-codex/registrations")
    revoking = asyncio.Event()
    release_revocation = asyncio.Event()
    listing_loaded = asyncio.Event()
    release_listing = asyncio.Event()
    locally_deleted = asyncio.Event()
    original_get_all = model_provider_repo.get_all
    original_forget = OpenAICodexCredentialStore.forget_registration
    listing = None

    async def controlled_get_all(current):
        providers = await original_get_all(current)
        if asyncio.current_task() is listing:
            listing_loaded.set()
            await release_listing.wait()
        return providers

    async def controlled_forget(current_store, current, client_id):
        confirmed = await original_forget(current_store, current, client_id)
        locally_deleted.set()
        return confirmed

    async def revoke(_request):
        revoking.set()
        await release_revocation.wait()
        return httpx.Response(200)

    monkeypatch.setattr(model_provider_repo, "get_all", controlled_get_all)
    monkeypatch.setattr(OpenAICodexCredentialStore, "forget_registration", controlled_forget)
    respx.get("https://auth.openai.com/.well-known/openid-configuration").mock(return_value=httpx.Response(200, json={"revocation_endpoint": "https://auth.openai.com/revoke"}))
    respx.post("https://auth.openai.com/revoke").mock(side_effect=revoke)
    deleting = asyncio.create_task(client.delete("/api/v1/openai-codex/registrations/oaiapp_test"))
    try:
        await asyncio.wait_for(revoking.wait(), timeout=5)
        listing = asyncio.create_task(client.get("/api/v1/openai-codex/registrations"))
        await asyncio.wait_for(listing_loaded.wait(), timeout=5)
        release_revocation.set()
        await asyncio.wait_for(locally_deleted.wait(), timeout=5)
    finally:
        release_revocation.set()
        release_listing.set()
        if listing is not None:
            await listing
        await deleting
    assert (await client.get("/api/v1/openai-codex/registrations")).json() == []
