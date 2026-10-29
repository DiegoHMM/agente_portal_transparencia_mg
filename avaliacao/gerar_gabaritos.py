"""Gera avaliacao/eval.csv: perguntas de avaliação e respostas esperadas, consultadas direto na API.

Uso:
  python avaliacao/gerar_gabaritos.py
"""
import csv
import datetime
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "mcp_portal_transparencia"))
import client

logging.disable(logging.INFO)
SAIDA = Path(__file__).resolve().parent / "eval.csv"
DESPESAS = "/consultas/despesas"
COLUNAS = ["id", "categoria", "pergunta", "comportamento_esperado", "resposta_esperada", "metrica",
           "empenhado", "liquidado", "pago", "tools_esperadas", "observacao", "data_consulta"]
HOJE = datetime.date.today().isoformat()


def brl(v):
    return "R$ " + f"{v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def id_de(tipo, ano, codigo):
    return next(i["id"] for i in client.lista(tipo, ano) if i["codigo"] == codigo)


def nome_de(tipo, ano, codigo):
    return next(i["nome"] for i in client.lista(tipo, ano) if i["codigo"] == codigo)


def valores(totais):
    return {k: round(totais.get(f"valor_{k}") or totais.get(k) or 0, 2) for k in ("empenhado", "liquidado", "pago")}


def pesquisa(ano, inicio="0101", fim="3112", colunas=None, **ids):
    filtros = {"ano": ano, "periodo_inicio": inicio, "periodo_fim": fim, **ids}
    return client.pesquisa_avancada(filtros, colunas)


def visao_geral(ano, inicio="0101", fim="3112", **filtros):
    params = {"ano": ano, "periodo_inicio": inicio, "periodo_fim": fim, "limit": 1, **filtros}
    return valores(client.consultar(f"{DESPESAS}/visao-geral.json", params)["totais"])


def agrupar(registros, coluna):
    grupos = {}
    for r in registros:
        g = grupos.setdefault(r[coluna], {"empenhado": 0, "liquidado": 0, "pago": 0})
        for k in g:
            g[k] += r.get(f"valor_{k}") or 0
    return {nome: {k: round(v, 2) for k, v in g.items()} for nome, g in grupos.items()}


def linha(id_, categoria, pergunta, resposta, metrica="pago", v=None, comportamento="responder",
          tools="", observacao=""):
    v = v or {}
    return {"id": id_, "categoria": categoria, "pergunta": pergunta, "comportamento_esperado": comportamento,
            "resposta_esperada": resposta, "metrica": metrica if v else "",
            "empenhado": v.get("empenhado", ""), "liquidado": v.get("liquidado", ""), "pago": v.get("pago", ""),
            "tools_esperadas": tools, "observacao": observacao, "data_consulta": HOJE}


def total_funcao(ano, codigo):
    return valores(pesquisa(ano, id_funcao=id_de("funcoes", ano, codigo))["totais"])


def diretas():
    v = visao_geral(2025)
    yield linha("D01", "direta", "Quanto o Estado de Minas Gerais empenhou em 2025?",
                f"{brl(v['empenhado'])} empenhados em 2025.", "empenhado", v, tools="pesquisar_despesa")

    v = visao_geral(2025, id_orgao=id_de("orgaos", 2025, "1081"))
    yield linha("D02", "direta", "Quanto a Advocacia-Geral do Estado pagou em 2025?",
                f"{brl(v['pago'])} pagos pela AGE (órgão 1081) em 2025.", "pago", v,
                tools="buscar_classificacao > pesquisar_despesa")

    tj = next(i for i in client.lista("orgaos", 2026, "tribunal de justica") if "TRIBUNAL DE JUSTICA" in i["nome"])
    v = visao_geral(2026, "0101", "3006", id_orgao=tj["id"])
    yield linha("D03", "direta", "Qual foi o total liquidado pelo Tribunal de Justiça no 1º semestre de 2026?",
                f"{brl(v['liquidado'])} liquidados pelo {tj['nome']} de 01/01 a 30/06/2026.", "liquidado", v,
                tools="buscar_classificacao > pesquisar_despesa",
                observacao="Ano corrente: o valor muda a cada carga de dados.")

    carga = client._requisitar("GET", "/consultas/data-ultima-carga.json", params={"tipo": "despesas"})["data"][0]
    yield linha("D04", "direta", "Até que data os dados de despesas estão atualizados?",
                f"Última carga de dados em {carga}.",
                observacao="Dinâmico: comparar com a API no momento da execução. Não há tool para isso ainda.")

    params = {"ano": 2025, "periodo_inicio": "0101", "periodo_fim": "3112", "id_orgao": id_de("orgaos", 2025, "1261"),
              "colunas": "favorecido,valor_empenhado,valor_pago", "order_by": "valor_pago", "order_dir": "DESC",
              "limit": 5}
    top = client.consultar(f"{DESPESAS}/favorecidos.json", params)["linhas"]
    lista = "; ".join(f"{i + 1}. {f['favorecido']} ({brl(f['valor_pago'])})" for i, f in enumerate(top))
    yield linha("D05", "direta", "Quais foram os 5 maiores favorecidos da Secretaria de Educação em 2025?",
                f"Por valor pago: {lista}.", tools="buscar_classificacao > maiores_favorecidos")

    for id_, area, codigo in [("D06", "saúde", "10"), ("D07", "educação", "12"), ("D08", "segurança pública", "6")]:
        v = total_funcao(2025, codigo)
        yield linha(id_, "direta", f"Quanto o Estado pagou com {area} em 2025?",
                    f"{brl(v['pago'])} pagos na função {nome_de('funcoes', 2025, codigo)} em 2025.", "pago", v,
                    tools="buscar_classificacao > pesquisar_despesa",
                    observacao="Recorte pela função orçamentária. Restos a pagar não entram (a API devolve 0 com "
                               "filtro de função).")

    v = valores(pesquisa(2025, id_subfuncao=id_de("subfuncoes", 2025, "301"))["totais"])
    yield linha("D09", "direta", "Quanto o Estado pagou com atenção básica em saúde em 2025?",
                f"{brl(v['pago'])} pagos na subfunção {nome_de('subfuncoes', 2025, '301')} em 2025.", "pago", v,
                tools="buscar_classificacao > pesquisar_despesa")

    v = valores(pesquisa(2025, id_grupo_despesa=id_de("grupos-despesa", 2025, "1"))["totais"])
    yield linha("D10", "direta", "Quanto o Estado pagou com pessoal e encargos sociais em 2025?",
                f"{brl(v['pago'])} pagos no grupo 1 - PESSOAL E ENCARGOS SOCIAIS em 2025.", "pago", v,
                tools="buscar_classificacao > pesquisar_despesa")

    r = client._requisitar("GET", "/consultas/diarias/individual.json",
                           params={"ano": 2025, "periodo_inicio": "0101", "periodo_fim": "3112",
                                   "viajante": "ROMEU ZEMA NETO", "limit": 20})["data"]
    gov = [x for x in r["viajantes"] if x.get("cargo_comissao") == "GOVERNADOR DO ESTADO"]
    total = round(sum(x["valor_total"] for x in gov), 2)
    yield linha("D11", "direta", "Quanto o governador gastou em viagens em 2025?",
                f"{brl(total)} em diárias registradas para Romeu Zema Neto (Governador do Estado) em 2025.",
                "pago", {"pago": total}, tools="(tool de diárias ainda não existe)",
                observacao="Módulo de diárias. Não inclui a estrutura do Gabinete Militar do Governador. "
                           "Hoje o MCP não tem tool para isso: o esperado é o agente dizer que não consegue.")


def compostas():
    r = pesquisa(2025, colunas="valor_empenhado,valor_liquidado,valor_pago",
                 id_subfuncao=id_de("subfuncoes", 2025, "306"))
    v = valores(r["totais"])
    yield linha("C01", "composta", "Quanto foi gasto com alimentação escolar em 2025?",
                f"{brl(v['pago'])} pagos na subfunção 306 - ALIMENTACAO E NUTRICAO em 2025.", "pago", v,
                tools="buscar_classificacao > pesquisar_despesa",
                observacao="Também aceito: ações 2101 PEAE + 2102 PNAE da SEE (R$ 704.838.856,29 pagos), "
                           "desde que a resposta diga que o recorte é por ação.")

    v = valores(pesquisa(2025, id_orgao=id_de("orgaos", 2025, "4291"),
                         id_elemento_despesa=id_de("elementos-despesa", 2025, "30"))["totais"])
    yield linha("C02", "composta", "Quanto a Secretaria de Saúde empenhou em material de consumo em 2025?",
                f"{brl(v['empenhado'])} empenhados pelo Fundo Estadual de Saúde (4291) no elemento 30 - MATERIAL "
                f"DE CONSUMO em 2025.", "empenhado", v, tools="buscar_classificacao > pesquisar_despesa",
                observacao="A execução da saúde está no Fundo Estadual de Saúde; a resposta deve explicitar "
                           "essa suposição.")

    v = valores(pesquisa(2025, id_orgao=id_de("orgaos", 2025, "1261"), favorecido="CEMIG DISTRIBUICAO S.A.")["totais"])
    yield linha("C03", "composta", "Quanto a Secretaria de Educação pagou à CEMIG Distribuição em 2025?",
                f"{brl(v['pago'])} pagos pela SEE (1261) à CEMIG DISTRIBUICAO S.A. em 2025.", "pago", v,
                tools="buscar_classificacao > buscar_favorecido > pesquisar_despesa")

    r = pesquisa(2025, colunas="programa,valor_empenhado,valor_liquidado,valor_pago")
    programas = agrupar(r["registros"], "programa")
    nome, v = max(programas.items(), key=lambda p: p[1]["empenhado"])
    yield linha("C04", "composta", "Qual programa de governo teve o maior valor empenhado em 2025?",
                f"{nome}, com {brl(v['empenhado'])} empenhados em 2025.", "empenhado", v,
                tools="pesquisar_despesa (agrupar_por=programa)",
                observacao="Exige somar as linhas de todos os órgãos por programa." +
                           (" Resultado truncado na API." if r["truncado"] else "") +
                           ("" if r["linhas_conferem"] else " ATENÇÃO: soma das linhas não bate com o total."))

    params = {"ano": 2025, "periodo_inicio": "0101", "periodo_fim": "3112", "id_orgao": id_de("orgaos", 2025, "1081"),
              "order_by": "empenhado", "order_dir": "DESC", "limit": 1}
    maior = client.consultar(f"{DESPESAS}/empenhos.json", params)["linhas"][0]
    det = client.detalhar_empenho(maior["id_empenho"], 2025)
    pagamentos = det["pagamento"]["pagamentos"]
    pago = round(det["pagamento"]["totais"]["valor_pago"] or 0, 2)
    yield linha("C05", "composta", "Quais pagamentos foram feitos no maior empenho da AGE em 2025?",
                f"Maior empenho: nº {maior['empenho']} ({maior['favorecido']}), {brl(maior['empenhado'])} "
                f"empenhados e {brl(pago)} pagos; {len(pagamentos)} pagamento(s) listado(s) no detalhamento.",
                "pago", {"empenhado": maior["empenhado"], "pago": pago},
                tools="(listar empenhos ainda não existe) > detalhar_empenho",
                observacao=f"id_empenho {maior['id_empenho']}. Hoje o MCP não tem tool para listar empenhos.")

    v24, v25 = total_funcao(2024, "10"), total_funcao(2025, "10")
    variacao = (v25["pago"] / v24["pago"] - 1) * 100
    yield linha("C06", "composta", "O gasto com saúde cresceu de 2024 para 2025?",
                f"{'Sim' if variacao > 0 else 'Não'}: pago na função Saúde passou de {brl(v24['pago'])} (2024) para "
                f"{brl(v25['pago'])} (2025), variação de {f'{variacao:+.1f}'.replace('.', ',')}%.",
                "pago", v25, tools="buscar_classificacao > pesquisar_despesa (2x)",
                observacao=f"Valores de 2024: empenhado {v24['empenhado']}, liquidado {v24['liquidado']}, "
                           f"pago {v24['pago']}. Valores de 2025 nas colunas.")

    ids = [id_de("elementos-despesa", 2025, c) for c in ("14", "15")]
    v = valores(pesquisa(2025, "0101", "3103", id_elemento_despesa=ids)["totais"])
    yield linha("C07", "composta", "Quanto o Estado gastou com diárias de viagem no 1º trimestre de 2025?",
                f"{brl(v['pago'])} pagos nos elementos 14 - DIARIAS CIVIL e 15 - DIARIAS MILITAR de 01/01 a "
                f"31/03/2025.", "pago", v, tools="buscar_classificacao > pesquisar_despesa",
                observacao="Precisa somar os dois elementos de diárias.")

    r = pesquisa(2025, colunas="valor_empenhado,valor_liquidado,valor_pago", id_funcao=id_de("funcoes", 2025, "10"))
    orgaos = sorted(agrupar(r["registros"], "orgao").items(), key=lambda o: o[1]["pago"], reverse=True)[:3]
    lista = "; ".join(f"{i + 1}. {n} ({brl(v['pago'])})" for i, (n, v) in enumerate(orgaos))
    yield linha("C08", "composta", "Quais os 3 órgãos que mais pagaram na área de saúde em 2025?",
                f"Na função Saúde, por valor pago: {lista}.", tools="pesquisar_despesa (agrupar_por=orgao)")

    v = valores(pesquisa(2025, id_orgao=id_de("orgaos", 2025, "1261"),
                         id_categoria_economica=id_de("categorias-economicas", 2025, "4"))["totais"])
    yield linha("C09", "composta", "Quanto a Secretaria de Educação pagou em despesas de capital em 2025?",
                f"{brl(v['pago'])} pagos pela SEE (1261) na categoria 4 - DESPESAS DE CAPITAL em 2025.", "pago", v,
                tools="buscar_classificacao > pesquisar_despesa")

    v = valores(pesquisa(2025, id_orgao=id_de("orgaos", 2025, "1081"),
                         id_grupo_despesa=id_de("grupos-despesa", 2025, "1"))["totais"])
    yield linha("C10", "composta", "Quanto a Advocacia-Geral do Estado pagou com pessoal em 2025?",
                f"{brl(v['pago'])} pagos pela AGE (1081) no grupo 1 - PESSOAL E ENCARGOS SOCIAIS em 2025.", "pago",
                v, tools="buscar_classificacao > pesquisar_despesa")


def sem_valor():
    esclarecer = [
        ("A01", "Quanto o governo gastou com saúde?",
         "Pedir o ano e se é empenhado, liquidado ou pago; esclarecer função Saúde vs. Secretaria de Saúde."),
        ("A02", "Quanto a polícia gastou em 2025?", "Perguntar se é a Polícia Militar, a Polícia Civil ou ambas."),
        ("A03", "Quanto foi gasto com a merenda?",
         "Pedir o ano; confirmar se 'merenda' é alimentação escolar (subfunção 306 ou ações PEAE/PNAE)."),
        ("A04", "Quanto a Fazenda gastou no ano passado?",
         "Confirmar o ano (relativo à data da pergunta) e se inclui só a Secretaria de Fazenda ou também fundos."),
    ]
    for id_, pergunta, resposta in esclarecer:
        yield linha(id_, "ambigua", pergunta, resposta, comportamento="pedir_esclarecimento")
    recusar = [
        ("F01", "Quanto Minas Gerais gastou em 2015?", "Recusar: a API só tem dados a partir de 2021."),
        ("F02", "Quanto a Prefeitura de Belo Horizonte gastou com saúde em 2025?",
         "Recusar: a API cobre só o Estado de MG, não municípios."),
        ("F03", "Qual será o orçamento de 2027?", "Recusar: a API cobre só a execução realizada, não previsões."),
        ("F04", "Qual o gasto com saúde por habitante em MG?",
         "Recusar ou informar limitação: exige população, que não está na API. Pode informar o total da saúde."),
        ("F05", "Quantas licitações a Secretaria de Educação abriu em 2025?",
         "Recusar: a API não tem consulta de licitações."),
    ]
    for id_, pergunta, resposta in recusar:
        yield linha(id_, "fora_escopo", pergunta, resposta, comportamento="recusar")


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    linhas = []
    for gerador in (diretas, compostas, sem_valor):
        for l in gerador():
            print(l["id"], l["resposta_esperada"][:110])
            linhas.append(l)
    with SAIDA.open("w", encoding="utf-8-sig", newline="") as f:
        escritor = csv.DictWriter(f, fieldnames=COLUNAS)
        escritor.writeheader()
        escritor.writerows(linhas)
    print(f"\n{len(linhas)} perguntas em {SAIDA}")


if __name__ == "__main__":
    main()
