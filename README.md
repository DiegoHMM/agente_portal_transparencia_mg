# Agente do Portal da Transparência de MG

MCP server que expõe a API de despesas do Portal da Transparência de Minas Gerais (Prodemge) como tools para
agentes LLM. Projeto da disciplina de LLMs (Grupo 2), com a pergunta de pesquisa: um agente com tool-use traduz
perguntas sobre gastos públicos em chamadas de API corretas?

## Estrutura

```
mcp_portal_transparencia/   MCP server
  server.py                   tools expostas ao agente
  client.py                   acesso à API (OAuth, paginação, retries, listas)
  verificar_api.py            confere o client.py contra a API real
  tests/                      testes unitários (sem rede) e fixtures
  app.yaml, requirements.txt  deploy como Databricks App
avaliacao/                  perguntas de avaliação
  eval.csv                    30 perguntas com resposta esperada
  gerar_gabaritos.py          recalcula os valores do eval.csv pela API
scripts/
  testar_endpoints.py         testa todos os endpoints do swagger
  testar_databricks.py        testa o acesso ao LLM pelo Databricks AI Gateway
docs/
  ENDPOINTS.md                referência da API e comportamentos encontrados
  api_consultas_portal_transparencia.yaml   swagger da API
  respostas/                  respostas reais salvas da API
  disciplina/                 especificação, proposta e plano do projeto
notebooks/endpoints.ipynb   exploração inicial da API
```

## Tools

| Tool | Para que serve |
|---|---|
| `anos_disponiveis` | Anos com dados (a partir de 2021) |
| `buscar_classificacao` | Encontra o código de órgão, função, ação, elemento etc. pelo nome |
| `pesquisar_despesa` | Valores empenhados, liquidados e pagos com qualquer combinação de filtros, agrupados ou não |
| `maiores_favorecidos` | Ranking de credores |
| `buscar_favorecido` | Encontra um credor pelo nome e devolve o nome completo e o CPF/CNPJ |
| `detalhar_empenho` | Ficha completa de um empenho |

## Como rodar

1. Crie o ambiente e instale as dependências:
   ```bash
   conda create -n portal_transp python=3.13
   conda activate portal_transp
   pip install -r requirements.txt
   ```
2. Copie `.env.example` para `.env` e preencha `PT_MG_BASIC_AUTH` (credencial da API, obtida com a Prodemge).
   As variáveis `DATABRICKS_*` só são necessárias para os scripts que chamam o LLM.
3. Rode os testes:
   ```bash
   python -m pytest mcp_portal_transparencia/tests
   ```

## Observações

- A API de homologação muda os valores a cada carga de dados; os gabaritos do `eval.csv` registram a data da consulta.
- O endpoint de token da homologação recusa chamadas de IPs de nuvem não liberados. Veja a seção 7 do
  [ENDPOINTS.md](docs/ENDPOINTS.md).
