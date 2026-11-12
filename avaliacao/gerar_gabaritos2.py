"""
Uso:
  python avaliacao/gerar_gabaritos2.py
"""
import csv
import sys
from pathlib import Path

from gerar_gabaritos import COLUNAS, agrupar, brl, id_de, linha, nome_de, pesquisa, valores, visao_geral

SAIDA = Path(__file__).resolve().parent / "eval2.csv"
BUSCA_ORGAO = "buscar_classificacao > pesquisar_despesa"


def total(ano, inicio="0101", fim="3112", **ids):
    return valores(pesquisa(ano, inicio, fim, **ids)["totais"])


def orgao(ano, codigo, inicio="0101", fim="3112"):
    """Total do órgão pela pesquisa avançada (a mesma da tool), conferido com a visão geral (outro endpoint)."""
    id_ = id_de("orgaos", ano, codigo)
    v = total(ano, inicio, fim, id_orgao=id_)
    conferencia = visao_geral(ano, inicio, fim, id_orgao=id_)
    aviso = "" if conferencia == v else f" ATENÇÃO: visão geral diverge da pesquisa avançada ({conferencia})."
    return v, aviso


def nome_orgao(ano, codigo):
    return nome_de("orgaos", ano, codigo)


def p(v):
    return brl(v["pago"])


def diretas():
    v, aviso = orgao(2024, "1031")
    yield linha("D12", "direta", "Quanto o Tribunal de Justiça de Minas Gerais pagou em 2024?",
                f"{p(v)} pagos pelo 1031 - TRIBUNAL DE JUSTICA DO ESTADO DE MINAS GERAIS em 2024.", "pago", v,
                tools=BUSCA_ORGAO, observacao="O pago inclui restos a pagar de anos anteriores." + aviso)

    v, aviso = orgao(2023, "1191")
    yield linha("D13", "direta", "Quanto a Secretaria de Estado de Fazenda empenhou em 2023?",
                f"{brl(v['empenhado'])} empenhados pela 1191 - SECRETARIA DE ESTADO DE FAZENDA em 2023.",
                "empenhado", v, tools=BUSCA_ORGAO,
                observacao="Não inclui o órgão 1911 - EGE SEC.FAZENDA-ENCARGOS DIVERSOS, que é outra unidade "
                           "orçamentária." + aviso)

    v = total(2022, id_elemento_despesa=id_de("elementos-despesa", 2022, "3"))
    yield linha("D14", "direta", "Quanto o Estado pagou em pensões em 2022?",
                f"{p(v)} pagos no elemento 03 - PENSOES em 2022.", "pago", v, tools=BUSCA_ORGAO,
                observacao="Recorte pelo elemento de despesa (pensões pagas por todos os órgãos). Não confundir "
                           "com a função 9 - PREVIDENCIA SOCIAL, que é mais ampla.")

    v = total(2024, id_grupo_despesa=id_de("grupos-despesa", 2024, "2"))
    yield linha("D15", "direta", "Quanto o Estado pagou de juros e encargos da dívida em 2024?",
                f"{p(v)} pagos no grupo 2 - JUROS E ENCARGOS DA DIVIDA em 2024.", "pago", v, tools=BUSCA_ORGAO)

    v, aviso = orgao(2022, "1501")
    yield linha("D16", "direta", "Quanto a Secretaria de Planejamento e Gestão liquidou em 2022?",
                f"{brl(v['liquidado'])} liquidados pela 1501 - SECRETARIA DE ESTADO DE PLANEJAMENTO E GESTAO "
                f"em 2022.", "liquidado", v, tools=BUSCA_ORGAO,
                observacao="Não inclui o órgão 1941 - EGE-SECRETARIA DE ESTADO DE PLANEJAMENTO E GESTAO." + aviso)

    nome = "MGS MINAS GERAIS ADMINISTRACAO E SERVICOS S/A"
    v = total(2024, favorecido=nome)
    amplo = total(2024, favorecido="MGS")
    yield linha("D17", "direta", "Quanto o Estado pagou à MGS em 2024?",
                f"{p(v)} pagos à {nome} em 2024, somando todos os órgãos.", "pago", v,
                tools="buscar_favorecido > pesquisar_despesa",
                observacao=f"Soma os dois CNPJs com esse nome (33.224.254/0001-42 e 33.224.254/0011-14). Armadilha: o "
                           f"filtro só com 'MGS' também pega AMGS COMERCIO E REPRESENTACOES LTDA e MGS BRASIL "
                           f"DISTRIBUIDORA LTDA ({p(amplo)} pagos); o agente deve usar o nome completo.")

    v, aviso = orgao(2021, "1441")
    yield linha("D18", "direta", "Quanto a Defensoria Pública de Minas Gerais pagou em 2021?",
                f"{p(v)} pagos pela 1441 - DEFENSORIA PUBLICA DO ESTADO DE MINAS GERAIS em 2021.", "pago", v,
                tools=BUSCA_ORGAO, observacao="Primeiro ano com dados na API." + aviso)


def compostas():
    r = pesquisa(2025, colunas="acao,valor_empenhado,valor_liquidado,valor_pago",
                 id_orgao=id_de("orgaos", 2025, "1031"))
    acoes = sorted(agrupar(r["registros"], "acao").items(), key=lambda a: a[1]["pago"], reverse=True)
    (nome, v), (nome2, v2) = acoes[0], acoes[1]
    yield linha("C11", "composta", "Qual ação do Tribunal de Justiça teve o maior valor pago em 2025?",
                f"{nome}, com {p(v)} pagos pelo TJMG (1031) em 2025.", "pago", v,
                tools="buscar_classificacao > pesquisar_despesa (orgaos=['1031'], agrupar_por=acao)",
                observacao=f"Segunda colocada: {nome2} ({p(v2)})." +
                           ("" if r["linhas_conferem"] else " ATENÇÃO: soma das linhas não bate com o total."))

    serie = {a: total(a, id_grupo_despesa=id_de("grupos-despesa", a, "2")) for a in range(2021, 2026)}
    menor = min(serie, key=lambda a: serie[a]["pago"])
    maior = max(serie, key=lambda a: serie[a]["pago"])
    yield linha("C12", "composta", "Como evoluiu o pagamento de juros da dívida de 2021 a 2025?",
                f"Pago no grupo 2 - JUROS E ENCARGOS DA DIVIDA: "
                f"{'; '.join(f'{a}: {p(v)}' for a, v in serie.items())}. Menor valor em {menor} e maior em {maior}.",
                "pago", serie[2025], tools="buscar_classificacao > pesquisar_despesa (5x, uma por ano)",
                observacao=f"Colunas com os valores de 2025. Em 2021 o empenhado foi {brl(serie[2021]['empenhado'])}, "
                           f"muito acima do pago. A resposta deve trazer os 5 anos.")

    tot = total(2025)
    prev = total(2025, id_funcao=id_de("funcoes", 2025, "9"))
    pct = prev["pago"] / tot["pago"] * 100
    yield linha("C13", "composta", "Que percentual do total pago pelo Estado em 2025 foi para previdência social?",
                f"{f'{pct:.1f}'.replace('.', ',')}%: {p(prev)} pagos na função 9 - PREVIDENCIA SOCIAL, de um total "
                f"de {p(tot)} pagos pelo Estado em 2025.", "pago", prev,
                tools="buscar_classificacao > pesquisar_despesa (2x: total e função 9)",
                observacao=f"Colunas com os valores da função 9. Percentual exato: "
                           f"{f'{pct:.2f}'.replace('.', ',')}%. A divisão fica com o LLM (nenhuma tool calcula "
                           f"percentual); conferir a conta.")

    v = total(2025, "0101", "3006", id_orgao=id_de("orgaos", 2025, "1501"),
              id_elemento_despesa=id_de("elementos-despesa", 2025, "40"))
    yield linha("C14", "composta",
                "Quanto a Secretaria de Planejamento e Gestão pagou em serviços de tecnologia da informação no "
                "1º semestre de 2025?",
                f"{p(v)} pagos pela SEPLAG (1501) no elemento 40 - SERVICOS DE TECNOLOGIA DA INFORMACAO E "
                f"COMUNICACAO - PESSOA JURIDICA de 01/01 a 30/06/2025.", "pago", v, tools=BUSCA_ORGAO,
                observacao="Período parcial (periodo_fim=3006). Recorte alternativo: subfunção 126 - TECNOLOGIA DA "
                           "INFORMACAO; aceitar se a resposta explicitar o recorte.")

    ids = [id_de("grupos-despesa", 2025, c) for c in ("2", "6")]
    v = total(2025, id_grupo_despesa=ids)
    juros = total(2025, id_grupo_despesa=ids[:1])
    amort = total(2025, id_grupo_despesa=ids[1:])
    yield linha("C15", "composta", "Quanto o Estado pagou com a dívida pública em 2025, somando juros e amortização?",
                f"{p(v)} pagos nos grupos 2 - JUROS E ENCARGOS DA DIVIDA e 6 - AMORTIZACAO DA DIVIDA em 2025.",
                "pago", v, tools="buscar_classificacao > pesquisar_despesa",
                observacao=f"Precisa somar os dois grupos. Juros: {p(juros)}; amortização: {p(amort)} pagos.")

    nome = "COMPANHIA DE TECNOLOGIA DA INFORMACAO DO ESTADO DE MINAS GERAIS-PRODEM"
    v = total(2025, id_orgao=id_de("orgaos", 2025, "1191"), favorecido=nome)
    yield linha("C16", "composta", "Quanto a Secretaria de Fazenda pagou à Prodemge em 2025?",
                f"{p(v)} pagos pela SEF (1191) à {nome} (CNPJ 16.636.540/0001-04) em 2025.", "pago", v,
                tools="buscar_classificacao > buscar_favorecido > pesquisar_despesa",
                observacao="Armadilha: buscar_favorecido('PRODEMGE') não acha nada, porque o nome na base é "
                           "truncado ('...-PRODEM'). O agente precisa buscar pela razão social.")


def ambiguas():
    def lista_valores(itens):
        return "; ".join(f"{rotulo}: {p(v)}" for rotulo, v in itens)

    itens = [(nome_orgao(2024, c), orgao(2024, c)[0]) for c in ("1031", "1051", "1451")]
    itens.append(("função 2 - JUDICIARIA", total(2024, id_funcao=id_de("funcoes", 2024, "2"))))
    yield linha("A05", "ambigua", "Quanto a Justiça gastou em 2024?",
                "Perguntar se é o Tribunal de Justiça, o Tribunal de Justiça Militar, a Secretaria de Justiça e "
                "Segurança Pública ou a função Judiciária; e se o valor é empenhado, liquidado ou pago.",
                comportamento="pedir_esclarecimento",
                observacao=f"Valores pagos em 2024 de cada interpretação: {lista_valores(itens)}.")

    ap = total(2025, id_elemento_despesa=id_de("elementos-despesa", 2025, "1"))
    pr = total(2025, id_funcao=id_de("funcoes", 2025, "9"))
    yield linha("A06", "ambigua", "Quanto o Estado gasta com aposentados?",
                "Pedir o ano; esclarecer se é só aposentadorias (elemento 01) ou toda a previdência (função 9, "
                "inclui pensões).", comportamento="pedir_esclarecimento",
                observacao=f"Referência 2025 (pago): elemento 01 - APOSENTADORIAS, RESERVA REMUNERADA E REFORMAS "
                           f"{p(ap)}; função 9 - PREVIDENCIA SOCIAL {p(pr)}.")

    itens = [("grupo 2 - JUROS E ENCARGOS DA DIVIDA", total(2025, id_grupo_despesa=id_de("grupos-despesa", 2025, "2"))),
             ("grupo 6 - AMORTIZACAO DA DIVIDA", total(2025, id_grupo_despesa=id_de("grupos-despesa", 2025, "6"))),
             ("órgão 1916 - GESTAO DA DIVIDA PUBLICA ESTADUAL", orgao(2025, "1916")[0])]
    yield linha("A07", "ambigua", "Quanto foi pago de dívida pública em 2025?",
                "Esclarecer se é só juros, só amortização (principal) ou ambos.",
                comportamento="pedir_esclarecimento",
                observacao=f"Valores pagos em 2025: {lista_valores(itens)}. Também aceito: responder com juros, "
                           f"amortização e a soma, explicitando o recorte.")

    mp, fmp = orgao(2025, "1091")[0], orgao(2025, "4441")[0]
    yield linha("A08", "ambigua", "Quanto o Ministério Público gastou em 2025?",
                "Esclarecer se é empenhado, liquidado ou pago e se inclui o Fundo Especial do Ministério Público.",
                comportamento="pedir_esclarecimento",
                observacao=f"O MP aparece como 1091 - PROCURADORIA GERAL DE JUSTICA (pago {p(mp)}; empenhado "
                           f"{brl(mp['empenhado'])}) e 4441 - FUNDO ESPECIAL DO MINISTERIO PUBLICO (pago {p(fmp)}). "
                           f"Armadilha: buscar 'ministerio publico' só acha o fundo.")

    itens = [(nome_orgao(2025, c), orgao(2025, c)[0]) for c in ("1501", "1941")]
    itens.append(("subfunção 121 - PLANEJAMENTO E ORCAMENTO",
                  total(2025, id_subfuncao=id_de("subfuncoes", 2025, "121"))))
    yield linha("A09", "ambigua", "Quanto o Planejamento gastou em 2025?",
                "Esclarecer se é a Secretaria de Planejamento e Gestão (1501), o EGE-SEPLAG (1941) ou a "
                "subfunção Planejamento e Orçamento; e a métrica.", comportamento="pedir_esclarecimento",
                observacao=f"Valores pagos em 2025: {lista_valores(itens)}.")

    q4 = total(2025, "0110", "3112", id_orgao=id_de("orgaos", 2025, "1441"))
    q3 = total(2026, "0107", "3009", id_orgao=id_de("orgaos", 2026, "1441"))
    yield linha("A10", "ambigua", "Quanto a Defensoria Pública gastou no último trimestre?",
                "Esclarecer o período (último trimestre fechado de 2026 ou 4º trimestre de 2025, o último ano fechado) "
                "e se o valor é empenhado, liquidado ou pago.", comportamento="pedir_esclarecimento",
                observacao=f"Defensoria Pública (1441), valores pagos: 4º trimestre de 2025 (01/10 a 31/12/2025) "
                           f"{p(q4)}; 3º trimestre de 2026 (01/07 a 30/09/2026) {p(q3)}. Os valores de 2026 mudam "
                           f"a cada carga de dados.")

    itens = [(nome_orgao(2024, c), orgao(2024, c)[0]) for c in ("4711", "2011", "2121", "2361", "4551")]
    yield linha("A11", "ambigua", "Quanto os fundos de previdência pagaram em 2024?",
                "Esclarecer quais entidades: FUNFIP, IPSEMG, IPSM, IPLEMG, fundo de pecúlio; ou a função 9 inteira.",
                comportamento="pedir_esclarecimento",
                observacao=f"Valores pagos em 2024: {lista_valores(itens)}.")

    sj = total(2025, id_elemento_despesa=id_de("elementos-despesa", 2025, "91"))
    yield linha("A12", "ambigua", "Quanto o Estado gastou com precatórios?",
                "Pedir o ano e a métrica; confirmar que precatórios correspondem ao elemento 91 - SENTENCAS JUDICIAIS.",
                comportamento="pedir_esclarecimento",
                observacao=f"Referência 2025: elemento 91 com {p(sj)} pagos e {brl(sj['empenhado'])} empenhados. "
                           f"Também pode haver precatórios em outros elementos (ex. 92 - despesas de exercícios "
                           f"anteriores).")

    fa = total(2023, id_funcao=id_de("funcoes", 2023, "4"))
    sa = total(2023, id_subfuncao=id_de("subfuncoes", 2023, "122"))
    yield linha("A13", "ambigua", "Quanto o governo gastou com administração em 2023?",
                "Esclarecer se é a função 4 - ADMINISTRACAO, a subfunção 122 - ADMINISTRACAO GERAL (presente em "
                "todas as áreas) ou os órgãos de gestão (ex. SEPLAG); e a métrica.",
                comportamento="pedir_esclarecimento",
                observacao=f"Valores pagos em 2023: função 4 {p(fa)}; subfunção 122 {p(sa)}.")


def fora_escopo():
    recusar = [
        ("F06", "Quanto o Estado arrecadou de ICMS em 2025?",
         "Recusar: o MCP só tem dados de despesa, não de receita."),
        ("F07", "Qual é o salário de um desembargador do Tribunal de Justiça?",
         "Recusar: não há tool de remuneração de servidores."),
        ("F08", "Qual foi o déficit da previdência estadual em 2025?",
         "Recusar ou informar limitação: exige receitas de contribuição, que não estão no MCP. Pode informar a "
         "despesa da função 9 - PREVIDENCIA SOCIAL."),
        ("F09", "O Tribunal de Justiça de Minas gasta mais que o de São Paulo?",
         "Recusar a comparação: a API cobre só o Estado de MG, sem dados de outros estados. Pode informar o gasto "
         "do TJMG, deixando claro que não dá para comparar."),
        ("F10", "O governo de Minas está gastando bem com a previdência?",
         "Recusar o juízo de valor: a API traz valores, não avaliações. Pode informar os valores da função 9 - "
         "PREVIDENCIA SOCIAL sem opinar."),
        ("F11", "Qual é o saldo atual da dívida de Minas Gerais com a União?",
         "Recusar: a API traz pagamentos (despesa), não o estoque da dívida. Pode informar juros e amortização pagos."),
        ("F12", "Quantos servidores aposentados o Estado de Minas Gerais tem?",
         "Recusar: a API não tem quantidade de servidores ou beneficiários."),
        ("F13", "Quanto o governo federal gastou com o INSS em 2025?",
         "Recusar: a API cobre só o Estado de MG, não a União."),
    ]
    inss = total(2025, favorecido="INSTITUTO NACIONAL DO SEGURO SOCIAL")
    observacoes = {
        "F13": f"Armadilha: o INSS aparece como favorecido do Estado ({p(inss)} pagos em 2025, CNPJ "
               f"29.979.036/0001-40 e filial). Responder com esse valor é erro: é o que o Estado pagou ao INSS, não o "
               f"gasto federal. Aceitável: recusar e, opcionalmente, citar esse pagamento deixando clara a diferença.",
    }
    for id_, pergunta, resposta in recusar:
        yield linha(id_, "fora_escopo", pergunta, resposta, comportamento="recusar",
                    observacao=observacoes.get(id_, ""))


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    linhas = []
    for gerador in (diretas, compostas, ambiguas, fora_escopo):
        for l in gerador():
            print(l["id"], l["resposta_esperada"][:110], "|", l["observacao"][:80])
            linhas.append(l)
    with SAIDA.open("w", encoding="utf-8-sig", newline="") as f:
        escritor = csv.DictWriter(f, fieldnames=COLUNAS)
        escritor.writeheader()
        escritor.writerows(linhas)
    print(f"\n{len(linhas)} perguntas em {SAIDA}")


if __name__ == "__main__":
    main()
