"""Testa todos os endpoints descritos em api_consultas_portal_transparencia.yaml.

Autenticacao (uma das opcoes, via variavel de ambiente):
  PT_MG_TOKEN=<bearer token>
  ou PT_MG_CONSUMER_KEY + PT_MG_CONSUMER_SECRET (gera o token via client_credentials)

Uso:
  pip install pyyaml python-dotenv
  python scripts/testar_endpoints.py [--filtro despesas] [--pausa 1.5] [--ano 2025]
  python scripts/testar_endpoints.py --filtro despesas --ano 2025 --salvar-respostas docs/respostas --variacoes
"""
import argparse
import base64
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import yaml
from dotenv import load_dotenv

load_dotenv()
PT_MG_TOKEN = os.environ.get("PT_MG_TOKEN")

YAML_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "docs", "api_consultas_portal_transparencia.yaml")
TOKEN_URL = "https://homologacao.manager.mgapi.prodemge.gov.br/oauth2/token"

ANO = 2026
# Valores padrao enviados quando o endpoint aceita o parametro.
DEFAULTS = {
    "ano": ANO,
    "mes": 6,  # ultimo mes com remuneracao carregada no teste de 25/09/2026
    "limit": 5,
    "page": 1,
}
PERIODO_DDMM = ("0101", "3108")  # despesas / diarias (dia + mes)
PERIODO_MM = ("01", "08")        # receitas

ID_ORGAO = 12264  # "1081 - ADVOCACIA GERAL DO ESTADO" em despesas/lista-orgaos
# Os ids das listas mudam por ano; AGE em cada ano.
ID_ORGAO_POR_ANO = {2025: 12135, 2026: 12264}

# Parametros que precisam de um registro real: {endpoint: {parametro: endpoint anterior que o fornece}}.
ENCADEAR = {
    "/consultas/remuneracao/detalhamento.json": {"hash": "/consultas/remuneracao/individual.json"},
    "/consultas/diarias/individual-documentos.json": {"hash": "/consultas/diarias/individual.json"},
    "/consultas/diarias/individual-detalhamento.json": {"id": "/consultas/diarias/individual-documentos.json"},
    "/consultas/despesas/empenhos/detalhamento.json": {"id_empenho": "/consultas/despesas/empenhos.json"},
    "/consultas/despesas/empenhos/detalhamento/download": {"id_empenho": "/consultas/despesas/empenhos.json"},
}

# Filtros exigidos pelo backend alem dos obrigatorios declarados no YAML.
EXTRAS = {
    "/consultas/despesas/favorecidos.json": {"id_orgao": ID_ORGAO},
    "/consultas/despesas/empenhos.json": {"id_orgao": ID_ORGAO},
    "/consultas/despesas/lista-empenhos.json": {"id_orgao": ID_ORGAO},
    "/consultas/despesas/lista-documentos-pagamento.json": {"id_orgao": ID_ORGAO},
    "/consultas/despesas/lista-favorecidos.json": {"termo": "SIL"},
    "/consultas/diarias/lista-nome-viajante": {"termo": "SILVA"},
    "/consultas/despesas/gerar-csv": {"periodo_fim": "3101"},  # intervalo maximo de 31 dias
}


def configurar(ano, id_orgao, periodo_fim):
    """Ajusta ano, orgao e periodo usados em todas as chamadas."""
    global ANO, ID_ORGAO, PERIODO_DDMM
    ANO, ID_ORGAO, PERIODO_DDMM = ano, id_orgao, ("0101", periodo_fim)
    DEFAULTS["ano"] = ano
    for extras in EXTRAS.values():
        if "id_orgao" in extras:
            extras["id_orgao"] = id_orgao


def variacoes_despesas():
    """Chamadas extras que mostram paginacao, erros e o efeito de colunas/termo."""
    base = {"ano": ANO, "periodo_inicio": PERIODO_DDMM[0], "periodo_fim": PERIODO_DDMM[1]}
    colunas_fav = "favorecido,cnpj_cpf_favorecido,orgao,valor_empenhado,valor_liquidado,valor_pago"
    return [
        ("visao-geral_pagina2", "GET", "/consultas/despesas/visao-geral.json", {**base, "limit": 5, "page": 2}, None),
        ("visao-geral_pagina_inexistente", "GET", "/consultas/despesas/visao-geral.json",
         {**base, "limit": 5, "page": 9999}, None),
        ("favorecidos_sem_colunas", "GET", "/consultas/despesas/favorecidos.json",
         {**base, "id_orgao": ID_ORGAO, "limit": 5, "page": 1}, None),
        ("favorecidos_com_colunas", "GET", "/consultas/despesas/favorecidos.json",
         {**base, "id_orgao": ID_ORGAO, "limit": 5, "page": 1, "colunas": colunas_fav,
          "order_by": "valor_pago", "order_dir": "DESC"}, None),
        ("favorecidos_nome_parcial", "GET", "/consultas/despesas/favorecidos.json",
         {**base, "favorecido": "CEMIG", "limit": 5, "page": 1, "colunas": colunas_fav,
          "order_by": "valor_pago", "order_dir": "DESC"}, None),
        ("empenhos_sem_orgao", "GET", "/consultas/despesas/empenhos.json", {**base, "limit": 5, "page": 1}, None),
        ("programas_com_orgao", "GET", "/consultas/despesas/programas.json",
         {**base, "id_orgao": ID_ORGAO, "limit": 5, "page": 1}, None),
        ("lista-orgaos_termo", "POST", "/consultas/despesas/lista-orgaos.json", None,
         {**base, "termo": "educacao", "limit": 20, "page": 1}),
        ("lista-acoes_termo", "POST", "/consultas/despesas/lista-acoes.json", None,
         {**base, "termo": "alimentacao", "limit": 20, "page": 1}),
        # Ids de 2025: SEE = 12158; acoes 2101 PEAE = 75488 e 2102 PNAE = 75788; elemento 30 MATERIAL DE CONSUMO = 22.
        ("programas_acao_sem_orgao", "GET", "/consultas/despesas/programas.json",
         {**base, "id_acao": 75488, "limit": 5, "page": 1}, None),
        ("programas_orgao_e_acao", "GET", "/consultas/despesas/programas.json",
         {**base, "id_orgao": 12158, "id_acao": 75788, "limit": 5, "page": 1}, None),
        ("empenhos_orgao_e_acao", "GET", "/consultas/despesas/empenhos.json",
         {**base, "id_orgao": 12158, "id_acao": 75788, "limit": 5, "page": 1}, None),
        ("itens-despesa_orgao_e_elemento", "GET", "/consultas/despesas/itens-despesa.json",
         {**base, "id_orgao": 12158, "id_elemento_despesa": 22, "limit": 5, "page": 1}, None),
        ("lista-orgaos_termo_acentuado", "POST", "/consultas/despesas/lista-orgaos.json", None,
         {**base, "termo": "educação", "limit": 20, "page": 1}),
    ]


def extensao_arquivo(ctype, bruto):
    """Extensao para respostas que nao sao JSON (CSV, planilhas, PDF)."""
    ctype = (ctype or "").lower()
    if "csv" in ctype:
        return ".csv"
    if "pdf" in ctype or bruto[:4] == b"%PDF":
        return ".pdf"
    if "spreadsheet" in ctype or "excel" in ctype:
        return ".xlsx"
    if "wordprocessing" in ctype:
        return ".docx"
    if bruto[:2] == b"PK":  # zip generico (xlsx/docx sem content-type claro)
        return ".zip"
    if ctype.startswith("text/"):
        return ".txt"
    return ".bin"


def salvar_resposta(pasta, nome, metodo, url, corpo, status, bruto, ctype=""):
    """Grava requisicao + resposta em <pasta>/<nome>.json.

    Respostas que nao sao JSON vao para <nome><ext> com os bytes originais,
    e o .json guarda so os metadados e o nome desse arquivo.
    """
    if not isinstance(bruto, bytes):
        bruto = str(bruto).encode()
    try:
        resposta = json.loads(bruto)
    except ValueError:
        arquivo = nome + extensao_arquivo(ctype, bruto)
        with open(os.path.join(pasta, arquivo), "wb") as f:
            f.write(bruto)
        resposta = {"arquivo": arquivo, "content_type": ctype, "bytes": len(bruto)}
    registro = {"requisicao": {"metodo": metodo, "url": url, "corpo": corpo},
                "status": status, "content_type": ctype, "resposta": resposta}
    with open(os.path.join(pasta, nome + ".json"), "w", encoding="utf-8") as f:
        json.dump(registro, f, ensure_ascii=False, indent=2)


def nome_arquivo(path, metodo):
    nome = path.replace("/consultas/", "", 1).strip("/").replace("/", "__").replace(".json", "")
    return f"{nome}_{metodo.lower()}"


def obter_token():
    token = os.environ.get("PT_MG_TOKEN")
    if token:
        return token
    key, secret = os.environ.get("PT_MG_CONSUMER_KEY"), os.environ.get("PT_MG_CONSUMER_SECRET")
    if not (key and secret):
        sys.exit("Defina PT_MG_TOKEN ou PT_MG_CONSUMER_KEY/PT_MG_CONSUMER_SECRET.")
    auth = base64.b64encode(f"{key}:{secret}".encode()).decode()
    req = urllib.request.Request(
        TOKEN_URL,
        data=b"grant_type=client_credentials",
        headers={"Authorization": f"Basic {auth}", "Content-Type": "application/x-www-form-urlencoded"},
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)["access_token"]


def achar_valor(obj, chaves):
    """Procura recursivamente o primeiro valor nao vazio de uma das chaves."""
    if isinstance(obj, dict):
        for k in chaves:
            if obj.get(k) not in (None, ""):
                return obj[k]
        for v in obj.values():
            achado = achar_valor(v, chaves)
            if achado is not None:
                return achado
    elif isinstance(obj, list):
        for v in obj:
            achado = achar_valor(v, chaves)
            if achado is not None:
                return achado
    return None


def montar_parametros(path, params, respostas):
    nomes = {p["name"]: p for p in params}
    periodo = PERIODO_MM if "/receitas/" in path else PERIODO_DDMM
    valores, faltando = {}, []
    for nome, p in nomes.items():
        if nome in DEFAULTS:
            valores[nome] = DEFAULTS[nome]
        elif nome == "periodo_inicio":
            valores[nome] = periodo[0]
        elif nome == "periodo_fim":
            valores[nome] = periodo[1]
        elif nome == "tipo" and p.get("enum"):
            valores[nome] = p["enum"][0]
        elif nome == "tipo":
            valores[nome] = "despesas"
        elif nome in ENCADEAR.get(path, {}) and achar_valor(respostas.get(ENCADEAR[path][nome]), [nome]) is not None:
            valores[nome] = achar_valor(respostas[ENCADEAR[path][nome]], [nome])
        elif p.get("required"):
            faltando.append(nome)
    for nome, valor in EXTRAS.get(path, {}).items():
        if nome in nomes:
            valores[nome] = valor
    return valores, [n for n in faltando if n not in valores]


def chamar(metodo, url, token, corpo=None, tentativas=2):
    # O firewall do gateway bloqueia (403) o User-Agent padrao do urllib.
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/json", "User-Agent": "testar-endpoints/1.0"}
    data = None
    if corpo is not None:
        data = json.dumps(corpo).encode()
        headers["Content-Type"] = "application/json"
    for tentativa in range(tentativas):
        inicio = time.time()
        try:
            req = urllib.request.Request(url, data=data, headers=headers, method=metodo)
            with urllib.request.urlopen(req, timeout=60) as r:
                bruto = r.read()
                return r.status, r.headers.get("Content-Type", ""), bruto, time.time() - inicio
        except urllib.error.HTTPError as e:
            return e.code, e.headers.get("Content-Type", ""), e.read(), time.time() - inicio
        except Exception as e:  # timeout, conexao
            if tentativa == tentativas - 1:
                return None, "", str(e).encode(), time.time() - inicio
            time.sleep(5)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--filtro", default="", help="Testa so caminhos que contem este texto")
    ap.add_argument("--pausa", type=float, default=1.5, help="Segundos entre chamadas (evita rate limit)")
    ap.add_argument("--saida", default="resultado_testes_endpoints.json")
    ap.add_argument("--ano", type=int, default=ANO)
    ap.add_argument("--id-orgao", type=int, help="Padrao: AGE no ano escolhido (ID_ORGAO_POR_ANO)")
    ap.add_argument("--periodo-fim", help="DDMM. Padrao: 3112 para anos fechados, 3108 para o ano corrente")
    ap.add_argument("--salvar-respostas", metavar="PASTA", help="Grava o JSON completo de cada chamada nesta pasta")
    ap.add_argument("--variacoes", action="store_true", help="Faz tambem as chamadas extras de despesas")
    ap.add_argument("--so-variacoes", action="store_true", help="Faz apenas as chamadas extras de despesas")
    args = ap.parse_args()

    id_orgao = args.id_orgao or ID_ORGAO_POR_ANO.get(args.ano)
    if id_orgao is None:
        sys.exit(f"Sem id de orgao conhecido para {args.ano}; informe --id-orgao.")
    configurar(args.ano, id_orgao, args.periodo_fim or ("3108" if args.ano >= 2026 else "3112"))
    if args.salvar_respostas:
        os.makedirs(args.salvar_respostas, exist_ok=True)

    spec = yaml.safe_load(open(YAML_FILE, encoding="utf-8"))
    base = "https://" + spec["host"] + spec["basePath"]
    token = obter_token()
    respostas, resultados = {}, []

    for path, ops in spec["paths"].items():
        if args.so_variacoes or args.filtro not in path:
            continue
        for metodo, op in ops.items():
            params = op.get("parameters", [])
            query_params = [p for p in params if p.get("in") == "query"]
            body_param = next((p for p in params if p.get("in") == "body"), None)
            valores, faltando = montar_parametros(path, query_params, respostas)
            corpo = None
            if body_param:
                props = body_param.get("schema", {}).get("properties", {})
                obrig = body_param.get("schema", {}).get("required", [])
                corpo, faltando_corpo = montar_parametros(
                    path, [{"name": n, "required": n in obrig} for n in props], respostas)
                faltando += faltando_corpo

            if faltando:
                res = {"metodo": metodo.upper(), "path": path, "status": "PULADO",
                       "obs": "sem valor para parametro obrigatorio: " + ", ".join(faltando)}
            else:
                url = base + path + ("?" + urllib.parse.urlencode(valores) if valores else "")
                status, ctype, bruto, dur = chamar(metodo.upper(), url, token, corpo)
                if args.salvar_respostas:
                    salvar_resposta(args.salvar_respostas, nome_arquivo(path, metodo),
                                    metodo.upper(), url, corpo, status, bruto, ctype)
                obs = ""
                if "json" in ctype:
                    try:
                        dados = json.loads(bruto)
                        if status == 200:
                            respostas[path] = dados
                        obs = json.dumps(dados, ensure_ascii=False)[:160]
                    except ValueError:
                        obs = "JSON truncado/invalido (resposta grande)"
                else:
                    obs = f"{ctype} {bruto[:120]!r}"
                res = {"metodo": metodo.upper(), "path": path, "status": status, "tempo_s": round(dur, 1),
                       "url": url, "corpo": corpo, "obs": obs}
                time.sleep(args.pausa)
            resultados.append(res)
            print(f"{str(res['status']):>7}  {res['metodo']:<5} {path}  {res.get('obs', '')[:90]}")

    if args.variacoes or args.so_variacoes:
        print("\nVariacoes de despesas:")
        for nome, metodo, path, params, corpo in variacoes_despesas():
            url = base + path + ("?" + urllib.parse.urlencode(params) if params else "")
            status, ctype, bruto, dur = chamar(metodo, url, token, corpo)
            if args.salvar_respostas:
                salvar_resposta(args.salvar_respostas, "variacao_" + nome, metodo, url, corpo, status, bruto, ctype)
            obs = bruto[:160].decode("utf-8", "replace") if isinstance(bruto, bytes) else str(bruto)[:160]
            resultados.append({"metodo": metodo, "path": path, "variacao": nome, "status": status,
                               "tempo_s": round(dur, 1), "url": url, "corpo": corpo, "obs": obs})
            print(f"{str(status):>7}  {metodo:<5} {nome}  {obs[:90]}")
            time.sleep(args.pausa)

    with open(args.saida, "w", encoding="utf-8") as f:
        json.dump(resultados, f, ensure_ascii=False, indent=2)
    ok = sum(1 for r in resultados if r["status"] in (200, 204))
    print(f"\n{ok}/{len(resultados)} com 200/204. Detalhes em {args.saida}")


if __name__ == "__main__":
    main()
