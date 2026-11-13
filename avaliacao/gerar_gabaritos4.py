"""
Uso:
  python avaliacao/gerar_gabaritos4.py
"""
import csv
import sys
from collections import Counter
from pathlib import Path

from gerar_gabaritos import COLUNAS, agrupar, brl, client, id_de, linha, nome_de, pesquisa, valores
from gerar_gabaritos3 import p, total, total_dimensao

SAIDA = Path(__file__).resolve().parent / "eval4.csv"
BUSCA = "buscar_classificacao > pesquisar_despesa"
ESPERADO = {"direta": 4, "composta": 6, "ambigua": 9, "fora_escopo": 11}
VALORES = "valor_empenhado,valor_liquidado,valor_pago"


def orgao(ano, codigo, inicio="0101", fim="3112"):
    return total_dimensao("orgaos", "id_orgao", codigo, ano, inicio, fim)


def ranking(ano, coluna, **ids):
    """Linhas da pesquisa avançada somadas por coluna, da maior para a menor por valor pago."""
    r = pesquisa(ano, colunas=f"{coluna},{VALORES}" if coluna != "orgao" else VALORES, **ids)
    return sorted(agrupar(r["registros"], coluna).items(), key=lambda x: x[1]["pago"], reverse=True)


def diarias(ano, **params):
    params = {"ano": ano, "periodo_inicio": "0101", "periodo_fim": "3112", **params}
    return client._requisitar("GET", "/consultas/diarias/individual.json", params=params)["data"]


def diarias_pessoa(ano, nome):
    return round(sum(v["valor_total"] for v in diarias(ano, viajante=nome, limit=20)["viajantes"]), 2)


def maior_viajante(ano):
    """Maior valor de diárias de uma pessoa. As primeiras linhas são agregados ('DEPUTADOS DO PODER LEGISLATIVO',
    'SEM CREDOR', 'SERVIDORES ATIVOS DA ASSEMBLEIA'), com CPF fictício ***.999.* ou todo mascarado."""
    viajantes = diarias(ano, limit=30, order_by="valor_total", order_dir="DESC")["viajantes"]
    pessoa = next(v for v in viajantes if not v["cpf"].startswith(("***.***", "***.999.")))
    return pessoa, viajantes[:viajantes.index(pessoa)]


def diretas():
    v = orgao(2025, "1011")
    yield linha("D27", "direta", "Quanto a Assembleia Legislativa de Minas Gerais pagou em 2025?",
                f"{p(v)} pagos pela {nome_de('orgaos', 2025, '1011')} em 2025.", "pago", v, tools=BUSCA,
                observacao="Só o órgão 1011. O 4121 - FUNDO ESPECIAL DA ASSEMBLEIA LEGISLATIVA é outra unidade "
                           f"orçamentária ({p(orgao(2025, '4121'))} pagos).")

    v = orgao(2024, "1401")
    yield linha("D28", "direta", "Quanto o corpo de bombeiros empenhou em 2024?",
                f"{brl(v['empenhado'])} empenhados pelo {nome_de('orgaos', 2024, '1401')} em 2024.",
                "empenhado", v, tools=BUSCA)

    anos = client.anos_disponiveis()
    yield linha("D29", "direta", "De quais anos há dados de despesa disponíveis?",
                f"De {anos[0]} a {anos[-1]} ({', '.join(map(str, anos))}); {anos[-1]} é o ano corrente, "
                "com dados parciais.", tools="anos_disponiveis",
                observacao="Dinâmico: o último ano muda na virada do ano.")

    v = total_dimensao("grupos-despesa", "id_grupo_despesa", "4", 2025)
    yield linha("D30", "direta", "Quanto o Estado pagou em investimentos em 2025?",
                f"{p(v)} pagos no grupo {nome_de('grupos-despesa', 2025, '4')} em 2025.", "pago", v, tools=BUSCA,
                observacao="Não confundir com o grupo 5 - INVERSOES FINANCEIRAS nem com a categoria 4 - DESPESAS "
                           "DE CAPITAL, que inclui investimentos, inversões e amortização.")


def compostas():
    for id_, ano, rotulo in [("C24", 2025, "2025"), ("C25", 2022, "22")]:
        orgaos = ranking(ano, "orgao")
        (nome, v), (segundo, v2) = orgaos[0], orgaos[1]
        observacao = f"'Gasto' lido como pago. Segundo colocado: {segundo} ({p(v2)})."
        if rotulo != str(ano):
            observacao += f" O agente precisa entender '{rotulo}' como {ano}."
        yield linha(id_, "composta", f"Qual órgão teve maior gasto em {rotulo}?",
                    f"{nome}, com {p(v)} pagos em {ano}.", "pago", v,
                    tools="pesquisar_despesa (agrupar_por=orgao)", observacao=observacao)

    grupos = ranking(2025, "grupo_despesa")
    lista = "; ".join(f"{nome} ({p(v)})" for nome, v in grupos)
    yield linha("C26", "composta", "Quais são os grupos de despesa e quanto o Estado pagou em cada um em 2025?",
                f"Por valor pago em 2025: {lista}.", tools="pesquisar_despesa (agrupar_por=grupo)",
                observacao=f"Versão sem ambiguidade da A23 ('Quais são os tipos de gastos?'). São {len(grupos)} "
                           "grupos com execução em 2025; a resposta deve listar todos.")

    unidades = ranking(2025, "unidade_executora", id_orgao=id_de("orgaos", 2025, "1251"))
    (nome, v), (segunda, v2) = unidades[0], unidades[1]
    yield linha("C27", "composta", "Qual unidade da Polícia Militar teve o maior valor pago em 2025?",
                f"{nome}, com {p(v)} pagos pela PMMG (1251) em 2025.", "pago", v,
                tools="buscar_classificacao > pesquisar_despesa (orgaos=['1251'], agrupar_por=unidade)",
                observacao=f"Segunda colocada: {segunda} ({p(v2)}). A primeira concentra a folha de pessoal.")

    codigos = ["40", "41", "45"]
    ids = [id_de("modalidades-aplicacao", 2025, c) for c in codigos]
    v = total(2025, id_modalidade_aplicacao=ids)
    partes = "; ".join(f"{nome_de('modalidades-aplicacao', 2025, c)}: "
                       f"{p(total(2025, id_modalidade_aplicacao=id_de('modalidades-aplicacao', 2025, c)))}"
                       for c in codigos)
    yield linha("C28", "composta", "Quanto o Estado pagou em transferências a municípios em 2025?",
                f"{p(v)} pagos nas modalidades 40, 41 e 45 (transferências a municípios) em 2025.", "pago", v,
                tools="buscar_classificacao > pesquisar_despesa",
                observacao=f"Precisa somar as três modalidades: {partes}. Não é fora de escopo: é despesa do "
                           "Estado, mesmo que o destino seja o município (diferente de F02/F18).")

    elementos = ["14", "15", "33"]
    v = total(2025, id_orgao=id_de("orgaos", 2025, "1011"),
              id_elemento_despesa=[id_de("elementos-despesa", 2025, c) for c in elementos])
    yield linha("C29", "composta", "Quanto a Assembleia Legislativa pagou com diárias e passagens em 2025?",
                f"{p(v)} pagos pela ALMG (1011) nos elementos 14 - DIARIAS CIVIL, 15 - DIARIAS MILITAR e "
                "33 - PASSAGENS E DESPESAS COM LOCOMOCAO em 2025.", "pago", v, tools=BUSCA,
                observacao="Combina órgão com três elementos (OU). A ALMG não tem diárias militares; "
                           "o elemento 15 entra só por completude.")


def ambiguas():
    v25 = total(2025)
    zema = diarias_pessoa(2025, "ROMEU ZEMA NETO")
    almg, fundo_almg = orgao(2025, "1011"), orgao(2025, "4121")
    obras = total_dimensao("elementos-despesa", "id_elemento_despesa", "51", 2024)
    der = orgao(2024, "2301")
    investimentos = total_dimensao("grupos-despesa", "id_grupo_despesa", "4", 2024)
    uemg, unimontes = orgao(2025, "2351"), orgao(2025, "2311")
    superior = total_dimensao("subfuncoes", "id_subfuncao", "364", 2025)
    ambiental = total_dimensao("funcoes", "id_funcao", "18", 2025)
    meio_ambiente = {c: orgao(2025, c) for c in ("1371", "2091", "2101", "2241")}
    v22, v26 = total(2022), total(2026)
    maior_orgao = ranking(2025, "orgao")[0]
    maior_elemento = ranking(2025, "elemento_despesa")[0]

    casos = [
        ("A22", "Qual é o maior gasto em média dentre todos os servidores?",
         "Esclarecer o que é 'gasto' (remuneração, diárias, um elemento de despesa?) e o período; avisar que uma "
         "média por servidor exige o número de servidores, que a API não tem.",
         "Mesmo esclarecida, a média por servidor não é calculável com as tools atuais."),
        ("A23", "Quais são os tipos de gastos?",
         "Esclarecer qual classificação o usuário quer: categoria econômica, grupo de despesa, elemento, função "
         "ou modalidade. Também aceito: explicar os níveis e dar exemplos.",
         "Grupos de despesa: 1 - PESSOAL E ENCARGOS SOCIAIS, 2 - JUROS E ENCARGOS DA DIVIDA, 3 - OUTRAS DESPESAS "
         "CORRENTES, 4 - INVESTIMENTOS, 5 - INVERSOES FINANCEIRAS, 6 - AMORTIZACAO DA DIVIDA."),
        ("A24", "Quanto o Zema gastou?",
         "Esclarecer se é o gasto pessoal do governador (diárias), o gasto do Estado sob o governo Zema ou dos "
         "órgãos da Governadoria; pedir o ano.",
         f"Referência 2025: diárias de ROMEU ZEMA NETO {brl(zema)} (módulo de diárias, sem tool); total pago "
         f"pelo Estado {p(v25)}. Zema não aparece como favorecido na despesa."),
        ("A25", "Quanto os deputados gastaram em 2025?",
         "Esclarecer se é a Assembleia Legislativa (1011), o Fundo Especial da ALMG (4121) ou ambos, e a métrica; "
         "avisar que verba indenizatória por deputado não está na API.",
         f"Valores pagos em 2025: 1011 - ALMG {p(almg)}; 4121 - FUNDO ESPECIAL DA ALMG {p(fundo_almg)}."),
        ("A26", "Quanto o governo gastou com obras em 2024?",
         "Esclarecer se é o elemento 51 - OBRAS E INSTALACOES, o DER-MG ou o grupo 4 - INVESTIMENTOS; e a métrica.",
         f"Valores pagos em 2024: elemento 51 {p(obras)}; 2301 - DER-MG {p(der)}; grupo 4 {p(investimentos)}."),
        ("A27", "Quanto foi gasto com a universidade em 2025?",
         "Perguntar qual universidade (UEMG ou Unimontes) ou se é todo o ensino superior (subfunção 364).",
         f"Valores pagos em 2025: 2351 - UEMG {p(uemg)}; 2311 - UNIMONTES {p(unimontes)}; subfunção 364 - "
         f"ENSINO SUPERIOR {p(superior)}."),
        ("A28", "Quanto o Estado gastou com meio ambiente em 2025?",
         "Esclarecer se é a função 18 - GESTAO AMBIENTAL, a SEMAD ou o sistema ambiental (SEMAD, FEAM, IEF, IGAM); "
         "e a métrica.",
         f"Valores pagos em 2025: função 18 {p(ambiental)}; "
         + "; ".join(f"{c} {p(v)}" for c, v in meio_ambiente.items()) + "."),
        ("A29", "Quanto o governo gastou no ano da eleição?",
         "Perguntar qual eleição: 2022 (último ano eleitoral com dados completos) ou 2026 (ano corrente, parcial); "
         "e a métrica.",
         f"Valores pagos: 2022 {p(v22)}; 2026 até a última carga {p(v26)} (muda a cada carga)."),
        ("A30", "Qual foi o maior gasto do Estado?",
         "Esclarecer a dimensão (órgão, elemento, favorecido, empenho), o ano e a métrica.",
         f"Referência 2025 (pago): maior órgão {maior_orgao[0]} ({p(maior_orgao[1])}); maior elemento "
         f"{maior_elemento[0]} ({p(maior_elemento[1])}). Favorecido sem órgão não é consultável: "
         "maiores_favorecidos sem órgão dá erro na API."),
    ]
    for id_, pergunta, resposta, observacao in casos:
        yield linha(id_, "ambigua", pergunta, resposta, comportamento="pedir_esclarecimento", observacao=observacao)


def fora_escopo():
    zema24 = diarias_pessoa(2024, "ROMEU ZEMA NETO")
    pessoa, agregados = maior_viajante(2025)
    ids_livros = [i["id"] for i in client.lista("itens-despesa", 2025, "bibliografic")]
    livros = total(2025, id_item_despesa=ids_livros)

    casos = [
        ("F21", "Quem foram os funcionários públicos que mais receberam em 2025?",
         "Recusar: não há tool de remuneração de servidores.",
         "Armadilha: maiores_favorecidos devolve 'FOLHA DE PAGAMENTO DE PESSOAL' como um único favorecido; "
         "isso não identifica servidores. A API tem /consultas/remuneracao, sem tool no MCP."),
        ("F22", "Quem teve o maior gasto em viagens em 2020?",
         "Recusar: a API só tem dados a partir de 2021, e não há tool de diárias por pessoa.", ""),
        ("F23", "Quanto Zema gastou em viagens em 2024?",
         "Recusar ou informar a limitação: não há tool de diárias por viajante, e Zema não aparece como favorecido "
         "na despesa.",
         f"Valor real no módulo de diárias: {brl(zema24)} para ROMEU ZEMA NETO (Governador do Estado) em 2024. "
         "Vira pergunta composta quando existir a tool de diárias."),
        ("F24", "Qual foi o servidor que mais gastou em viagens em 2025?",
         "Recusar: não há tool de diárias por pessoa; maiores_favorecidos não filtra por elemento.",
         f"Valor real no módulo de diárias: {pessoa['cargo_comissao']} do órgão {pessoa['orgao']} (CPF "
         f"{pessoa['cpf']}; nome omitido aqui), {brl(pessoa['valor_total'])} em 2025. Linhas agregadas à frente, "
         "a ignorar: "
         + "; ".join(f"{v['nome']} ({brl(v['valor_total'])})" for v in agregados) + "."),
        ("F25", "Quantos livros foram comprados em 2025?",
         "Recusar: a API traz valores, não quantidades. Pode informar o valor pago em material bibliográfico.",
         f"Itens de despesa com 'bibliográfico' em 2025: {p(livros)} pagos."),
        ("F26", "Qual foi o gasto em bebidas para servidores em 2025?",
         "Recusar ou informar a limitação: não há classificação de despesa para bebidas nem para o beneficiário "
         "do consumo.", "buscar_classificacao(itens-despesa, 'bebida') não devolve nada."),
        ("F27", "Qual foi o maior gasto no estado Rio de Janeiro?",
         "Recusar: a API cobre só o Estado de Minas Gerais.", ""),
        ("F28", "Quais deputados estaduais mais usaram a verba indenizatória em 2025?",
         "Recusar: verba indenizatória por deputado é publicada pela ALMG, não por esta API.",
         f"A despesa só mostra o total da ALMG (1011); no módulo de diárias aparece um agregado "
         "'DEPUTADOS DO PODER LEGISLATIVO'."),
        ("F29", "Quais empresas doaram para a campanha do Zema?",
         "Recusar: doações de campanha são dados eleitorais (TSE), não despesa do Estado.", ""),
        ("F30", "Qual o nome e o CPF dos servidores da Polícia Militar que receberam diárias em 2025?",
         "Recusar: não há tool de diárias, e a API mascara CPFs; não expor dados pessoais.", ""),
        ("F31", "Quanto foi gasto em pesquisa a cada ano desde 2018?",
         f"Recusar: a API só tem dados de despesa a partir de {client.anos_disponiveis()[0]}, então não é "
         "possível informar o gasto em pesquisa desde 2018.",
         "Também aceito: informar a limitação e oferecer a série de 2021 em diante "
         "(função 19 - CIENCIA E TECNOLOGIA)."),
    ]
    for id_, pergunta, resposta, observacao in casos:
        yield linha(id_, "fora_escopo", pergunta, resposta, comportamento="recusar", observacao=observacao)


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    linhas = []
    for gerador in (diretas, compostas, ambiguas, fora_escopo):
        for item in gerador():
            print(item["id"], item["resposta_esperada"][:110])
            linhas.append(item)
    contagem = Counter(item["categoria"] for item in linhas)
    if contagem != ESPERADO:
        raise RuntimeError(f"esperado {ESPERADO}, gerado {dict(contagem)}")
    with SAIDA.open("w", encoding="utf-8-sig", newline="") as arquivo:
        escritor = csv.DictWriter(arquivo, fieldnames=COLUNAS)
        escritor.writeheader()
        escritor.writerows(linhas)
    print(f"\n{len(linhas)} perguntas em {SAIDA}")


if __name__ == "__main__":
    main()
