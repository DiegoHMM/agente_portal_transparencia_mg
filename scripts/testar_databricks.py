import json
import os

import requests
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()
host = os.environ["DATABRICKS_HOST"].rstrip("/")

r = requests.post(
    f"{host}/oidc/v1/token",
    auth=(os.environ["DATABRICKS_CLIENT_ID"], os.environ["DATABRICKS_CLIENT_SECRET"]),
    data={"grant_type": "client_credentials", "scope": os.getenv("DATABRICKS_SCOPES", "ai-gateway")},
    timeout=30,
)
if r.status_code != 200:
    raise SystemExit(f"Falha ao obter token ({r.status_code}): {r.text}")

cliente = OpenAI(base_url=f"{host}/ai-gateway/mlflow/v1", api_key=r.json()["access_token"])
resposta = cliente.chat.completions.create(
    model="inteligencia_artifical.default.portal_transparencia",
    messages=[{"role": "user", "content": "Responda só: ok"}],
    max_tokens=10,
    extra_headers={"Databricks-Ai-Gateway-Request-Tags": json.dumps({"config": "teste", "pergunta": "D06"})},
)
print(resposta.choices[0].message.content, resposta.usage)
