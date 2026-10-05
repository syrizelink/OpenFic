import asyncio
import base64
from contextlib import suppress
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from urllib.parse import parse_qs, urlsplit

import jwt
import pytest
import pytest_asyncio
import respx
from cryptography.hazmat.primitives.asymmetric import rsa
import httpx

from app.core.encryption import EncryptionService
from app.agent_runtime.model_config import without_api_key
from app.models.services.openai_codex_service import (
    OPENAI_CODEX_SCOPES,
    OPENAI_CODEX_PROVIDER_TYPE,
    OpenAICodexCredentialStore,
    OpenAICodexCredentials,
    OpenAICodexOAuthClient,
    build_authorization_url,
    decrypt_portable_credentials,
    encrypt_portable_credentials,
    get_openai_codex_host_id,
    verify_openai_codex_id_token,
    OpenAICodexOAuthError,
)
from app.models.entities.model_provider import ModelProvider


ENCRYPTION_KEY = "id-hEPdEELwlgep9FQhcYQtX7ow188l7WHwy65qOZGQ="


@pytest.fixture(autouse=True)
def isolate_oauth_lock_files(monkeypatch, tmp_path):
    monkeypatch.setattr("app.models.services.openai_codex_service.BACKEND_DATA_DIR", tmp_path)


def test_openai_codex_authorization_url_uses_loopback_and_dynamic_registration():
    url = build_authorization_url(
        client_id="dynamic_agent_client",
        redirect_uri="http://127.0.0.1:8000/api/v1/openai-codex/auth/callback",
        state="state-value",
        nonce="nonce-value",
        code_challenge="challenge-value",
        ext_agent_host_id="urn:uuid:11111111-1111-4111-8111-111111111111",
        agent_name_hint="OpenFic",
    )

    parsed = httpx.URL(url)
    params = dict(parsed.params.multi_items())

    assert parsed.host == "auth.openai.com"
    assert parsed.path == "/api/accounts/authorize"
    assert params["client_id"] == "dynamic_agent_client"
    assert params["agent_name_hint"] == "OpenFic"
    assert params["redirect_uri"].startswith("http://127.0.0.1:")
    assert "localhost" not in params["redirect_uri"]
    assert params["scope"] == " ".join(OPENAI_CODEX_SCOPES)
    assert params["resource"] == "https://api.openai.com/v1"
    assert params["code_challenge_method"] == "S256"


def test_openai_codex_reauthorization_keeps_issued_client_id():
    oauth = OpenAICodexOAuthClient()
    transaction = oauth.create_transaction(
        redirect_uri="http://127.0.0.1:8000/api/v1/openai-codex/auth/callback",
        ext_agent_host_id="urn:uuid:11111111-1111-4111-8111-111111111111",
        expected_client_id="oaiapp_issued",
    )
    params = parse_qs(urlsplit(oauth.authorization_url(transaction)).query)

    assert params["client_id"] == ["oaiapp_issued"]
    assert "agent_name_hint" not in params
    assert oauth.validate_callback_client_id(
        returned_client_id=None,
        expected_client_id="oaiapp_issued",
    ) == "oaiapp_issued"


def test_openai_codex_credentials_round_trip_without_exposing_plaintext():
    credentials = OpenAICodexCredentials(
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
        scopes=frozenset(OPENAI_CODEX_SCOPES),
    )
    encrypted = EncryptionService(ENCRYPTION_KEY).encrypt(credentials.to_json())

    assert "access-token" not in encrypted
    assert OpenAICodexCredentials.from_json(
        EncryptionService(ENCRYPTION_KEY).decrypt(encrypted)
    ) == credentials
    assert OPENAI_CODEX_PROVIDER_TYPE == "openai-codex"


def test_openai_codex_tokens_are_removed_from_checkpoint_config():
    persisted = without_api_key(
        {
            "provider_id": "provider-1",
            "api_key": "access-token",
            "access_token": "access-token",
            "refresh_token": "refresh-token",
            "id_token": "id-token",
            "credentials": {"access_token": "access-token"},
        }
    )

    assert persisted == {"provider_id": "provider-1"}


def test_openai_codex_portable_credentials_are_passphrase_protected():
    credentials = OpenAICodexCredentials(
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
        scopes=frozenset(OPENAI_CODEX_SCOPES),
    )

    portable = encrypt_portable_credentials(credentials, "correct horse")

    assert "access-token" not in portable
    assert decrypt_portable_credentials(portable, "correct horse") == credentials
    with pytest.raises(ValueError, match="凭据文件或口令无效"):
        decrypt_portable_credentials(portable, "wrong horse")


@pytest.mark.asyncio
async def test_openai_codex_refresh_is_serialized_and_uses_rotated_token(monkeypatch):
    expired = OpenAICodexCredentials(
        client_id="oaiapp_test",
        ext_agent_host_id="urn:uuid:11111111-1111-4111-8111-111111111111",
        issuer="https://auth.openai.com",
        subject="subject",
        email="user@example.com",
        id_token="id-token",
        access_token="expired-token",
        refresh_token="refresh-token",
        token_type="Bearer",
        expires_at=datetime.now(UTC) - timedelta(minutes=1),
        scopes=frozenset(OPENAI_CODEX_SCOPES),
    )
    provider = ModelProvider(
        id="provider-1",
        name="OpenAI Codex",
        url="https://api.openai.com/v1",
        api_key_encrypted="",
        provider_type=OPENAI_CODEX_PROVIDER_TYPE,
    )
    store = OpenAICodexCredentialStore(EncryptionService(ENCRYPTION_KEY))
    store.write(provider, expired)
    refresh_calls = 0

    class FakeSession:
        def get_bind(self):
            return SimpleNamespace(dialect=SimpleNamespace(name="test"))

        async def commit(self):
            return None

        async def rollback(self):
            return None

        async def close(self):
            return None

    async def get_provider(_session, _provider_id):
        return provider

    async def refresh(_credentials):
        nonlocal refresh_calls
        refresh_calls += 1
        await asyncio.sleep(0)
        return {
            "access_token": "rotated-access-token",
            "refresh_token": "rotated-refresh-token",
            "expires_in": 3600,
        }

    import app.models.services.openai_codex_service as openai_codex
    from app.models.repos import model_provider_repo

    monkeypatch.setattr(openai_codex, "create_session", lambda: _fake_session(FakeSession()))
    monkeypatch.setattr(model_provider_repo, "get_by_id", get_provider)
    monkeypatch.setattr(store, "_refresh_token", refresh)

    tokens = await asyncio.gather(
        store.get_access_token("provider-1"),
        store.get_access_token("provider-1"),
    )

    assert tokens == ["rotated-access-token", "rotated-access-token"]
    assert refresh_calls == 1
    assert store.read(provider).refresh_token == "rotated-refresh-token"


async def _fake_session(session):
    return session


@pytest_asyncio.fixture
async def oauth_database(monkeypatch, tmp_path):
    from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
    from sqlmodel import SQLModel
    from tests.model_registry import register_sqlmodel_models
    import app.models.services.openai_codex_service as plan

    register_sqlmodel_models()
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'oauth.db'}")
    async with engine.begin() as connection:
        await connection.run_sync(lambda conn: SQLModel.metadata.create_all(
            conn, tables=[SQLModel.metadata.tables[name] for name in (
                "model_providers", "model_provider_oauth_registrations",
            )],
        ))
    credentials = OpenAICodexCredentials(
        client_id="oaiapp_lock", ext_agent_host_id="host", issuer=plan.OPENAI_CODEX_ISSUER,
        subject="subject", email=None, id_token="id", access_token="expired",
        refresh_token="refresh", token_type="Bearer",
        expires_at=datetime.now(UTC) - timedelta(minutes=1), scopes=frozenset(OPENAI_CODEX_SCOPES),
    )
    store = OpenAICodexCredentialStore(EncryptionService(ENCRYPTION_KEY))
    provider = ModelProvider(id="lock-provider", name="Plan", url=plan.OPENAI_CODEX_API_BASE_URL,
                             provider_type=OPENAI_CODEX_PROVIDER_TYPE, api_key_encrypted="")
    store.write(provider, credentials)
    monkeypatch.setattr(plan, "BACKEND_DATA_DIR", tmp_path)
    try:
        async with AsyncSession(engine, expire_on_commit=False) as session:
            session.add(provider)
            await session.commit()
        yield engine, store, provider, credentials
    finally:
        await engine.dispose()


@pytest.mark.asyncio
@pytest.mark.parametrize("operation", ["refresh", "delete"])
async def test_oauth_network_does_not_hold_sqlite_write_lock(monkeypatch, oauth_database, operation):
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import AsyncSession

    engine, store, provider, _credentials = oauth_database

    async def network(_credentials):
        async with AsyncSession(engine) as other:
            await other.execute(text("PRAGMA busy_timeout=20"))
            await other.execute(text("BEGIN IMMEDIATE"))
            await other.rollback()
        if operation == "delete":
            return True
        return {"access_token": "fresh", "refresh_token": "rotated", "expires_in": 3600}

    monkeypatch.setattr(store, "_refresh_token", network)
    monkeypatch.setattr(store, "_revoke_refresh_token", network)
    async with AsyncSession(engine, expire_on_commit=False) as session:
        if operation == "refresh":
            await store._refresh_with_account_lock(session, provider.id)
        else:
            await store.revoke_and_delete(session, provider)


@pytest.mark.asyncio
@pytest.mark.parametrize("operation", ["refresh", "delete"])
async def test_oauth_rereads_rotation_from_another_process(monkeypatch, tmp_path, oauth_database, operation):
    from sqlalchemy.ext.asyncio import AsyncSession
    import app.models.services.openai_codex_service as plan

    engine, store, provider, credentials = oauth_database
    script = '''
import asyncio
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
import sys
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from app.core.encryption import EncryptionService
from app.models.repos import model_provider_repo
import app.models.services.openai_codex_service as plan

async def main():
    plan.BACKEND_DATA_DIR = Path(sys.argv[1])
    engine = create_async_engine(sys.argv[2])
    store = plan.OpenAICodexCredentialStore(EncryptionService(sys.argv[3]))
    try:
        async with plan.openai_codex_credential_lock("oaiapp_lock", "subject"):
            print("locked", flush=True)
            await asyncio.to_thread(sys.stdin.readline)
            async with AsyncSession(engine, expire_on_commit=False) as session:
                provider = await model_provider_repo.get_by_id(session, "lock-provider")
                credentials = store.read(provider)
                store.write(provider, replace(credentials, access_token="child-access",
                    refresh_token="child-rotated", expires_at=datetime.now(UTC) + timedelta(hours=1)))
                await session.commit()
    finally:
        await engine.dispose()

asyncio.run(main())
'''
    child = await asyncio.create_subprocess_exec(
        "uv", "run", "python", "-c", script, str(tmp_path), str(engine.url), ENCRYPTION_KEY,
        stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
    )
    task = None
    try:
        assert await asyncio.wait_for(child.stdout.readline(), 30) == b"locked\n"

        async def forbidden_refresh(_credentials):
            pytest.fail("must use the other process's committed replacement")

        monkeypatch.setattr(store, "_refresh_token", forbidden_refresh)

        async def revoke(latest):
            assert latest.refresh_token == "child-rotated"
            return True

        monkeypatch.setattr(store, "_revoke_refresh_token", revoke)
        async with AsyncSession(engine, expire_on_commit=False) as session:
            if operation == "refresh":
                task = asyncio.create_task(store._refresh_with_account_lock(session, provider.id))
            else:
                task = asyncio.create_task(store.revoke_and_delete(session, provider))
            await asyncio.sleep(0.1)
            assert not task.done()
            # A separate account must not queue behind this session.
            async with plan.openai_codex_credential_lock(credentials.client_id, "other-subject"):
                pass
            child.stdin.write(b"rotate\n")
            await child.stdin.drain()
            refreshed = await asyncio.wait_for(task, 30)
            if operation == "refresh":
                assert refreshed.access_token == "child-access"
                assert refreshed.refresh_token == "child-rotated"
            else:
                assert refreshed is True
        _stdout, stderr = await asyncio.wait_for(child.communicate(), 30)
        assert child.returncode == 0, stderr.decode()
    finally:
        if task is not None and not task.done():
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task
        if child.returncode is None:
            child.kill()
        await child.communicate()


@pytest.mark.asyncio
@pytest.mark.parametrize("cancel_waiter", [False, True])
async def test_credential_lock_cancellation_releases_file(monkeypatch, tmp_path, cancel_waiter):
    import app.models.services.openai_codex_service as plan

    monkeypatch.setattr(plan, "BACKEND_DATA_DIR", tmp_path)
    entered = asyncio.Event()
    release = asyncio.Event()

    async def hold():
        async with plan.openai_codex_credential_lock("client", "subject"):
            entered.set()
            await release.wait()

    holder = asyncio.create_task(hold())
    await entered.wait()
    waiter = asyncio.create_task(hold()) if cancel_waiter else holder
    try:
        await asyncio.sleep(0.1)
        waiter.cancel()
        with pytest.raises(asyncio.CancelledError):
            await waiter
    finally:
        release.set()
        await asyncio.gather(holder, waiter, return_exceptions=True)
    async with plan.openai_codex_credential_lock("client", "subject"):
        pass


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", ["cancel", "transient", "terminal", "missing-access"])
async def test_refresh_failure_cleans_up_lock_and_transaction(monkeypatch, oauth_database, failure):
    from sqlalchemy.ext.asyncio import AsyncSession
    from app.models.repos import model_provider_repo
    import app.models.services.openai_codex_service as plan

    engine, store, provider, credentials = oauth_database
    entered = asyncio.Event()

    async def fail(_credentials):
        entered.set()
        if failure == "cancel":
            await asyncio.Event().wait()
        if failure == "transient":
            raise OpenAICodexOAuthError("temporarily_unavailable")
        if failure == "terminal":
            raise OpenAICodexOAuthError("invalid_grant")
        return {}

    monkeypatch.setattr(store, "_refresh_token", fail)
    async with AsyncSession(engine, expire_on_commit=False) as session:
        task = asyncio.create_task(store._refresh_with_account_lock(session, provider.id))
        await entered.wait()
        if failure == "cancel":
            task.cancel()
            expected = asyncio.CancelledError
        else:
            expected = plan.OpenAICodexError
        with pytest.raises(expected):
            await task
        assert not session.in_transaction()
    async with plan.openai_codex_credential_lock(credentials.client_id, credentials.subject):
        async with AsyncSession(engine, expire_on_commit=False) as session:
            persisted = await model_provider_repo.get_by_id(session, provider.id)
            assert store.read(persisted) == (credentials.without_tokens() if failure == "terminal" else credentials)


@pytest.mark.parametrize("force_consent", [False, True])
def test_authorization_only_prompts_for_explicit_consent(force_consent):
    oauth = OpenAICodexOAuthClient()
    transaction = oauth.create_transaction(
        redirect_uri="http://127.0.0.1:8000/callback", ext_agent_host_id="host",
        force_consent=force_consent,
    )
    params = parse_qs(urlsplit(oauth.authorization_url(transaction)).query)
    assert params.get("prompt") == (["consent"] if force_consent else None)


def test_openai_codex_host_id_is_stable_uuid_v4(tmp_path):
    first = get_openai_codex_host_id(tmp_path)
    second = get_openai_codex_host_id(tmp_path)

    assert first == second
    assert first.startswith("urn:uuid:")
    assert first.removeprefix("urn:uuid:").count("-") == 4
    assert first.removeprefix("urn:uuid:")[14] == "4"


@pytest.mark.asyncio
@pytest.mark.parametrize("invalid_claim", [None, "nonce", "aud", "iss", "exp", "signature"])
@respx.mock
async def test_openai_codex_id_token_requires_openai_jwks_and_nonce(invalid_claim):
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public_numbers = key.public_key().public_numbers()
    jwk = {
        "kty": "RSA",
        "kid": f"test-key-{invalid_claim}",
        "use": "sig",
        "alg": "RS256",
        "n": base64.urlsafe_b64encode(
            public_numbers.n.to_bytes((public_numbers.n.bit_length() + 7) // 8, "big")
        ).rstrip(b"=").decode(),
        "e": base64.urlsafe_b64encode(
            public_numbers.e.to_bytes((public_numbers.e.bit_length() + 7) // 8, "big")
        ).rstrip(b"=").decode(),
    }
    respx.get("https://auth.openai.com/.well-known/jwks.json").mock(
        return_value=httpx.Response(200, json={"keys": [jwk]})
    )
    claims_payload = {
            "iss": "https://auth.openai.com",
            "aud": "oaiapp_test",
            "sub": "subject",
            "nonce": "nonce-value",
            "iat": datetime.now(UTC),
            "exp": datetime.now(UTC) + timedelta(minutes=5),
        }
    if invalid_claim in {"nonce", "aud", "iss"}:
        claims_payload[invalid_claim] = "wrong-value"
    elif invalid_claim == "exp":
        claims_payload["exp"] = datetime.now(UTC) - timedelta(minutes=5)
    token = jwt.encode(
        claims_payload,
        rsa.generate_private_key(public_exponent=65537, key_size=2048) if invalid_claim == "signature" else key,
        algorithm="RS256",
        headers={"kid": f"test-key-{invalid_claim}"},
    )

    if invalid_claim:
        with pytest.raises(OpenAICodexOAuthError):
            await verify_openai_codex_id_token(token, client_id="oaiapp_test", nonce="nonce-value")
        return
    claims = await verify_openai_codex_id_token(
        token,
        client_id="oaiapp_test",
        nonce="nonce-value",
    )

    assert claims["sub"] == "subject"


@pytest.mark.asyncio
async def test_openai_codex_oauth_client_rejects_changed_issued_client_id():
    client = OpenAICodexOAuthClient()

    with pytest.raises(ValueError, match="client ID"):
        client.validate_callback_client_id(
            returned_client_id="oaiapp_other",
            expected_client_id="oaiapp_original",
        )


@pytest.mark.asyncio
async def test_openai_codex_callback_scope_does_not_grant_plan_usage(monkeypatch):
    import app.models.services.openai_codex_service as openai_codex

    async def verified_token(*_args, **_kwargs):
        return {"sub": "subject"}

    monkeypatch.setattr(openai_codex, "verify_openai_codex_id_token", verified_token)
    credentials = await OpenAICodexOAuthClient().credentials_from_token_response(
        {"id_token": "id", "access_token": "access", "refresh_token": "refresh"},
        client_id="oaiapp_test",
        nonce="nonce",
        ext_agent_host_id="urn:uuid:11111111-1111-4111-8111-111111111111",
    )
    assert not credentials.openai_codex_access_enabled


@pytest.mark.asyncio
async def test_openai_codex_delete_waits_for_an_in_flight_refresh(monkeypatch):
    import app.models.services.openai_codex_service as plan

    credentials = OpenAICodexCredentials(
        client_id="oaiapp_test", ext_agent_host_id="urn:uuid:11111111-1111-4111-8111-111111111111",
        issuer=plan.OPENAI_CODEX_ISSUER, subject="subject", email=None, id_token="id",
        access_token="access", refresh_token="refresh", token_type="Bearer",
        expires_at=datetime.now(UTC) + timedelta(hours=1), scopes=frozenset(OPENAI_CODEX_SCOPES),
    )
    provider = ModelProvider(id="disconnect-refresh", name="Plan", url=plan.OPENAI_CODEX_API_BASE_URL,
                             provider_type=OPENAI_CODEX_PROVIDER_TYPE, api_key_encrypted="")
    store = OpenAICodexCredentialStore(EncryptionService(ENCRYPTION_KEY))
    store.write(provider, credentials)
    revoked = asyncio.Event()
    deleted = asyncio.Event()

    async def revoke(_credentials):
        revoked.set()
        return True

    async def get_provider(_session, _id):
        return provider

    async def delete_provider(_session, _id):
        deleted.set()
        return True

    async def save_registration(_session, _credentials, _provider_id):
        return None

    async def get_registration(_session, **_kwargs):
        return None

    class FakeSession:
        def get_bind(self):
            return SimpleNamespace(dialect=SimpleNamespace(name="test"))

        def add(self, _provider):
            pass

        async def commit(self):
            pass

        async def rollback(self):
            pass

    monkeypatch.setattr(store, "_revoke_refresh_token", revoke)
    monkeypatch.setattr("app.models.repos.model_provider_repo.get_by_id", get_provider)
    monkeypatch.setattr("app.models.repos.model_provider_repo.delete_by_id", delete_provider)
    monkeypatch.setattr("app.models.services.openai_codex_service.save_openai_codex_registration", save_registration)
    monkeypatch.setattr("app.models.repos.model_provider_oauth_registration_repo.get_for_provider", get_registration)
    lock = plan._REFRESH_LOCKS[provider.id]
    await lock.acquire()
    task = asyncio.create_task(store.revoke_and_delete(FakeSession(), provider))
    try:
        await asyncio.sleep(0)
        assert not revoked.is_set()
    finally:
        lock.release()
        await task
    assert revoked.is_set()
    assert deleted.is_set()
