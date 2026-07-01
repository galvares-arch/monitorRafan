# Monitor de Inteligência RAFAN — Prompts e Setup dos Módulos (MVP web search)

Mapeamento sobre o cenário **já clonado** do Cenergy (4 módulos). Nada de módulo novo.

| Módulo | Papel | Modelo | Ferramentas | Entrada → Saída |
|---|---|---|---|---|
| **M1 Pesquisa A** | Reputação das 2 unidades (Google + Instagram) | Claude Sonnet | **Web search ON** | — → `{"moteis":[...]}` em ```json |
| **M2 Pesquisa B** | Imprensa do DF | Claude Sonnet | **Web search ON** | — → `{"imprensa":{...}}` em ```json |
| **M3 Agregador** | Monta o JSON final + resumo | Claude Haiku | **Sem ferramentas** | `{{1.textResponse}}` + `{{2.textResponse}}` → JSON final em ```json |
| **M4 HTTP POST** | Envia pro endpoint | — | — | Body = `{{3.textResponse}}` → `/render` |

**Regras de ouro do Make (as mesmas que já validamos):**
- Todos os módulos de IA terminam a saída **dentro de um bloco ` ```json `** — é isso que joga o conteúdo no `textResponse` (e não no `jsonResponse`, que não injeta no prompt seguinte).
- Encadeie sempre por `{{N.textResponse}}`.
- Efeito (effort) sugerido no MVP: **medium** nos dois de pesquisa (equilíbrio custo × qualidade).

---

## Esquema final (o que o M3 precisa entregar e o endpoint espera)

```json
{
  "intro": "texto com data de hoje e período (dia anterior)",
  "resumo": {
    "kpis": [["7","avaliações Google"],["9","comentários Instagram"],["10 / 3 / 3","pos / neu / neg"],["4,3★","nota média Google"]],
    "destaques": [["Rótulo:","frase"], ["Rótulo:","frase"]]
  },
  "moteis": [
    {
      "nome": "Motel Colorado",
      "subtitle": "Sobradinho/DF — reputação online referente a DD/MM/AAAA.",
      "handle": "@motelcolorado",
      "kpis": [["4","avaliações Google"],["4,2★","nota média"],["5","comentários Instagram"]],
      "avaliacoes": [
        {"autor":"Nome ou Anônimo","nota":5,"data":"DD/MM","comentario":"texto em linguagem simples","classificacao":"positivo|neutro|negativo"}
      ],
      "leitura": "1-2 frases de leitura do bloco Google",
      "instagram": [
        {"autor":"@usuario","data":"DD/MM","comentario":"texto","post_url":"https://instagram.com/p/...","classificacao":"positivo|neutro|negativo"}
      ],
      "leitura_instagram": "1-2 frases de leitura do bloco Instagram"
    },
    { "nome": "Motel Park Way", "handle": "@motelparkwaybsb", "...": "mesma estrutura" }
  ],
  "imprensa": {
    "subtitle": "linha explicativa do que foi monitorado",
    "rows": [
      {"titulo":"título da matéria","url":"https://...","fonte":"Veículo<br/>DD/MM/AAAA","resumo":"resumo simples","relevancia":"ALTA|MÉDIA|BAIXA"}
    ],
    "leitura": "1-2 frases de leitura da imprensa"
  }
}
```

**Convenções que o renderizador usa:**
- `classificacao`: `positivo` (verde), `neutro` (âmbar), `negativo` (vermelho). Qualquer caixa serve.
- `relevancia`: `ALTA` (vermelho), `MÉDIA` (âmbar), `BAIXA` (verde).
- `nota`: inteiro 1–5 (vira estrelas). Sem nota → `"—"`.
- Nada encontrado → **lista vazia `[]`** (o PDF escreve "nenhum registro encontrado"). **Nunca inventar.**

---

## M1 — Pesquisa A (Reputação: Google + Instagram das 2 unidades)

**Config:** Claude Sonnet · Web search **ON** · effort medium

**Prompt:**

```
Você é analista de inteligência de reputação. Use a ferramenta de busca na web para
levantar o que há de mais recente (foco no DIA ANTERIOR à data de hoje) sobre DOIS
motéis do grupo RAFAN, em duas frentes cada: (1) avaliações no Google e (2)
comentários no Instagram do perfil oficial.

UNIDADE 1 — MOTEL COLORADO
- Razão social: Rafan Empreendimentos Imob Ltda | CNPJ 00.652.875/0002-59
- Endereço: SPMN EPIA BR 020, Km 0, Lote 01 — Sobradinho/DF — CEP 71.560-100
- Site: https://www.motelcolorado.com.br/
- Instagram: https://www.instagram.com/motelcolorado/

UNIDADE 2 — MOTEL PARK WAY
- Razão social: Rafan Empreendimentos Imobiliários Ltda | CNPJ 00.652.875/0001-78
- Endereço: SPMS EPIA, Lote 07 (parte) — Núcleo Bandeirante/DF — CEP 71.738-010
- Site: https://www.motelparkway.com.br/
- Instagram: https://www.instagram.com/motelparkwaybsb/

REGRAS
- Confirme que é a empresa certa pelos dados acima; descarte homônimos de outras cidades.
- Foque no que for do dia anterior. Se não houver nada novo do dia anterior, traga o
  mais recente que encontrar e diga isso na leitura — mas NÃO invente.
- Classifique cada item em "positivo", "neutro" ou "negativo".
- Google: informe a nota de 1 a 5. Autor não identificado = "Anônimo".
- Instagram: por busca web os comentários podem não estar acessíveis. Se não conseguir
  recuperar comentários reais, retorne "instagram": [] e explique em "leitura_instagram".
- ANTI-ALUCINAÇÃO: nunca invente autor, nota, data, texto ou link. Sem registros = [].
- kpis de cada motel: [[qtd avaliações Google novas,"avaliações Google"],
  [nota média atual com ★,"nota média"],[qtd comentários Instagram novos,"comentários Instagram"]].

SAÍDA: responda APENAS com um bloco ```json contendo exatamente:
{
  "moteis": [
    {"nome":"Motel Colorado","subtitle":"Sobradinho/DF — reputação online referente a DD/MM/AAAA.","handle":"@motelcolorado","kpis":[...],"avaliacoes":[...],"leitura":"...","instagram":[...],"leitura_instagram":"..."},
    {"nome":"Motel Park Way","subtitle":"Núcleo Bandeirante/DF — reputação online referente a DD/MM/AAAA.","handle":"@motelparkwaybsb","kpis":[...],"avaliacoes":[...],"leitura":"...","instagram":[...],"leitura_instagram":"..."}
  ]
}
```

---

## M2 — Pesquisa B (Imprensa do DF)

**Config:** Claude Sonnet · Web search **ON** · effort medium

**Prompt:**

```
Você é analista de mídia. Use a busca na web para procurar menções recentes (foco no
DIA ANTERIOR à data de hoje) ao Motel Colorado, ao Motel Park Way e ao grupo
Rafan Empreendimentos Imobiliários nos portais de notícias do DF, especialmente
Metrópoles, Correio Braziliense e Jornal de Brasília — e outros portais locais.

REGRAS
- Só inclua matérias que realmente citem os motéis ou o grupo (direta ou
  indiretamente, ex.: "motéis da EPIA"). Cite a URL real da matéria.
- Classifique a relevância para a reputação em "ALTA", "MÉDIA" ou "BAIXA".
- ANTI-ALUCINAÇÃO: nunca invente título, veículo, data ou link. Se não houver menção
  no período, retorne "rows": [] e explique em "leitura".

SAÍDA: responda APENAS com um bloco ```json contendo exatamente:
{
  "imprensa": {
    "subtitle": "Monitoramento de Metrópoles, Correio Braziliense, Jornal de Brasília e demais portais do DF, buscando menções aos motéis e ao grupo RAFAN.",
    "rows": [{"titulo":"...","url":"https://...","fonte":"Veículo<br/>DD/MM/AAAA","resumo":"...","relevancia":"ALTA|MÉDIA|BAIXA"}],
    "leitura": "..."
  }
}
```

---

## M3 — Agregador (monta o JSON final)

**Config:** Claude Haiku · **sem ferramentas**

**Prompt:**

```
Você recebe dois blocos JSON (dentro de cercas ```json) e deve montar UM único JSON
final para o relatório. NÃO pesquise nada; use apenas o que veio nas entradas.

ENTRADA A (reputação):
{{1.textResponse}}

ENTRADA B (imprensa):
{{2.textResponse}}

TAREFA
1. Extraia "moteis" da Entrada A e "imprensa" da Entrada B.
2. Escreva "intro": comece com "Data de elaboração: <b>HOJE por extenso</b> | Período
   monitorado: <b>avaliações, comentários e notícias do dia anterior (DD/MM/AAAA)</b>."
   e explique em 1 frase o que o relatório reúne. Use a data de hoje real.
3. Monte "resumo.kpis" com 4 pares, contando a partir das entradas:
   - total de avaliações Google (soma dos dois motéis)
   - total de comentários Instagram (soma dos dois motéis)
   - saldo "P / N / Ng" somando as classificações (Google + Instagram) das duas unidades
   - nota média geral do Google com ★ (média simples das notas médias das unidades)
4. Monte "resumo.destaques": 3 a 4 itens no formato ["Rótulo:","frase"], destacando
   saldo do dia, principal ponto de atenção, algo do Instagram e algo da imprensa.
5. Se algum bloco vier vazio, reflita isso com honestidade (não invente).

SAÍDA: responda APENAS com um bloco ```json contendo:
{"intro":"...","resumo":{"kpis":[...],"destaques":[...]},"moteis":[...da Entrada A...],"imprensa":{...da Entrada B...}}
```

---

## M4 — HTTP POST (envio ao endpoint)

- **URL:** `https://SEU-ENDPOINT.onrender.com/render`
- **Method:** POST
- **Body type:** Raw / JSON — **conteúdo = `{{3.textResponse}}`**
- **Headers:** `Content-Type: application/json`

O endpoint extrai o JSON de dentro das cercas por regex (`\{.*\}`), gera o PDF único
(capa + 1 página por motel com Google e Instagram + página de imprensa) e — quando o
canal de entrega estiver definido — envia. Enquanto isso, a rota `/test` gera o PDF de
exemplo sem gastar crédito.

---

## Evolução futura (quando quiser trocar de "modelo")

- **Google reviews confiável:** substituir a busca do M1 por uma chamada à SerpAPI
  (Google Maps Reviews) ou Outscraper, ordenando por mais recentes e filtrando ontem.
- **Instagram real:** Graph API oficial (contas Business do grupo) ou Apify.
- Nada disso mexe no renderizador nem no esquema JSON — é trocar a origem dos dados.
```
