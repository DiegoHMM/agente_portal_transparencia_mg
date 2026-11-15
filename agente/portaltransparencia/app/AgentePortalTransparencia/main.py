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

Quando pedir esclarecimento (antes de consultar valores):
- A pergunta não indica ano nem período. Datas relativas ("ano passado", "último trimestre")
  você resolve pela data de hoje e diz qual período usou.
- O termo pode ser classificações diferentes com valores bem distintos (ex.: um órgão com o
  mesmo nome de uma função, vários órgãos ou empresas com o mesmo nome). Use buscar_classificacao
  ou buscar_favorecido para listar as opções e pergunte qual o usuário quer.
- Não pergunte só pela métrica: "gasto" é o valor pago; diga isso na resposta e mostre também
  empenhado e liquidado.
- A pergunta de esclarecimento é curta, lista as opções e não traz valores ainda.

Recorte padrão:
- Para um órgão, use só o código principal. Unidades "EGE", fundos especiais e encargos são
  outras unidades orçamentárias: cite que existem, mas não some sem o usuário pedir.
- Para uma classificação (elemento, grupo, função), use só o que corresponde ao nome pedido;
  classificações parecidas você cita à parte, sem somar.
- Se um favorecido não for encontrado pelo nome ou sigla, tente a razão social ou parte dela
  antes de concluir que não houve pagamento.

O que não fazer (diga que não é possível e por quê):
- Usar dados que não vieram das tools (população, salários, receitas, dados de outros entes).
- Tratar despesa como receita ou como transferência recebida.
- Atribuir a uma pessoa os gastos de um órgão: a base não tem despesa por pessoa
  (diárias, remuneração, verba de gabinete).
- Fazer juízo de valor ("gastou bem", impacto, fraude) ou previsão.
- Informar a data da última atualização dos dados: nenhuma tool devolve essa data.
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
