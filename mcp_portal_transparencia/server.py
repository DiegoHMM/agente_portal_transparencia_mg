import os
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
    tipo: Literal["orgaos", "unidades", "funcoes", "subfuncoes", "programas", "acoes", "categorias-economicas",
                  "grupos-despesa", "modalidades-aplicacao", "elementos-despesa", "itens-despesa", "fontes-recurso"],
    termo: str,
    ano: int,
) -> list[dict]:
    """Converte um nome no código oficial usado pelos filtros de pesquisar_despesa.
    Devolve até 10 itens {id, codigo, nome}. Passe o CÓDIGO para pesquisar_despesa (é estável entre anos);
    o id é interno e muda a cada ano.
    Exceção: itens-despesa e fontes-recurso repetem códigos (o item "10" existe em vários elementos);
    para eles passe o ID, buscado com o mesmo ano da pesquisa.
    Favorecidos não passam por aqui: use o filtro favorecido (nome) de pesquisar_despesa.
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
def buscar_favorecido(nome: str, ano: int) -> list[dict]:
    """Lista quem recebeu dinheiro do Estado com esse trecho no nome, com o CPF/CNPJ e o total pago no ano.
    Use antes de pesquisar_despesa quando o nome for genérico: "CEMIG" casa com CEMIG Distribuição,
    CEMIG Geração e Transmissão, Companhia Energética de MG, consórcios e associações.
    Passe o NOME COMPLETO escolhido no filtro favorecido de pesquisar_despesa.
    O cpf_cnpj serve para distinguir homônimos ao mostrar a resposta; CPFs de pessoas vêm mascarados."""
    if len(nome.strip()) < 3:
        raise ToolError("nome precisa ter pelo menos 3 letras.")
    params = {"ano": ano, "periodo_inicio": "0101", "periodo_fim": "3112",
              "favorecido": client.sem_acento(nome.strip()),
              "colunas": "favorecido,cnpj_cpf_favorecido,valor_pago", "order_by": "valor_pago", "order_dir": "DESC"}
    try:
        linhas = client.consultar_todas(f"{DESPESAS}/favorecidos.json", params)["linhas"]
    except client.ErroAPI as e:
        raise ToolError(str(e)) from e
    por_documento = {}
    for linha in linhas:
        documento = linha.get("cpf_cnpj_favorecido")
        item = por_documento.setdefault(documento, {"cpf_cnpj": documento, "nome": linha.get("favorecido"), "pago": 0})
        item["pago"] += linha.get("valor_pago") or 0
    maiores = sorted(por_documento.values(), key=lambda i: i["pago"], reverse=True)[:15]
    return [{**i, "pago": round(i["pago"], 2)} for i in maiores]


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
    "unidades": ("unidades", "id_unidade"), "categorias": ("categorias-economicas", "id_categoria_economica"),
    "grupos": ("grupos-despesa", "id_grupo_despesa"), "modalidades": ("modalidades-aplicacao", "id_modalidade_aplicacao"),
}
DIMENSOES_POR_ID = {
    "ids_itens": ("itens-despesa", "id_item_despesa"), "ids_fontes": ("fontes-recurso", "id_fonte_recurso"),
}
AGRUPAR = {"orgao": None, "unidade": "unidade_executora", "funcao": "funcao", "subfuncao": "subfuncao",
           "programa": "programa", "acao": "acao", "categoria": "categoria_economica", "grupo": "grupo_despesa",
           "modalidade": "modalidade_aplicacao", "elemento": "elemento_despesa", "item": "item_despesa",
           "fonte": "fonte_recurso"}

def _ids(tipo: str, ano: int, codigos: list[str]) -> list[int]:
    por_codigo = {i["codigo"]: i["id"] for i in client.lista(tipo, ano)}
    faltando = [c for c in codigos if c not in por_codigo]
    if faltando:
        raise ToolError(f"Códigos de {tipo} inexistentes em {ano}: {faltando}. Use buscar_classificacao.")
    return [por_codigo[c] for c in codigos]


def _validar_ids(tipo: str, ano: int, ids: list[int]) -> list[int]:
    existentes = {i["id"] for i in client.lista(tipo, ano)}
    faltando = [i for i in ids if i not in existentes]
    if faltando:
        raise ToolError(f"Ids de {tipo} inexistentes em {ano}: {faltando}. "
                        f"Os ids mudam a cada ano; use buscar_classificacao com ano={ano}.")
    return ids


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
    unidades: list[str] | None = None,
    funcoes: list[str] | None = None,
    subfuncoes: list[str] | None = None,
    programas: list[str] | None = None,
    acoes: list[str] | None = None,
    categorias: list[str] | None = None,
    grupos: list[str] | None = None,
    modalidades: list[str] | None = None,
    elementos: list[str] | None = None,
    ids_itens: list[int] | None = None,
    ids_fontes: list[int] | None = None,
    favorecido: str | None = None,
    agrupar_por: Literal["total", "orgao", "unidade", "funcao", "subfuncao", "programa", "acao", "categoria",
                         "grupo", "modalidade", "elemento", "item", "fonte"] = "total",
    top: int = 10,
) -> dict:
    """Despesa do Estado de MG (empenhado, liquidado, pago) com filtros combinados.
    A maioria dos filtros recebe CÓDIGOS oficiais, iguais em todos os anos (função "10" = Saúde,
    subfunção "306" = Alimentação e Nutrição, órgão "1261" = SEE, categoria "4" = Despesas de Capital,
    grupo "1" = Pessoal e Encargos Sociais). Descubra os códigos com buscar_classificacao.
    ids_itens e ids_fontes recebem o ID (não o código), porque esses códigos se repetem;
    busque o id com buscar_classificacao usando o mesmo ano.
    favorecido é parte do nome de quem recebeu (mínimo 3 letras) e soma todos os nomes que contêm o trecho:
    "CEMIG" inclui várias empresas e até associações. Para um favorecido exato, chame buscar_favorecido
    e passe o nome completo devolvido (ex. "CEMIG DISTRIBUICAO S.A.").
    Vários valores no mesmo filtro são somados (OU); filtros diferentes se combinam (E).
    Ex.: "quanto o Estado gastou com saúde em 2025" -> ano=2025, funcoes=["10"].
         "quanto a SEE pagou à CEMIG Distribuição em 2025" -> ano=2025, orgaos=["1261"], favorecido="CEMIG DISTRIBUICAO S.A."."""

    filtros = {"ano": ano, "periodo_inicio": periodo_inicio, "periodo_fim": periodo_fim}
    codigos_por_filtro = {"orgaos": orgaos, "unidades": unidades, "funcoes": funcoes, "subfuncoes": subfuncoes,
                          "programas": programas, "acoes": acoes, "categorias": categorias, "grupos": grupos,
                          "modalidades": modalidades, "elementos": elementos}
    ids_por_filtro = {"ids_itens": ids_itens, "ids_fontes": ids_fontes}
    if favorecido is not None and len(favorecido.strip()) < 3:
        raise ToolError("favorecido precisa ter pelo menos 3 letras.")
    try:
        for filtro, codigos in codigos_por_filtro.items():
            if codigos:
                tipo, chave = DIMENSOES[filtro]
                filtros[chave] = _ids(tipo, ano, codigos)
        for filtro, ids in ids_por_filtro.items():
            if ids:
                tipo, chave = DIMENSOES_POR_ID[filtro]
                filtros[chave] = _validar_ids(tipo, ano, ids)
        if favorecido:
            filtros["favorecido"] = client.sem_acento(favorecido.strip())

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
    elif agrupar_por != "total" and not r["linhas_conferem"]:
        resposta["avisos"].append("A soma dos grupos não bate com o total (paginação instável da API); "
                                  "use os totais e trate o detalhamento como aproximado, ou refine os filtros.")
    return resposta


if __name__ == "__main__":
    if os.getenv("DATABRICKS_APP_PORT"):
        mcp.run("streamable-http", host="0.0.0.0",
                port=int(os.environ["DATABRICKS_APP_PORT"]), stateless_http=True)
    else:
        mcp.run()
