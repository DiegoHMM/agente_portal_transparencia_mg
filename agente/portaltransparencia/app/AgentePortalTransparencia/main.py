from collections import OrderedDict
from datetime import date
from strands import Agent
from strands.agent.conversation_manager import SlidingWindowConversationManager
from bedrock_agentcore.runtime import BedrockAgentCoreApp
from model.load import load_model
from mcp_client.client import get_streamable_http_mcp_client
from tracing.tool_logger import LogTools

app = BedrockAgentCoreApp()
log = app.logger

SYSTEM_PROMPT = """
Você é um assistente que responde perguntas sobre as despesas do Estado de Minas Gerais
(não de municípios), com dados do Portal da Transparência a partir de 2021.
Antes de filtrar por órgão, função, ação ou elemento, descubra o código com buscar_classificacao.
Sempre informe o ano e os filtros usados, e cite valores em reais.

Hoje é {hoje}. Anos anteriores a {ano} estão fechados; só {ano} tem dados parciais.
A diferença entre empenhado e pago num ano fechado não é "processamento": é o que foi inscrito
em restos a pagar e pago (ou não) no ano seguinte.

Recorte da pergunta:
- buscar_classificacao devolve no máximo 10 itens e só acha trechos do nome oficial.
- Na resposta, diga quais classificações entraram na soma e quais ficaram de fora e por quê.
  Se o recorte for incerto, mostre o valor do recorte estrito e o do recorte amplo.
"""


def _system_prompt() -> str:
    hoje = date.today()
    return SYSTEM_PROMPT.format(hoje=hoje.strftime("%d/%m/%Y"), ano=hoje.year)

# Tools do MCP do Portal da Transparência MG
tools = [get_streamable_http_mcp_client()]


def agent_factory():
    cache = OrderedDict()
    def get_or_create_agent(session_id):
        if session_id in cache:
            cache.move_to_end(session_id)
            return cache[session_id]
        if len(cache) >= 128:
            cache.popitem(last=False)
        cache[session_id] = Agent(
            model=load_model(),
            system_prompt=_system_prompt(),
            tools=tools,
            hooks=[LogTools()],
            conversation_manager=SlidingWindowConversationManager(window_size=20),
            callback_handler=None,
        )
        return cache[session_id]
    return get_or_create_agent
get_or_create_agent = agent_factory()


@app.entrypoint
async def invoke(payload, context):
    log.info("Invoking Agent.....")

    session_id = getattr(context, "session_id", "default-session")
    agent = get_or_create_agent(session_id)

    async for event in agent.stream_async(payload.get("prompt", "")):
        if not isinstance(event, dict) or "event" not in event:
            continue
        cbs = event["event"].get("contentBlockStart")
        if cbs is not None and not cbs.get("start"):
            continue
        yield event


if __name__ == "__main__":
    app.run()
