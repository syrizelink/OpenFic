"""PKCE OAuth flows: one-use state, bounded lifetime, encrypted token storage."""

import base64
import hashlib
import secrets
import time
from urllib.parse import urlencode


class PluginOAuth:
    def __init__(self, context):
        self.context = context

    async def start(
        self,
        *,
        authorization_url,
        token_url,
        client_id,
        client_secret="",
        scopes,
        extra=None,
    ):
        context = self.context
        context.require("network")
        context.require("secrets")
        base = context.runtime.get("backend_url")
        if not base:
            raise ValueError("OAuth must be started from a plugin UI request")
        verifier = secrets.token_urlsafe(48)
        challenge = (
            base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest())
            .rstrip(b"=")
            .decode()
        )
        state = secrets.token_urlsafe(32)
        redirect_uri = base + "/plugin-oauth/callback"
        context.host.oauth_flows[state] = {
            "plugin_id": context.plugin_id,
            "expires": time.monotonic() + 600,
            "token_url": token_url,
            "client_id": client_id,
            "client_secret": client_secret,
            "redirect_uri": redirect_uri,
            "verifier": verifier,
        }
        context.host.oauth_flows = {
            k: v
            for k, v in context.host.oauth_flows.items()
            if v["expires"] > time.monotonic()
        }
        if len(context.host.oauth_flows) > 100:
            context.host.oauth_flows.pop(state)
            raise ValueError("Too many pending OAuth flows")
        from urllib.parse import urlsplit

        if (
            urlsplit(authorization_url).hostname
            not in context.plugin.manifest.network_hosts
            or urlsplit(token_url).hostname not in context.plugin.manifest.network_hosts
        ):
            context.host.oauth_flows.pop(state)
            raise PermissionError("OAuth destinations must be declared network hosts")
        params = {
            "client_id": client_id,
            "response_type": "code",
            "redirect_uri": redirect_uri,
            "scope": " ".join(scopes),
            "state": state,
            "code_challenge": challenge,
            "code_challenge_method": "S256",
            **(extra or {}),
        }
        return {
            "url": authorization_url + "?" + urlencode(params),
            "redirect_uri": redirect_uri,
        }


async def finish_oauth(host, state: str, code: str | None, error: str | None):
    flow = host.oauth_flows.pop(state, None)
    if not flow or flow["expires"] < time.monotonic():
        raise ValueError("OAuth state expired, invalid, or already used")
    plugin = host.get(flow["plugin_id"])
    if not plugin.registration:
        raise ValueError("Plugin is no longer enabled")
    if error:
        raise ValueError("OAuth authorization was denied")
    if not code:
        raise ValueError("OAuth code is missing")
    context = host.context(plugin.manifest.id, None)
    form = {
        "grant_type": "authorization_code",
        "code": code,
        "client_id": flow["client_id"],
        "redirect_uri": flow["redirect_uri"],
        "code_verifier": flow["verifier"],
    }
    if flow["client_secret"]:
        form["client_secret"] = flow["client_secret"]
    response = await context.http.request("POST", flow["token_url"], form=form)
    if (
        not response["ok"]
        or not isinstance(response["json"], dict)
        or not response["json"].get("access_token")
    ):
        raise ValueError("OAuth token exchange failed")
    tokens = response["json"]
    tokens["obtained_at"] = time.time()
    await context.secrets.set("oauth.tokens", tokens)
    host.emit("oauth.connected", {"pluginId": plugin.manifest.id}, plugin.manifest.id)
