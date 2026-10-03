import httpx
import pytest
import respx

from app.models.adapters.openai_codex import OpenAICodexAdapter


@pytest.mark.asyncio
@respx.mock
async def test_openai_codex_adapter_reads_account_models_array_and_list_visibility():
    route = respx.get("https://api.openai.com/v1/models").mock(
        return_value=httpx.Response(
            200,
            json={
                "models": [
                    {"slug": "gpt-visible", "display_name": "Visible GPT", "visibility": "list"},
                    {"slug": "gpt-hidden", "display_name": "Hidden GPT", "visibility": "hidden"},
                ]
            },
        )
    )

    models = await OpenAICodexAdapter().get_llm_models(
        httpx.AsyncClient(),
        "https://api.openai.com/v1",
        "access-token",
    )

    assert models == [{"id": "gpt-visible", "name": "Visible GPT"}]
    assert route.calls[0].request.headers["authorization"] == "Bearer access-token"
