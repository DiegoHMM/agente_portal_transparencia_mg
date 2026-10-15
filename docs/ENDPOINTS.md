# Endpoints da API do Portal da Transparência de MG

Referência dos endpoints identificados na API do Portal da Transparência de Minas Gerais (MGapi / WSO2, Prodemge).
Fontes: [api_consultas_portal_transparencia.yaml](api_consultas_portal_transparencia.yaml) (swagger), as chamadas
reais salvas em [respostas/](respostas/) (ano 2025, consulta de 25/09/2026) e os achados registrados em
[../avaliacao/perguntas.yaml](../avaliacao/perguntas.yaml).

Legenda de status:

| Marca | Significado |
|---|---|
| ✅ | Chamado na API de homologação e respondeu 200; resposta salva em `respostas/` |
| 🧩 | Já usado por [client.py](../mcp_portal_transparencia/client.py) |
| ⚠️ | Funciona, mas com comportamento que exige cuidado (ver observações) |
| ❌ | Não funciona no gateway |
| 📄 | Só documentado no swagger; ainda não testado |

---

## 1. Acesso

| Item | Homologação | Produção |
|---|---|---|
| Base URL | `https://homologacao.apigw.mgapi.prodemge.gov.br/portaltransparencia/1.0.0` | `https://apigw.mgapi.prodemge.gov.br/portaltransparencia/1.0.0` |
| Token | `https://homologacao.manager.mgapi.prodemge.gov.br/oauth2/token` | `https://manager.mgapi.prodemge.gov.br/oauth2/token` |

- **Autenticação:** OAuth2 `client_credentials`. Faça `POST` no endpoint de token com `Authorization: Basic base64(key:secret)`
  e `grant_type=client_credentials`. Use o `access_token` retornado como `Authorization: Bearer <token>`.
  O token expira em cerca de 1 h.
- **Credencial:** é preciso uma Application inscrita na API `PortalTransparencia` e aprovada pela Prodemge (api@prodemge.gov.br).
  Configure no `.env` (ver [.env.example](../.env.example)).
- **User-Agent:** envie um User-Agent próprio. O firewall do gateway pode recusar alguns valores com 403.

## 2. Convenções gerais

| Tema | Comportamento |
|---|---|
| Envelope | `{"status": 200, "data": {...}}` |
| Período (despesas, diárias) | `periodo_inicio` / `periodo_fim` em **DDMM**: `"0101"`–`"3112"` é o ano inteiro |
| Período (receitas) | **MM**: `"01"`–`"12"` |
| Paginação | `limit` (até 100) e `page` (começa em 1). Página além do fim devolve lista vazia, mas mantém os totais |
| Totais | `total_*` se referem ao **conjunto filtrado inteiro**, não só à página. Para obter apenas os totais, use `limit=1`. `subtotal_*` se refere à página |
| Valores | Número JSON (não string pt-BR). Arredonde para 2 casas, porque há resíduos como `798117998.9399999` |
| Colunas | `colunas=a,b,c` (CSV, sem espaços) escolhe os campos das linhas. Cada resposta traz `colunas_disponiveis` e `colunas_exibidas` |
| Ordenação | `order_by=<campo>` e `order_dir=asc\|desc` (alguns endpoints usam maiúsculas) |
| Acentos | Termo com acento (ex. `"educação"`) recebe **HTTP 403 em HTML** do gateway. Remova os acentos antes de enviar |
| Ids | Os ids das listas **mudam a cada ano** (AGE = 12135 em 2025 e 12264 em 2026). Resolva o id sempre com o mesmo `ano` da consulta |
| Erros | Parâmetro obrigatório ausente devolve **HTTP 500** com `{"message": "..."}`, não 400. Endpoint inexistente devolve 404 do gateway |

---

## 3. Despesas: consultas de valores (GET)

Todas aceitam `ano`, `periodo_inicio`, `periodo_fim`, `termo`, `colunas`, `order_by`, `order_dir`, `limit`, `page`, `export`.
Abaixo estão só os filtros específicos de cada uma.

### `GET /consultas/despesas/visao-geral.json` ✅ 🧩

Despesas por órgão (unidade orçamentária).

- **Filtros:** `id_orgao`
- **Linhas:** `orgaos[]` com `id_orgao, cd_orgao, sigla, nome, empenhado, liquidado, pago, liquidado_restos_a_pagar, pago_restos_a_pagar`
- **Contagem:** `qt_orgaos` (87 em 2025)
- **Extras:** `grafico1` (por categoria econômica) e `grafico2` (série anual)
- ⚠️ Ignora `id_elemento_despesa`, `id_funcao` e `id_subfuncao` **sem avisar**: devolve o total sem filtro.
- Exemplo: o total de 2025 tem empenhado 131.563.975.828,04, liquidado 127.112.592.180,39 e pago 125.459.430.296,87.

### `GET /consultas/despesas/programas.json` ✅ 🧩

Despesas por programa e ação.

- **Filtros:** `id_programa`, `id_acao`, `id_orgao` (separados ou combinados; `id_acao` sozinho não exige órgão)
- **Linhas:** `programas[]` com `id_orgao, id_programa, id_acao, acao, empenhado, liquidado, pago, liquidado_restos_a_pagar, pago_restos_a_pagar`
- **Contagem:** `qt_programas` (1581 em 2025)
- ⚠️ Cada linha é uma combinação **órgão + programa + ação**. Para um ranking por programa é preciso agregar.
- ⚠️ Restos a pagar de exercícios anteriores podem aparecer com outro `id_programa`/`id_acao` para a mesma ação.
  Filtrar só por `id_acao` pode deixar esses restos de fora.

### `GET /consultas/despesas/itens-despesa.json` ✅ 🧩

Despesas por item e elemento de despesa.

- **Filtros:** `id_item_despesa`, `id_elemento_despesa`, `id_orgao`, `id_empenho` (`id_orgao` + `id_elemento_despesa` funcionam juntos)
- **Linhas:** `itens_despesa[]` com `id_orgao, id_elemento_despesa, id_item_despesa, item_despesa, elemento_despesa, orgao, empenhado, liquidado, pago, …`
- **Contagem:** `qt_itens_despesa` (6215 em 2025)

### `GET /consultas/despesas/empenhos.json` ✅ ⚠️ 🧩

Lista de empenhos.

- **Filtros:** `id_empenho`, `favorecido`, `id_orgao`, `id_unidade`, `id_item_despesa`, `id_elemento_despesa`, `id_programa`, `id_acao`
- ⚠️ **Exige `id_orgao`, `id_unidade` ou `favorecido`.** Sem nenhum deles, retorna HTTP 500 com "É obrigatório informar o Órgão ou a Unidade Executora…".
- **Linhas:** `empenhos[]` com `id_empenho, id_orgao, id_unidade_executora, empenho, data_registro, cpf_cnpj_favorecido, favorecido, orgao, unidade_executora, numero_processo_compra, processo_contratacao, item_despesa, empenhado, liquidado, …` (20 colunas disponíveis)
- **Contagem:** `qt_empenhos`
- ⚠️ Lento: até 23 s com órgão + ação. Com os mesmos filtros, dá os mesmos totais que `programas.json`.
- ⚠️ `total_liquidado_restos_a_pagar` difere de `visao-geral`/`programas` (AGE 2025: 2.761.925,39 contra 2.761.361,24). Cite sempre o endpoint de origem.

### `GET /consultas/despesas/favorecidos.json` ✅ ⚠️ 🧩

Despesas por favorecido (credor).

- **Filtros:** `id_orgao`, `favorecido` (aceita nome parcial: `favorecido=CEMIG` retorna 61 linhas, uma por órgão × favorecido)
- **Linhas:** `registros[]`
- **Contagem:** `qt_registros`
- ⚠️ **Sem `colunas`, não traz valores**, só `id_orgao, id_favorecido, favorecido`. Use, por exemplo,
  `colunas=favorecido,cnpj_cpf_favorecido,orgao,valor_empenhado,valor_liquidado,valor_pago&order_by=valor_pago&order_dir=DESC`.
- ⚠️ `totais` e `subtotais` vêm vazios. Para obter o total, some as linhas.
- ⚠️ A coluna pedida como `cnpj_cpf_favorecido` volta com o nome `cpf_cnpj_favorecido`.

### `GET /consultas/despesas/empenhos/detalhamento.json` ✅ 🧩

Ficha completa de um empenho.

- **Parâmetros:** `id_empenho`, `ano` (aceita também `id_orgao`, `termo`, `order_by`, `order_dir`, `limit`, `page`)
- **Resposta:** seções `classificacao_orcamentaria`, `empenho` (reforços, anulações, inscrições em restos a pagar, totais),
  `liquidacao`, `pagamento` e `outras_informacoes` (processos de compra, contratos, convênios)

### `GET /consultas/despesas/empenhos/detalhamento/download` ✅

O mesmo detalhamento em **.xlsx**. Parâmetros: `id_empenho`, `ano`.

### `GET /consultas/despesas/gerar-csv` ✅ ⚠️

Exportação em CSV.

- **Parâmetros:** `ano`, `periodo_inicio`, `periodo_fim`, `id_orgao`, `termo`, `limit`, `nome_arquivo`
- ⚠️ O intervalo pode ter **no máximo 31 dias**; acima disso, retorna 500.
- O CSV usa `;` como separador e vem com BOM UTF-8.

### `GET /consultas/despesas/lista-periodo.json` ✅ 🧩

Anos disponíveis: `data = [[2021, 2022, 2023, 2024, 2025, 2026]]`.

### `POST /consultas/despesas/pesquisa-avancada.json` ❌

Está no swagger (corpo: `nivel, filtros, limit, page, order_by, order_dir`), mas o gateway responde **404** ("endpoint não existe").

---

## 4. Despesas: listas auxiliares (POST)

Servem para transformar um nome (ex. "educação") no `id` que os filtros das consultas exigem.

- **Corpo JSON:** `{"ano", "periodo_inicio", "periodo_fim", "termo", "limit", "page"}`
- **Resposta:** `data = {"total", "registros": [...]}`
- O `termo` filtra no servidor, mas **precisa estar sem acento**.
- 🧩 [client.py](../mcp_portal_transparencia/client.py) baixa as listas pequenas inteiras e faz a busca localmente, sem acento.
  As listas grandes ele consulta com `termo`.
- Os registros vêm em formatos diferentes e podem conter `\t` e `\r\n`. Por isso o `_normalizar_item` converte tudo para `{id, codigo, nome}`.

| Endpoint (`/consultas/despesas/…`) | Obrigatórios | Total 2025 | Formato do registro | Obs. |
|---|---|---:|---|---|
| `lista-orgaos.json` ✅ | — | 87 | `id_orgao, nome` ("1081 - ADVOCACIA GERAL DO ESTADO") | "saude" retorna o Fundo Estadual de Saúde e a ESP, não a Secretaria |
| `lista-unidades.json` ✅ | — | 1116 | `id_orgao, nome` | unidades executoras |
| `lista-programas.json` ✅ | — | 158 | `id_programa, codigo_programa, nome_programa, nome_programa_sem_id` | |
| `lista-acoes.json` ✅ | — | 671 | `id_acao, codigo_acao, nome_acao, nome_acao_sem_id` | |
| `lista-funcoes.json` ✅ | — | 26 | `id, codigo, descricao, nome` | ⚠️ `id_funcao` é ignorado pelas consultas |
| `lista-subfuncoes.json` ✅ | — | 81 | `id, codigo, descricao, nome` | ⚠️ `id_subfuncao` é ignorado pelas consultas |
| `lista-elementos-despesa.json` ✅ | — | 55 | `id_elemento_despesa, nome` | |
| `lista-itens-despesa.json` ✅ | — | 440 | `id_item_despesa, nome` | |
| `lista-categorias-economicas.json` ✅ | — | 2 | `id, codigo, descricao, nome` | |
| `lista-grupos-despesa.json` ✅ | — | 6 | `id, codigo, descricao, nome` | |
| `lista-modalidades-aplicacao.json` ✅ | — | 14 | `id, codigo, descricao, nome` | |
| `lista-fontes-recurso.json` ✅ | — | 92 | `id, codigo, descricao, nome` | |
| `lista-fontes-recurso-stn.json` ✅ | — | 49 | `id, codigo, descricao, nome` | |
| `lista-ipu.json` ✅ | — | 12 | `id, codigo, descricao, nome` | há `codigo = 0` válido |
| `lista-upg.json` ✅ | — | 5303 | `id, codigo, descricao, nome` | |
| `lista-favorecidos.json` ✅ | — | 23219 | `id_favorecido, nome, cnpj_cpf_favorecido, descricao` | grande: use `termo` |
| `lista-processos-compra.json` ✅ | — | 33649 | `id, codigo, descricao, nome` | |
| `lista-procedimentos-contratacao.json` ✅ | — | 12 | `id, codigo, descricao, nome` | |
| `lista-objetos-processo.json` ✅ | `ano` | 24391 | `id, codigo, descricao, nome` | |
| `lista-contratos-convenios.json` ✅ | — | 75713 | `id, codigo, descricao, nome` | |
| `lista-objetos-contrato.json` ✅ | `ano` | 15048 | `id, codigo, descricao, nome` | |
| `lista-titulos-convenio.json` ✅ | `ano` | 7561 | `id, codigo, descricao, nome` | |
| `lista-empenhos.json` ✅ | `ano`, `id_orgao` | 108070 | `id, codigo, descricao, nome` | ⚠️ só números ("1 - 1"); não serve para busca por texto |
| `lista-documentos-pagamento.json` ✅ | `ano`, `id_orgao` | 115608 | `id, codigo, descricao, nome` | ⚠️ só números; não serve para busca por texto |

---

## 5. Outros módulos (📄 só no swagger, não testados)

Todos usam GET. Os parâmetros com `*` são obrigatórios.

### Receitas (`/consultas/receitas/…`), período em MM

| Endpoint | Parâmetros principais |
|---|---|
| `visao-geral.json` | `ano, periodo_inicio, periodo_fim, id_orgao, termo` + paginação/ordenação/`export` |
| `classificacao-orcamentaria.json` | os mesmos de `visao-geral.json` + `id_classificacao_receita, id_categoria_economica, id_origem, id_especie, id_desdobramento_1..3, id_tipo_receita, id_item_receita, id_subitem_receita` |
| `gerar-csv` | `ano, periodo_inicio, periodo_fim, id_orgao, termo` |
| `lista-periodo.json` | — |
| `lista-orgaos.json`, `lista-classificacao-receita.json`, `lista-categoria-economica.json`, `lista-origem.json`, `lista-especie.json`, `lista-desdobramento-1/2/3.json`, `lista-tipo-receita.json`, `lista-item-receita.json`, `lista-subitem-receita.json`, `lista-fonte-recurso.json`, `lista-fonte-recurso-stn.json` | `termo, limit, page` |

### Remuneração (`/consultas/remuneracao/…`)

| Endpoint | Parâmetros principais |
|---|---|
| `orgao.json` | `ano, mes, id_orgao, situacao, termo` |
| `cargo.json` | `ano, mes, id_cargo_efetivo, id_cargo_comissao, situacao, termo` |
| `individual.json` | `ano*, mes*, id_orgao, situacao, nome_servidor, masp, id_cargo_efetivo, id_cargo_comissao, termo` |
| `detalhamento.json` | `masp, hash` (vindo de `individual.json`), `ano, mes, id_servidor, id_orgao, id_remuneracao` |
| `jetons.json` | `ano, mes, id_servidor, id_remuneracao, nome_empresa, nome_servidor` |
| `situacao.json` | `ano, mes, situacao, id_orgao` |
| `listar-arquivos.json` | `ano, mes` |
| `lista-orgaos.json`, `lista-cargos-efetivos.json`, `lista-cargos-comissao.json`, `lista-empresas.json` | `termo` + id específico, `limit, page` |
| `lista-anos-meses.json` | — |

### Diárias e viagens (`/consultas/diarias/…`), período em DDMM

| Endpoint | Parâmetros principais |
|---|---|
| `visao-geral.json` | `ano, periodo_inicio, periodo_fim, id_orgao, termo` |
| `destinos.json` | `id_destino, ano, periodo_inicio, periodo_fim, id_viajante, id_destino_tipo` |
| `individual.json` | `ano*, periodo_inicio*, periodo_fim*, id_orgao, id_destino, id_destino_tipo, viajante, cpf, cargo_comissao` |
| `individual-documentos.json` | `hash*` (vindo de `individual.json`), `id_destino_tipo` |
| `individual-detalhamento.json` | `id*` (vindo de `individual-documentos.json`), `tipo*` |
| `gerar-csv` | `ano, periodo_inicio, periodo_fim` |
| `lista-periodo.json`, `lista-tipos.json` | — |
| `lista-orgaos.json`, `lista-destinos.json`, `lista-viajantes.json`, `lista-nome-viajante` | `termo, limit, page` |

### Gerais

| Endpoint | Parâmetros |
|---|---|
| `GET /consultas/consultas.json` | `tipo, limit, page`: consultas disponíveis |
| `GET /consultas/data-ultima-carga.json` | `tipo`: data da última carga de dados |

---

## 6. Roteiros de uso (despesas)

| Pergunta | Caminho |
|---|---|
| Quanto o Estado gastou no ano? | `visao-geral.json?ano=…&periodo_inicio=0101&periodo_fim=3112&limit=1` e ler `total_*` |
| Quanto o órgão X gastou? | `lista-orgaos` (termo sem acento) → `id_orgao` → `visao-geral.json?id_orgao=…&limit=1` |
| Quanto foi gasto com a ação/política Y? | `lista-acoes` → um ou mais `id_acao` → `programas.json?id_acao=…&limit=1` para cada um, somando os totais |
| Gasto do órgão X com o elemento Z | `lista-elementos-despesa` → `itens-despesa.json?id_orgao=…&id_elemento_despesa=…` (não use `visao-geral`, que ignora esse filtro) |
| Maiores credores | `favorecidos.json` com `colunas` com valores e `order_by=valor_pago&order_dir=DESC` |
| Detalhe de um empenho | `empenhos.json?id_orgao=…` → `id_empenho` → `empenhos/detalhamento.json` |
