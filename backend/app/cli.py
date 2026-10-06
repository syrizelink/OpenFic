"""OpenFic CLI 入口。

用于以 pipx/uvx 安装后启动本地服务。
桌面端与 Docker 均通过此入口启动后端服务。
"""

from __future__ import annotations

import argparse
import asyncio
from dataclasses import replace
from getpass import getpass
import os
from pathlib import Path
import sys
from urllib.parse import parse_qs, urlsplit
import webbrowser

from app.logging import configure_standard_logging

_DEFAULT_HOST = "127.0.0.1"
_DEFAULT_PORT = 8000


def _windows_selector_loop_factory() -> asyncio.AbstractEventLoop:
    return asyncio.SelectorEventLoop()


def _get_uvicorn_loop_factory() -> str:
    """Use a selector loop on Windows because pyzmq requires add_reader."""
    if sys.platform == "win32":
        return "app.cli:_windows_selector_loop_factory"
    return "auto"


def _ensure_data_dir() -> None:
    """CLI 默认数据目录为 ~/.openfic，仅在未显式设置时生效。"""
    if os.getenv("OPENFIC_DATA_DIR"):
        return
    data_dir = Path.home() / ".openfic"
    data_dir.mkdir(parents=True, exist_ok=True)
    os.environ["OPENFIC_DATA_DIR"] = str(data_dir)


def _read_version() -> str:
    try:
        from importlib.metadata import PackageNotFoundError, version

        return version("openfic")
    except (PackageNotFoundError, Exception):
        return "0.0.0"


def handle_version(_args: argparse.Namespace) -> None:
    print(f"openfic {_read_version()}")


def handle_serve(args: argparse.Namespace) -> None:
    _ensure_data_dir()
    configure_standard_logging()
    os.environ["OPENFIC_SERVER_HOST"] = args.host
    os.environ["OPENFIC_SERVER_PORT"] = str(args.port)
    auth_password = getattr(args, "auth_password", None)
    if auth_password is not None:
        os.environ["OPENFIC_AUTH_PASSWORD"] = auth_password

    import uvicorn
    from app.main import app as asgi_app, fastapi_app

    config = uvicorn.Config(
        asgi_app,
        host=args.host,
        port=args.port,
        loop=_get_uvicorn_loop_factory(),
        log_level="info",
        log_config=None,
        access_log=False,
    )
    server = uvicorn.Server(config)
    fastapi_app.state.uvicorn_server = server
    server.run()


def _write_private_file(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temporary_path.write_text(content, encoding="utf-8")
    temporary_path.chmod(0o600)
    temporary_path.replace(path)
    path.chmod(0o600)


def handle_openai_codex_auth(args: argparse.Namespace) -> None:
    _ensure_data_dir()

    async def authorize() -> Path:
        from app.models.services.openai_codex_service import (
            OPENAI_CODEX_CALLBACK_PATH,
            OPENAI_CODEX_DYNAMIC_CLIENT_ID,
            OPENAI_CODEX_ISSUER,
            OPENAI_CODEX_PROVIDER_TYPE,
            OpenAICodexOAuthClient,
            decrypt_portable_credentials,
            encrypt_portable_credentials,
            get_openai_codex_host_id,
            OpenAICodexCredentialStore,
            openai_codex_credential_lock,
            save_openai_codex_registration,
        )
        from app.core.encryption import EncryptionService
        from app.models.repos import model_provider_oauth_registration_repo, model_provider_repo
        from app.settings import settings
        from app.storage.database import create_session

        data_dir = Path(os.environ["OPENFIC_DATA_DIR"])
        source_path = Path(args.input).expanduser() if args.input else None
        output_path = Path(args.output or source_path or data_dir / "openai-codex-credential.ofc").expanduser()
        if args.new_account and source_path:
            raise RuntimeError("--new-account 不能与 --input 同时使用")
        if source_path is None and output_path.exists() and not args.new_account:
            source_path = output_path
        passphrase = getpass("输入转移文件口令（不会显示）：")
        if not passphrase:
            raise RuntimeError("转移文件口令不能为空")
        previous = (
            decrypt_portable_credentials(source_path.read_text(encoding="utf-8"), passphrase)
            if source_path else None
        )
        session = await create_session()
        known_credentials = previous
        try:
            registrations = await OpenAICodexCredentialStore(EncryptionService(settings.encryption_key)).list_registrations(session)
            registration = None
            if previous:
                registration = await model_provider_oauth_registration_repo.get_by_client_id(
                    session, provider_type=OPENAI_CODEX_PROVIDER_TYPE, issuer=OPENAI_CODEX_ISSUER, client_id=previous.client_id,
                )
                registration = await save_openai_codex_registration(session, previous, registration.provider_id if registration else None)
                await session.commit()
            elif not args.new_account:
                if len(registrations) > 1:
                    raise RuntimeError("存在多个 OAuth 注册，请用 --input 选择已有凭据，或用 --new-account 明确添加新账户")
                registration = registrations[0] if registrations else None
                if registration and registration.provider_id:
                    provider = await model_provider_repo.get_by_id(session, registration.provider_id)
                    if provider is not None:
                        known_credentials = OpenAICodexCredentialStore(
                            EncryptionService(settings.encryption_key),
                        ).read(provider)
        finally:
            await session.close()
        oauth = OpenAICodexOAuthClient()
        callback_result: asyncio.Future[dict[str, str]] = asyncio.get_running_loop().create_future()
        handlers: set[asyncio.Task] = set()

        async def callback_handler(
            reader: asyncio.StreamReader,
            writer: asyncio.StreamWriter,
        ) -> None:
            task = asyncio.current_task()
            if task is not None:
                handlers.add(task)
            try:
                request_line = await asyncio.wait_for(reader.readline(), timeout=10)
                parts = request_line.decode("utf-8", errors="replace").split(" ")
                if len(parts) != 3 or parts[0] != "GET":
                    return
                parsed = urlsplit(parts[1])
                query = {
                    key: values[-1]
                    for key, values in parse_qs(parsed.query, keep_blank_values=True).items()
                }
                is_valid = (
                    parsed.path == OPENAI_CODEX_CALLBACK_PATH
                    and query.get("state") == transaction.state
                    and not callback_result.done()
                )
                if is_valid:
                    callback_result.set_result(query)
                status = b"200 OK" if is_valid else b"400 Bad Request"
                writer.write(
                    b"HTTP/1.1 " + status + b"\r\nContent-Type: text/html; charset=utf-8\r\n"
                    b"Connection: close\r\nCache-Control: no-store\r\nReferrer-Policy: no-referrer\r\n\r\n"
                    b"<p>Return to OpenFic to check authorization status.</p>"
                )
                await writer.drain()
            except (TimeoutError, ConnectionError, ValueError):
                pass
            finally:
                writer.close()
                try:
                    await writer.wait_closed()
                except ConnectionError:
                    pass
                if task is not None:
                    handlers.discard(task)

        server = await asyncio.start_server(callback_handler, "127.0.0.1", 0)
        port = server.sockets[0].getsockname()[1]
        transaction = oauth.create_transaction(
            redirect_uri=f"http://127.0.0.1:{port}{OPENAI_CODEX_CALLBACK_PATH}",
            ext_agent_host_id=get_openai_codex_host_id(data_dir),
            expected_client_id=registration.client_id if registration else OPENAI_CODEX_DYNAMIC_CLIENT_ID,
            id_token_hint=known_credentials.id_token if known_credentials else None,
            login_hint=registration.email if registration else None,
            expected_subject=registration.subject if registration else None,
            force_consent=bool(known_credentials and not known_credentials.openai_codex_access_enabled),
        )
        try:
            webbrowser.open(oauth.authorization_url(transaction))
            result = await asyncio.wait_for(callback_result, timeout=600)
            if result.get("state") != transaction.state:
                raise RuntimeError("OAuth state 校验失败")
            if result.get("error"):
                raise RuntimeError("OpenAI Codex 授权被取消或拒绝")
            issued_client_id = oauth.validate_callback_client_id(
                returned_client_id=result.get("client_id"),
                expected_client_id=transaction.expected_client_id,
            )
            session = await create_session()
            try:
                await model_provider_oauth_registration_repo.save_issued(
                    session, provider_type=OPENAI_CODEX_PROVIDER_TYPE, issuer=OPENAI_CODEX_ISSUER, client_id=issued_client_id,
                )
                await session.commit()
            finally:
                await session.close()
            token_payload = await oauth.exchange_code(
                code=result.get("code", ""),
                client_id=issued_client_id,
                code_verifier=transaction.code_verifier,
                redirect_uri=transaction.redirect_uri,
            )
            credentials = await oauth.credentials_from_token_response(
                token_payload,
                client_id=issued_client_id,
                nonce=transaction.nonce,
                ext_agent_host_id=transaction.ext_agent_host_id,
            )
            if transaction.expected_subject and credentials.subject != transaction.expected_subject:
                raise RuntimeError("重新授权返回了不同的 OpenAI Codex 账户")
            if not credentials.openai_codex_access_enabled:
                raise RuntimeError("账户未授予 OpenAI Codex 直接访问权限")
            session = await create_session()
            try:
                async with openai_codex_credential_lock(credentials.client_id, credentials.subject):
                    retained = await model_provider_oauth_registration_repo.get_by_client_id(
                        session, provider_type=OPENAI_CODEX_PROVIDER_TYPE, issuer=OPENAI_CODEX_ISSUER, client_id=credentials.client_id,
                    )
                    if retained and retained.provider_id:
                        provider = await model_provider_repo.get_by_id(session, retained.provider_id)
                        if provider is not None:
                            OpenAICodexCredentialStore(EncryptionService(settings.encryption_key)).write(provider, credentials)
                            session.add(provider)
                    await save_openai_codex_registration(session, credentials, retained.provider_id if retained else None)
                    await session.commit()
            finally:
                await session.close()
            _write_private_file(
                output_path,
                encrypt_portable_credentials(credentials, passphrase),
            )
            return output_path
        finally:
            server.close()
            await server.wait_closed()
            remaining = list(handlers)
            for task in remaining:
                task.cancel()
            await asyncio.gather(*remaining, return_exceptions=True)

    async def run_authorize() -> Path:
        from app.storage.database import close_db, init_db

        await init_db()
        try:
            return await authorize()
        finally:
            await close_db()

    output_path = asyncio.run(run_authorize())
    print(f"OpenAI Codex 凭据已加密写入: {output_path}")


def handle_openai_codex_import(args: argparse.Namespace) -> None:
    _ensure_data_dir()
    from app.models.services.openai_codex_service import (
        OpenAICodexCredentialStore,
        OPENAI_CODEX_API_BASE_URL,
        OPENAI_CODEX_PROVIDER_TYPE,
        openai_codex_provider_name,
        decrypt_portable_credentials,
        get_openai_codex_host_id,
        save_openai_codex_registration,
        openai_codex_credential_lock,
    )
    from app.core.encryption import EncryptionService
    from app.models.repos import model_provider_repo
    from app.settings import settings
    from app.storage.database import close_db, create_session, init_db

    source_path = Path(args.input).expanduser()
    passphrase = getpass("输入转移文件口令（不会显示）：")
    credentials = decrypt_portable_credentials(
        source_path.read_text(encoding="utf-8"),
        passphrase,
    )

    async def import_credentials() -> str:
        await init_db()
        session = await create_session()
        try:
            store = OpenAICodexCredentialStore(EncryptionService(settings.encryption_key))
            imported = replace(
                credentials,
                ext_agent_host_id=get_openai_codex_host_id(),
            )
            async with openai_codex_credential_lock(imported.client_id, imported.subject):
                provider = None
                for candidate in await model_provider_repo.get_all(session):
                    if candidate.provider_type != OPENAI_CODEX_PROVIDER_TYPE:
                        continue
                    try:
                        candidate_credentials = store.read(candidate)
                    except Exception:
                        continue
                    if (
                        candidate_credentials.client_id == imported.client_id
                        and candidate_credentials.subject == imported.subject
                    ):
                        provider = candidate
                        if candidate_credentials.refresh_token:
                            if candidate_credentials.refresh_token == imported.refresh_token:
                                return provider.id
                            raise RuntimeError(
                                "本机已有该账户的有效凭据，不能用不同的 refresh token 覆盖；"
                                "请使用 openfic openai-codex auth --input 重新授权后更新凭据",
                            )
                        break
                if provider is None:
                    provider = await model_provider_repo.create(
                        session=session,
                        name=openai_codex_provider_name(imported),
                        url=OPENAI_CODEX_API_BASE_URL,
                        api_key_encrypted="",
                        provider_type=OPENAI_CODEX_PROVIDER_TYPE,
                    )
                provider.name = openai_codex_provider_name(imported)
                store.write(provider, imported)
                session.add(provider)
                await save_openai_codex_registration(session, imported, provider.id)
                await session.commit()
                return provider.id
        finally:
            await session.close()
            await close_db()

    provider_id = asyncio.run(import_credentials())
    print(f"OpenAI Codex 凭据已导入，provider_id: {provider_id}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="openfic",
        description="OpenFic 本地服务启动器",
    )

    subparsers = parser.add_subparsers(dest="command")

    serve_parser = subparsers.add_parser("serve", help="启动本地服务")
    serve_parser.add_argument("--host", default=_DEFAULT_HOST, help=f"绑定地址（默认 {_DEFAULT_HOST}）")
    serve_parser.add_argument("--port", type=int, default=_DEFAULT_PORT, help=f"绑定端口（默认 {_DEFAULT_PORT}）")
    serve_parser.add_argument("--auth-password", default=None, help="启用应用密码保护")
    serve_parser.set_defaults(handler=handle_serve)

    version_parser = subparsers.add_parser("version", help="显示版本号")
    version_parser.set_defaults(handler=handle_version)

    openai_codex_parser = subparsers.add_parser("openai-codex", help="管理 OpenAI Codex OAuth 凭据")
    openai_codex_subparsers = openai_codex_parser.add_subparsers(dest="openai_codex_command", required=True)
    auth_parser = openai_codex_subparsers.add_parser(
        "auth",
        help="在本机 127.0.0.1 回调完成浏览器授权并生成加密转移文件",
    )
    auth_parser.add_argument("--output", default=None, help="加密凭据文件路径")
    auth_parser.add_argument("--input", default=None, help="重新授权时读取原注册的加密凭据文件")
    auth_parser.add_argument("--new-account", action="store_true", help="明确注册另一个 OpenAI Codex 账户或工作区")
    auth_parser.set_defaults(handler=handle_openai_codex_auth)
    import_parser = openai_codex_subparsers.add_parser(
        "import",
        help="导入由 auth 生成的加密凭据文件并由本机接管刷新",
    )
    import_parser.add_argument("--input", required=True, help="加密凭据文件路径")
    import_parser.set_defaults(handler=handle_openai_codex_import)

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    handler = getattr(args, "handler", None)
    if handler is None:
        parser.print_help()
        raise SystemExit(0)

    handler(args)


if __name__ == "__main__":
    main()
