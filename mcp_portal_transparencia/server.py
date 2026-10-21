from typing import Literal
from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError

import client

mcp = MCPServer(
    name="portal-transparencia-mg",
    instructions="Dados de despesa do Estado de Minas Gerais (não de municípios), a partir de 2021. "
                 "Antes de filtrar por órgão, função, ação ou elemento, descubra o código com buscar_classificacao.",
)

DESPESAS = "/consultas/despesas"

def _sem_vazios(params: dict) -> dict:
    return {k: v for k, v in params.items() if v is not None}

@mcp.tool()
def anos_disponiveis() -> list[int]:
    """Anos com dados de despesa na API. Use antes de responder sobre um ano fora desse intervalo."""
    try:
        return client.anos_disponiveis()
    except client.ErroAPI as e:
        raise ToolError(str(e)) from e


@mcp.tool()
def buscar_classificacao(
    tipo: Literal["orgaos", "unidades", "funcoes", "subfuncoes", "programas", "acoes", "elementos-despesa", "itens-despesa", "fontes-recurso", "favorecidos"],
    termo: str,
    ano: int,
) -> list[dict]:
    """Converte um nome no código oficial usado pelos filtros de pesquisar_despesa.
    Devolve até 10 itens {id, codigo, nome}. Passe o CÓDIGO para pesquisar_despesa (é estável entre anos);
    o id é interno e muda a cada ano.
    Ex.: tipo="funcoes", termo="saude" -> [{"id": 4711, "codigo": "10", "nome": "10 - SAUDE"}]
         tipo="orgaos", termo="educacao" -> [{"id": 12158, "codigo": "1261", "nome": "1261 - SECRETARIA DE ESTADO DE EDUCACAO"}, ...]"""
    try:
        return client.lista(tipo, ano, termo)[:10]
    except client.ErroAPI as e:
        raise ToolError(str(e)) from e


@mcp.tool()
def maiores_favorecidos(ano: int, orgao: str | None = None, top: int = 10, periodo_inicio: str = "0101", periodo_fim: str = "3112") -> list[dict]:
    """Quem mais recebeu (por valor pago), opcionalmente dentro de um órgão.
    orgao é o CÓDIGO do órgão (ex. "1261" = SEE); descubra com buscar_classificacao."""
    try:
        id_orgao = _ids("orgaos", ano, [orgao])[0] if orgao else None
        params = _sem_vazios({"ano": ano, "periodo_inicio": periodo_inicio, "periodo_fim": periodo_fim,
                              "id_orgao": id_orgao, "colunas": "favorecido,valor_empenhado,valor_pago",
                              "order_by": "valor_pago", "order_dir": "DESC", "limit": min(top, 50)})
        return client.consultar(f"{DESPESAS}/favorecidos.json", params)["linhas"]
    except client.ErroAPI as e:
        raise ToolError(str(e)) from e

@mcp.tool()
def detalhar_empenho(id_empenho: int, ano: int) -> dict:
    """Ficha de um empenho: classificação, liquidações e pagamentos."""
    try:
        return client.detalhar_empenho(id_empenho, ano)
    except client.ErroAPI as e:
        raise ToolError(str(e)) from e



DIMENSOES = {  # parâmetro da tool -> (lista para converter código em id, chave do filtro)
    "orgaos": ("orgaos", "id_orgao"), "funcoes": ("funcoes", "id_funcao"),
    "subfuncoes": ("subfuncoes", "id_subfuncao"), "programas": ("programas", "id_programa"),
    "acoes": ("acoes", "id_acao"), "elementos": ("elementos-despesa", "id_elemento_despesa"),
}
AGRUPAR = {"orgao": None, "funcao": "funcao", "subfuncao": "subfuncao", "programa": "programa",
           "acao": "acao", "elemento": "elemento_despesa", "fonte": "fonte_recurso"}

def _ids(tipo: str, ano: int, codigos: list[str]) -> list[int]:
    por_codigo = {i["codigo"]: i["id"] for i in client.lista(tipo, ano)}
    faltando = [c for c in codigos if c not in por_codigo]
    if faltando:
        raise ToolError(f"Códigos de {tipo} inexistentes em {ano}: {faltando}. Use buscar_classificacao.")
    return [por_codigo[c] for c in codigos]


def _limpar(valores: dict) -> dict:
    return {
        "empenhado": round(valores.get("valor_empenhado") or 0, 2),
        "liquidado": round(valores.get("valor_liquidado") or 0, 2),
        "pago": round(valores.get("valor_pago") or 0, 2),
    }


@mcp.tool()
def pesquisar_despesa(
    ano: int,
    periodo_inicio: str = "0101",
    periodo_fim: str = "3112",
    orgaos: list[str] | None = None,
    funcoes: list[str] | None = None,
    subfuncoes: list[str] | None = None,
    programas: list[str] | None = None,
    acoes: list[str] | None = None,
    elementos: list[str] | None = None,
    agrupar_por: Literal["total", "orgao", "funcao", "subfuncao", "programa", "acao", "elemento", "fonte"] = "total",
    top: int = 10,
) -> dict:
    """Despesa do Estado de MG (empenhado, liquidado, pago) com filtros combinados.
    Filtros recebem CÓDIGOS oficiais, iguais em todos os anos (função "10" = Saúde,
    subfunção "306" = Alimentação e Nutrição, órgão "1261" = SEE).
    Descubra os códigos com buscar_classificacao.
    Vários códigos no mesmo filtro são somados (OU); filtros diferentes se combinam (E).
    Ex.: "quanto o Estado gastou com saúde em 2025" -> ano=2025, funcoes=["10"]."""

    filtros = {"ano": ano, "periodo_inicio": periodo_inicio, "periodo_fim": periodo_fim}
    codigos_por_filtro = {"orgaos": orgaos, "funcoes": funcoes, "subfuncoes": subfuncoes,
                          "programas": programas, "acoes": acoes, "elementos": elementos}
    try:
        for filtro, codigos in codigos_por_filtro.items():
            if codigos:
                tipo, chave = DIMENSOES[filtro]
                filtros[chave] = _ids(tipo, ano, codigos)

        coluna = AGRUPAR.get(agrupar_por)
        colunas = f"{coluna},valor_empenhado,valor_liquidado,valor_pago" if coluna else None
        r = client.pesquisa_avancada(filtros, colunas)
    except client.ErroAPI as e:
        raise ToolError(str(e)) from e

    resposta = {"totais": _limpar(r["totais"]), "filtros_aplicados": filtros, "avisos": []}

    if agrupar_por != "total":
        grupos = {}
        for reg in r["registros"]:
            nome = reg["orgao"] if coluna is None else reg[coluna]
            if nome not in grupos:
                grupos[nome] = {"valor_empenhado": 0, "valor_liquidado": 0, "valor_pago": 0}
            grupos[nome]["valor_empenhado"] += reg.get("valor_empenhado") or 0
            grupos[nome]["valor_liquidado"] += reg.get("valor_liquidado") or 0
            grupos[nome]["valor_pago"] += reg.get("valor_pago") or 0

        maiores = sorted(grupos, key=lambda nome: grupos[nome]["valor_pago"], reverse=True)[:top]
        resposta["por_" + agrupar_por] = [{"nome": nome, **_limpar(grupos[nome])} for nome in maiores]

    if funcoes or subfuncoes:
        resposta["avisos"].append("Com filtro de função/subfunção, a API não atribui restos a pagar (vêm 0).")
    if r["truncado"]:
        resposta["avisos"].append("Resultado truncado: refine os filtros.")
    return resposta


if __name__ == "__main__":
    mcp.run()  # stdio
