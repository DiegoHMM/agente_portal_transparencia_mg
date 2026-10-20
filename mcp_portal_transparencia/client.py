import base64, os, time, unicodedata
from functools import lru_cache
from pathlib import Path
import httpx
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

BASE_URL = os.getenv("PT_MG_BASE_URL",
    "https://homologacao.apigw.mgapi.prodemge.gov.br/portaltransparencia/1.0.0")
TOKEN_URL = os.getenv("PT_MG_TOKEN_URL",
    "https://homologacao.manager.mgapi.prodemge.gov.br/oauth2/token")
USER_AGENT = "mcp-portal-transparencia/0.1"

class ErroAPI(Exception):
    def __init__(self, status, mensagem, endpoint):
        super().__init__(f"{endpoint}: HTTP {status}: {mensagem}")
        self.status, self.mensagem, self.endpoint = status, mensagem, endpoint

def _credencial_basic() -> str:
    """base64(key:secret). Aceita PT_MG_BASIC_AUTH (valor pronto do portal) ou key + secret."""
    pronto = os.getenv("PT_MG_BASIC_AUTH", "").strip().removeprefix("Basic ").strip()
    if pronto:
        return pronto
    key, secret = os.getenv("PT_MG_CONSUMER_KEY"), os.getenv("PT_MG_CONSUMER_SECRET")
    if not (key and secret):
        raise ErroAPI(None, "defina PT_MG_BASIC_AUTH ou PT_MG_CONSUMER_KEY + PT_MG_CONSUMER_SECRET no .env",
                      TOKEN_URL)
    return base64.b64encode(f"{key}:{secret}".encode()).decode()

def _obter_token(forcar=False) -> str:
    if os.getenv("PT_MG_TOKEN"):
        return os.environ["PT_MG_TOKEN"]
    if not forcar and _token["valor"] and time.time() < _token["expira"] - 60:
        return _token["valor"]
    r = httpx.post(TOKEN_URL, data={"grant_type": "client_credentials"},
                   headers={"Authorization": f"Basic {_credencial_basic()}", "User-Agent": USER_AGENT},
                   timeout=30)
    r.raise_for_status()
    dados = r.json()
    _token.update(valor=dados["access_token"], expira=time.time() + dados.get("expires_in", 3600))
    return _token["valor"]

def _requisitar(metodo, path, params=None, corpo=None, tentativas=3):
    for tentativa in range(tentativas):
        try:
            r = _http.request(metodo, path, params=params, json=corpo,
                              headers={"Authorization": f"Bearer {_obter_token()}"})
        except (httpx.TimeoutException, httpx.TransportError):
            if tentativa == tentativas - 1:
                raise ErroAPI(None, "sem resposta da API", path)
            time.sleep(2 ** tentativa)
            continue
        if r.status_code == 401 and tentativa == 0:
            _obter_token(forcar=True)
            continue
        if r.status_code != 200:
            raise ErroAPI(r.status_code, _mensagem_de_erro(r), path)
        return r.json()

def _mensagem_de_erro(r):
    if r.status_code == 403:  # firewall do gateway responde com pagina HTML
        return "requisicao bloqueada pelo gateway (acento no corpo ou User-Agent nao aceito)"
    if r.status_code == 401:
        return "token recusado; se PT_MG_TOKEN estiver definido, ele pode ter expirado"
    try:
        dados = r.json()
    except ValueError:
        return r.text[:300] or "resposta vazia"
    return (dados.get("message") if isinstance(dados, dict) else None) or r.text[:300]



def consultar(path, params) -> dict:
    """Uma página. path como no swagger (ex. "/consultas/despesas/programas.json").
    Devolve {"totais", "linhas", "qt"}."""
    if path not in ESTRUTURA:
        raise ValueError(f"endpoint sem estrutura conhecida: {path}. Use um de: {', '.join(ESTRUTURA)}")
    chave_linhas, chave_qt = ESTRUTURA[path]
    data = _requisitar("GET", path, params=params)["data"]
    totais = {k.removeprefix("total_"): v for k, v in data.items() if k.startswith("total_")}
    return {"totais": totais, "linhas": data.get(chave_linhas, []), "qt": data.get(chave_qt, 0)}

def consultar_todas(path, params, limit=100, max_paginas=50) -> dict:
    """Todas as páginas, parando na lista vazia ou quando já leu qt linhas."""
    primeira = consultar(path, {**params, "limit": limit, "page": 1})
    linhas = list(primeira["linhas"])
    page = 2
    while linhas and len(linhas) < primeira["qt"] and page <= max_paginas:
        lote = consultar(path, {**params, "limit": limit, "page": page})["linhas"]
        if not lote:
            break
        linhas += lote
        page += 1
    return {**primeira, "linhas": linhas, "truncado": len(linhas) < primeira["qt"]}


def sem_acento(texto: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", texto) if unicodedata.category(c) != "Mn")

def _normalizar_item(r: dict) -> dict:
    id_ = next(r[k] for k in ("id", "id_orgao", "id_acao", "id_programa",
                              "id_elemento_despesa", "id_item_despesa", "id_favorecido") if k in r)
    nome = " ".join(str(r.get("nome_acao") or r.get("nome_programa") or r.get("nome") or "").split())
    # "is not None" e nao "or": ha codigos 0 validos (ex. lista-ipu)
    codigo = next((r[k] for k in ("codigo", "codigo_acao", "codigo_programa") if r.get(k) is not None), None)
    if codigo is None and " - " in nome:   # "1081 - ADVOCACIA GERAL DO ESTADO"
        codigo = nome.split(" - ", 1)[0]
    return {"id": id_, "codigo": None if codigo is None else str(codigo).strip(), "nome": nome}


LISTAS_PEQUENAS = {"orgaos", "unidades", "programas", "acoes", "funcoes", "subfuncoes",
                   "elementos-despesa", "itens-despesa", "categorias-economicas",
                   "grupos-despesa", "modalidades-aplicacao", "fontes-recurso"}

@lru_cache(maxsize=128)
def _lista_completa(tipo: str, ano: int) -> tuple:
    corpo = {"ano": ano, "periodo_inicio": "0101", "periodo_fim": "3112", "limit": 100}
    itens, page = [], 1
    while True:
        data = _requisitar("POST", f"/consultas/despesas/lista-{tipo}.json",
                           corpo={**corpo, "page": page})["data"]
        itens += data["registros"]
        if not data["registros"] or len(itens) >= data["total"]:
            break
        page += 1
    return tuple(_normalizar_item(r) for r in itens)

def lista(tipo: str, ano: int, termo: str | None = None) -> list[dict]:
    if tipo in LISTAS_PEQUENAS:
        itens = _lista_completa(tipo, ano)
        # copias, para quem chamar nao alterar o cache
        if not termo:
            return [dict(i) for i in itens]
        alvo = sem_acento(termo).upper()
        return [dict(i) for i in itens if alvo in sem_acento(i["nome"]).upper()]
    corpo = {"ano": ano, "periodo_inicio": "0101", "periodo_fim": "3112",
             "termo": sem_acento(termo or ""), "limit": 50, "page": 1}
    data = _requisitar("POST", f"/consultas/despesas/lista-{tipo}.json", corpo=corpo)["data"]
    return [_normalizar_item(r) for r in data["registros"]]

def detalhar_empenho(id_empenho: int, ano: int) -> dict:
    return _requisitar("GET", "/consultas/despesas/empenhos/detalhamento.json",
                       params={"id_empenho": id_empenho, "ano": ano})["data"]

def anos_disponiveis() -> list[int]:
    return _requisitar("GET", "/consultas/despesas/lista-periodo.json")["data"][0]


PESQUISA = "/consultas/despesas/pesquisa-avancada.json"

def pesquisa_avancada(filtros: dict, colunas: str | None = None, max_paginas=20) -> dict:
    """Todas as páginas da pesquisa avançada (nível 1). ano e período devem ser escalares."""
    corpo = {"nivel": 1, "filtros": filtros, "limit": 100, "page": 1}
    if colunas:
        corpo["colunas"] = colunas
    data = _requisitar("POST", PESQUISA, corpo=corpo)["data"]
    registros = list(data["registros"])
    while corpo["page"] < min(data["total_paginas"], max_paginas):
        corpo["page"] += 1
        registros += _requisitar("POST", PESQUISA, corpo=corpo)["data"]["registros"]
    return {"totais": data["totais"], "registros": registros,
            "truncado": data["total_paginas"] > max_paginas}



_token = {"valor": None, "expira": 0.0}

_http = httpx.Client(base_url=BASE_URL, timeout=60, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})

ESTRUTURA = {  # path (como no swagger) -> (chave das linhas, chave da contagem)
    "/consultas/despesas/visao-geral.json":   ("orgaos", "qt_orgaos"),
    "/consultas/despesas/programas.json":     ("programas", "qt_programas"),
    "/consultas/despesas/itens-despesa.json": ("itens_despesa", "qt_itens_despesa"),
    "/consultas/despesas/empenhos.json":      ("empenhos", "qt_empenhos"),
    "/consultas/despesas/favorecidos.json":   ("registros", "qt_registros"),
}