"""
Uso:
  python avaliacao/gerar_gabaritos3.py
"""
import csv
import sys
from pathlib import Path

from gerar_gabaritos import COLUNAS, agrupar, brl, id_de, linha, nome_de, pesquisa, valores

SAIDA = Path(__file__).resolve().parent / "eval3.csv"
BUSCA = "buscar_classificacao > pesquisar_despesa"


def total(ano, inicio="0101", fim="3112", **ids):
    return valores(pesquisa(ano, inicio, fim, **ids)["totais"])


def p(v):
    return brl(v["pago"])


def percentual(v, casas=1, sinal=False):
    formato = f"{{:{'+' if sinal else ''}.{casas}f}}"
    return formato.format(v).replace(".", ",") + "%"


def total_dimensao(tipo, chave, codigo, ano, inicio="0101", fim="3112"):
    return total(ano, inicio, fim, **{chave: id_de(tipo, ano, codigo)})


def diretas():
    casos = [
        ("D19", 2024, "funcoes", "id_funcao", "13", "cultura", "função", "pago"),
        ("D20", 2023, "funcoes", "id_funcao", "17", "saneamento", "função", "liquidado"),
        ("D21", 2022, "subfuncoes", "id_subfuncao", "302", "assistência hospitalar e ambulatorial",
         "subfunção", "pago"),
        ("D22", 2024, "elementos-despesa", "id_elemento_despesa", "33", "passagens e despesas com locomoção",
         "elemento", "empenhado"),
        ("D23", 2023, "categorias-economicas", "id_categoria_economica", "4", "despesas de capital",
         "categoria", "pago"),
        ("D24", 2021, "grupos-despesa", "id_grupo_despesa", "3", "outras despesas correntes",
         "grupo", "pago"),
        ("D25", 2025, "funcoes", "id_funcao", "26", "transporte", "função", "pago"),
        ("D26", 2024, "elementos-despesa", "id_elemento_despesa", "46", "auxílio-alimentação",
         "elemento", "liquidado"),
    ]
    verbos = {"pago": "pagou", "liquidado": "liquidou", "empenhado": "empenhou"}
    participios = {"pago": "pagos", "liquidado": "liquidados", "empenhado": "empenhados"}
    for id_, ano, tipo, chave, codigo, assunto, rotulo, metrica in casos:
        v = total_dimensao(tipo, chave, codigo, ano)
        nome = nome_de(tipo, ano, codigo)
        preposicao = "no" if rotulo in {"elemento", "grupo"} else "na"
        yield linha(id_, "direta", f"Quanto o Estado {verbos[metrica]} com {assunto} em {ano}?",
                    f"{brl(v[metrica])} {participios[metrica]} {preposicao} {rotulo} {nome} em {ano}.",
                    metrica, v, tools=BUSCA,
                    observacao="O recorte é pela classificação orçamentária indicada, em todos os órgãos.")


def compostas():
    total_estado = total(2024)
    educacao = total_dimensao("funcoes", "id_funcao", "12", 2024)
    pct = educacao["pago"] / total_estado["pago"] * 100
    yield linha("C17", "composta", "Que percentual do total pago pelo Estado em 2024 foi destinado à educação?",
                percentual(pct) + f": {p(educacao)} na função 12 - EDUCACAO, de "
                f"{p(total_estado)} pagos pelo Estado em 2024.", "pago", educacao,
                tools="buscar_classificacao > pesquisar_despesa (2x)",
                observacao=f"Percentual exato: {percentual(pct, 2)}. Colunas numéricas contêm os valores da educação.")

    v23 = total_dimensao("funcoes", "id_funcao", "13", 2023)
    v24 = total_dimensao("funcoes", "id_funcao", "13", 2024)
    variacao = (v24["pago"] / v23["pago"] - 1) * 100
    yield linha("C18", "composta", "O pagamento na área de cultura aumentou de 2023 para 2024?",
                f"{'Sim' if variacao > 0 else 'Não'}: passou de {p(v23)} em 2023 para {p(v24)} em 2024 "
                f"({percentual(variacao, sinal=True)}).", "pago", v24,
                tools="buscar_classificacao > pesquisar_despesa (2x)",
                observacao=f"Valores de 2023: {v23}. Colunas numéricas contêm os valores de 2024.")

    ids = [id_de("elementos-despesa", 2025, c) for c in ("30", "39")]
    v = total(2025, id_elemento_despesa=ids)
    yield linha("C19", "composta", "Quanto o Estado pagou em material de consumo e serviços de terceiros pessoa "
                "jurídica em 2025?", f"{p(v)} pagos, somando os elementos 30 - MATERIAL DE CONSUMO e "
                "39 - OUTROS SERVICOS DE TERCEIROS - PESSOA JURIDICA em 2025.", "pago", v, tools=BUSCA,
                observacao="Os dois códigos devem ser enviados no mesmo filtro de elementos (operação OU).")

    r = pesquisa(2024, colunas="funcao,valor_empenhado,valor_liquidado,valor_pago")
    funcoes = sorted(agrupar(r["registros"], "funcao").items(), key=lambda x: x[1]["pago"], reverse=True)
    nome, v = funcoes[0]
    yield linha("C20", "composta", "Qual função orçamentária recebeu o maior valor pago em 2024?",
                f"{nome}, com {p(v)} pagos em 2024.", "pago", v,
                tools="pesquisar_despesa (agrupar_por=funcao)",
                observacao=f"Segunda colocada: {funcoes[1][0]} ({p(funcoes[1][1])}).")

    see = id_de("orgaos", 2024, "1261")
    r = pesquisa(2024, colunas="elemento_despesa,valor_empenhado,valor_liquidado,valor_pago", id_orgao=see)
    elementos = sorted(agrupar(r["registros"], "elemento_despesa").items(),
                       key=lambda x: x[1]["pago"], reverse=True)
    nome, v = elementos[0]
    yield linha("C21", "composta", "Qual elemento de despesa teve o maior valor pago pela Secretaria de Educação "
                "em 2024?", f"{nome}, com {p(v)} pagos pela SEE (1261) em 2024.", "pago", v,
                tools="buscar_classificacao > pesquisar_despesa (agrupar_por=elemento)",
                observacao=f"Segundo colocado: {elementos[1][0]} ({p(elementos[1][1])}).")

    h1 = total(2025, "0101", "3006", id_funcao=id_de("funcoes", 2025, "10"))
    h2 = total(2025, "0107", "3112", id_funcao=id_de("funcoes", 2025, "10"))
    yield linha("C22", "composta", "Em qual semestre de 2025 o Estado pagou mais na função Saúde?",
                f"No {'1º' if h1['pago'] > h2['pago'] else '2º'} semestre: {p(h1)} de janeiro a junho e "
                f"{p(h2)} de julho a dezembro.", "pago", h1 if h1["pago"] > h2["pago"] else h2,
                tools="buscar_classificacao > pesquisar_despesa (2x)",
                observacao=f"1º semestre: {h1}; 2º semestre: {h2}.")

    v = total(2024, id_orgao=id_de("orgaos", 2024, "1261"),
              id_funcao=id_de("funcoes", 2024, "12"))
    yield linha("C23", "composta", "Quanto a Secretaria de Educação pagou especificamente na função Educação "
                "em 2024?", f"{p(v)} pagos pela SEE (1261) na função 12 - EDUCACAO em 2024.", "pago", v,
                tools=BUSCA, observacao="Combina dois filtros diferentes (órgão E função).")


def ambiguas():
    casos = [
        ("A14", "Quanto o Estado gastou com transporte?",
         "Pedir o ano e a métrica; esclarecer se é a função 26 - TRANSPORTE ou gastos com veículos e locomoção."),
        ("A15", "Quanto a Educação gastou em 2024?",
         "Esclarecer se é a função Educação, a Secretaria de Educação ou ambos; e se o valor é empenhado, "
         "liquidado ou pago."),
        ("A16", "Quanto foi gasto com hospitais?",
         "Pedir o ano e a métrica; esclarecer se é a subfunção Assistência Hospitalar, a FHEMIG, o Fundo Estadual "
         "de Saúde ou favorecidos hospitalares."),
        ("A17", "Quanto o Estado pagou à Cemig?",
         "Pedir o ano e identificar qual empresa do grupo CEMIG ou se o usuário quer todas elas."),
        ("A18", "Qual órgão mais gastou no ano passado?",
         "Confirmar o ano relativo e a métrica; 'gastou' pode significar empenhado, liquidado ou pago."),
        ("A19", "Quanto foi gasto com tecnologia em 2025?",
         "Esclarecer se o recorte é a subfunção Tecnologia da Informação, o elemento Serviços de TIC ou compras de "
         "empresas como Prodemge."),
        ("A20", "Quanto a segurança gastou no primeiro trimestre?",
         "Pedir o ano e a métrica; esclarecer entre função Segurança Pública e Secretaria de Justiça e Segurança."),
        ("A21", "Quanto foi gasto com pessoal da saúde em 2024?",
         "Esclarecer se deve combinar função Saúde com grupo Pessoal ou considerar somente os órgãos do sistema de "
         "saúde; e qual métrica usar."),
    ]
    for id_, pergunta, resposta in casos:
        yield linha(id_, "ambigua", pergunta, resposta, comportamento="pedir_esclarecimento")


def fora_escopo():
    casos = [
        ("F14", "Quanto Minas Gerais recebeu de transferências da União em 2025?",
         "Recusar: o MCP consulta despesas, não receitas ou transferências recebidas."),
        ("F15", "Quais contratos da Secretaria de Saúde vencem no próximo mês?",
         "Recusar: não há ferramenta de contratos nem de vencimentos."),
        ("F16", "Quantos alunos estão matriculados na rede estadual?",
         "Recusar: a API não contém matrículas ou indicadores educacionais."),
        ("F17", "Qual fornecedor fraudou mais licitações em Minas Gerais?",
         "Recusar: os dados de despesa não permitem concluir fraude, e não há ferramenta de licitações."),
        ("F18", "Quanto o município de Uberlândia pagou em educação em 2024?",
         "Recusar: a API cobre o Estado de Minas Gerais, não municípios."),
        ("F19", "Quanto o governo pretende gastar com saúde em 2027?",
         "Recusar: as ferramentas consultam execução realizada, não planejamento ou previsão futura."),
        ("F20", "Qual foi o impacto dos gastos com segurança na redução da criminalidade?",
         "Recusar ou explicar a limitação: a API fornece despesas, não estatísticas criminais nem causalidade."),
    ]
    for id_, pergunta, resposta in casos:
        yield linha(id_, "fora_escopo", pergunta, resposta, comportamento="recusar")


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    linhas = []
    for gerador in (diretas, compostas, ambiguas, fora_escopo):
        for item in gerador():
            print(item["id"], item["resposta_esperada"][:110])
            linhas.append(item)
    if len(linhas) != 30:
        raise RuntimeError(f"esperadas 30 perguntas, geradas {len(linhas)}")
    with SAIDA.open("w", encoding="utf-8-sig", newline="") as arquivo:
        escritor = csv.DictWriter(arquivo, fieldnames=COLUNAS)
        escritor.writeheader()
        escritor.writerows(linhas)
    print(f"\n{len(linhas)} perguntas em {SAIDA}")


if __name__ == "__main__":
    main()
