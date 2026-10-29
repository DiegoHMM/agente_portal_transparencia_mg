"""Confere o client.py contra a API real, com valores de referência do avaliacao/eval.csv.

Precisa de PT_MG_BASIC_AUTH (ou PT_MG_CONSUMER_KEY + PT_MG_CONSUMER_SECRET) no .env.

Uso:
  python mcp_portal_transparencia/verificar_api.py
"""
import sys
import time

import client

P2025 = {"ano": 2025, "periodo_inicio": "0101", "periodo_fim": "3112"}
falhas = []


def conferir(nome, ok, detalhe=""):
    print(f"[{'OK' if ok else 'FALHOU'}] {nome} {detalhe}")
    if not ok:
        falhas.append(nome)


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    try:
        t = client.consultar("/consultas/despesas/visao-geral.json", {**P2025, "limit": 1})["totais"]
    except client.ErroAPI as e:
        sys.exit(f"Nao foi possivel acessar a API: {e}")
    conferir("token", client._token["valor"] is not None or bool(client.os.getenv("PT_MG_TOKEN")))
    conferir("D01 total pago 2025", round(t["pago"], 2) == 125459430296.87, f"({t['pago']:,.2f})")

    acoes = client.lista("acoes", 2025, "alimentação escolar")
    conferir("busca com acento acha PEAE e PNAE", {a["id"] for a in acoes} == {75488, 75788},
             str([a["nome"] for a in acoes]))
    inicio = time.time()
    client.lista("acoes", 2025, "saude")
    conferir("segunda busca usa cache", time.time() - inicio < 0.5)

    soma = sum(client.consultar("/consultas/despesas/programas.json", {**P2025, "id_acao": a["id"], "limit": 1})
               ["totais"]["pago"] for a in acoes)
    conferir("C01 merenda pago 2025", round(soma, 2) == 704838856.29, f"({soma:,.2f})")

    try:
        client.consultar("/consultas/despesas/empenhos.json", {**P2025, "limit": 1})
        conferir("empenhos sem orgao gera erro", False)
    except client.ErroAPI as e:
        conferir("empenhos sem orgao gera erro com mensagem", e.status == 500 and "Órgão" in e.mensagem)

    conferir("anos disponiveis", client.anos_disponiveis()[:1] == [2021])
    secoes = set(client.detalhar_empenho(17352862, 2025))
    conferir("detalhamento de empenho", {"empenho", "liquidacao", "pagamento"} <= secoes)

    r = client.consultar_todas("/consultas/despesas/visao-geral.json", P2025, limit=30)
    conferir("paginacao completa", len(r["linhas"]) == r["qt"] and not r["truncado"],
             f"({len(r['linhas'])} de {r['qt']})")

    print(f"\n{'Tudo certo.' if not falhas else f'{len(falhas)} falha(s): ' + ', '.join(falhas)}")
    sys.exit(1 if falhas else 0)


if __name__ == "__main__":
    main()
