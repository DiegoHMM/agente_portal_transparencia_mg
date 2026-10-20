from typing import Literal
from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError

import client

mcp = MCPServer(
    name="portal-transparencia-mg",
    instructions="Dados de despesa do Estado de Minas Gerais (não de municípios), a partir de 2021. "
                 "Antes de filtrar por órgão, ação ou elemento, descubra o id com buscar_classificacao.",
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
    tipo: Literal["orgaos", "unidades", "programas", "acoes", "elementos-despesa", "itens-despesa", "favorecidos"],
    termo: str,
    ano: int
  ) -> list[int]:
    """Converte um nome em id. Os ids mudam a cada ano: use o mesmo ano da consulta.
    Ex.: tipo="orgaos", termo="educacao" -> [{"id": 12158, "codigo": "1261", "nome": "..."}]"""
    try:
        return client.list(tipo, ano, termo)[:10]
    except client.ErroAPI as e:
        raise ToolError(str(e)) from e


@mcp.tool()
def consultar_totais(
    ano: int,
    periodo_inicio: str = "0101",
    periodo_fim: str = "3112",
    id_orgao: int | None = None,
    ids_acao: list[int] | None = None,
    ids_elemento_despesa: list[int] | None = None,
) -> dict:
    """Totais empenhado, liquidado e pago. Período em DDMM ("0101" a "3112" é o ano todo).
    Sem filtros: total do Estado. Vários ids de ação ou de elemento são somados.
    Não existe filtro por função ou subfunção: a API ignora esse filtro."""
    if ids_acao and ids_elemento_despesa:
        raise ToolError("Informe ids_acao ou ids_elemento_despesa, não os dois.")
    base = _sem_vazios({"ano": ano, "periodo_inicio": periodo_inicio, "periodo_fim": periodo_fim, "id_orgao": id_orgao, "limit": 1})
    if ids_acao:
        path, chave, ids = f"{DESPESAS}/programas.json", "id_acao", ids_acao
    elif ids_elemento_despesa:
        path, chave, ids = f"{DESPESAS}/itens-despesa.json", "id_elemento_despesa", ids_elemento_despesa
    else:
        path, chave, ids = f"{DESPESAS}/visao-geral.json", None, [None]

    soma, parcelas = {"empenhado": 0.0, "liquidado": 0.0, "pago": 0.0}, []
    try:
        for id_ in ids:
            params = base if chave is None else {**base, chave: id_}
            t = client.consultar(path, params)["totais"]
            for k in soma:
                soma[k] += t.get(k, 0)
            if chave:
                parcelas.append({chave: id_, **{k: round(t.get(k, 0), 2) for k in soma}})
    except client.ErroAPI as e:
        raise ToolError(str(e)) from e
    return {"valores": {k: round(v, 2) for k, v in soma.items()}, "parcelas": parcelas, "endpoint": path}

@mcp.tool
def maiores_favorecidos(ano: int, id_orgao: int | None = None, top: int = 10, periodo_inicio: str = "0101", periodo_fim: str = "3112")-> list[dict]:
    """Quem mais recebeu (por valor pago), opcionalmente dentro de um órgão."""
    try:
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


if __name__ == "__main__":
    mcp.run()  # stdio