import os
from functools import cache

import httpx
import openai
from databricks.sdk.core import Config
from strands.models.openai import OpenAIModel


class _DatabricksAuth(httpx.Auth):
    """Token OAuth M2M do service principal; o databricks-sdk guarda e renova antes de expirar."""

    def __init__(self):
        self._cfg = Config(scopes=["ai-gateway"])

    def auth_flow(self, request):
        request.headers.update(self._cfg.authenticate())
        yield request

@cache
def _cliente() -> openai.AsyncOpenAI:
    """Cliente único para todas as sessões, para compartilhar o token."""
    return openai.AsyncOpenAI(
        base_url=os.environ["DATABRICKS_BASE_URL"],
        api_key="databricks-oauth",
        http_client=httpx.AsyncClient(auth=_DatabricksAuth(), timeout=120),
    )

def load_model() -> OpenAIModel:
    """Modelo servido pelo Unity AI Gateway do Databricks (API compatível com OpenAI)."""
    return OpenAIModel(
        client=_cliente(),
        model_id=os.environ["DATABRICKS_MODEL_ENDPOINT"],
        params={"max_tokens": 4096},
    )
