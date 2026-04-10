# Roadmap — Quem São Eles?

## Objetivo Meta

> Sempre buscar novas fontes que destravam o acesso a mais informações sobre "eles",
> e melhorar a UX para que a informação seja útil e fácil de acessar.

## Duas Modalidades de Informação

1. **Datasets públicos estruturados** — PEP, TSE, Portal da Transparência, Receita Federal, CEIS/CNEP, DJEN, etc.
2. **Pesquisa jornalística / Diários Oficiais** — scraping de portais de notícias e DOU/DOE, com arquivamento obrigatório no Internet Archive.

## Vantagem Estratégica: CPF como Chave Universal

O dataset PEP já contém o **CPF de toda pessoa exposta politicamente no Brasil**. Esse identificador é a chave que desbloqueia cruzamentos com:

| Fonte | O que destranca |
|---|---|
| **TSE** | Candidaturas históricas, doações recebidas, declarações de bens |
| **Portal da Transparência** | Salários, viagens a serviço, contratos do órgão |
| **Receita Federal (CNPJ aberto)** | Empresas onde é sócio ou administrador |
| **DJEN via [causaganha](https://github.com/franklinbaldo/causaganha)** | Processos judiciais onde aparece como parte |
| **CEIS/CNEP** | Sanções, multas e impedimentos administrativos |
| **Diário Oficial (DOU/DOE)** | Nomeações, exonerações, portarias |

## Natureza Incremental

Este projeto cresce de forma incremental: um ciclo de cada vez, uma fonte de cada vez. O critério de "pronto" para qualquer ciclo é:

- A nova informação aparece no perfil do político
- A fonte está documentada na página `/dados`
- O pipeline tem teste automatizado
- Toda URL externa está arquivada no Internet Archive

Não existe sprint grande — cada fonte nova já é uma entrega válida.

## Princípios

1. **Cada nova fonte = um ciclo completo**: pipeline → Parquet → enriquecimento do perfil → melhoria de UX
2. **Tudo arquivado**: toda URL de fonte externa vai para o Internet Archive
3. **CPF como âncora**: pipelines giram em torno do cruzamento por CPF
4. **causaganha como parceiro**: consumir os Parquets do DJEN, não reimplementar a coleta
5. **Documentação em Astro**: o próprio site documenta as fontes (página `/dados`)

---

## Fases

### Fase 0 — Fundação
*Limpar o que está incompleto antes de avançar*

- [ ] Corrigir boilerplate: `src/consts.ts`, `Footer.astro`, uso consistente do `Header.astro`
- [ ] Adicionar Ruff + pre-commit ao projeto Python
- [ ] Adicionar ESLint ao frontend
- [ ] Habilitar upload automático para Internet Archive no pipeline PEP
- [ ] Criar 5–10 perfis políticos reais em `src/content/politicos/` (prova de conceito)

### Fase 1 — Arquitetura de Pipelines
*Criar a estrutura que torna trivial adicionar novas fontes*

- [ ] Refatorar `scripts/pep_pipeline.py` → CLI com `typer` (comando `fetch-pep`)
- [ ] Estabelecer padrão de pipeline: `fetch → normalize → to_parquet → upload_ia`
- [ ] pytest para todos os pipelines Python
- [ ] structlog para auditoria de coleta
- [ ] Vitest para componentes Svelte

**Primeira nova fonte: TSE**
- [ ] `fetch-tse-candidaturas` — histórico de candidaturas por CPF
- [ ] `fetch-tse-bens` — declarações de bens por CPF
- [ ] Cruzar com PEP e enriquecer Parquet do perfil

### Fase 2 — Expansão de Datasets Públicos
*Cada fonte = um novo comando CLI + enriquecimento do perfil*

**Portal da Transparência**
- [ ] Viagens a serviço — cruzar por CPF
- [ ] Remunerações — salário histórico do servidor

**Receita Federal**
- [ ] Cruzar CPF com base CNPJ (quadro societário de empresas)

**CEIS/CNEP**
- [ ] Pipeline de sanções; badge de sanção no perfil

**causaganha (DJEN)**
- [ ] Consumir Parquets públicos do causaganha
- [ ] Cruzar CPF/nome com partes dos processos
- [ ] Mostrar processos relevantes no perfil

### Fase 3 — Fontes Não-Estruturadas (IA)
*Extrair estrutura de texto livre com Gemini API*

- [ ] Adicionar `google-genai` + `pydantic-ai`
- [ ] Scraper do DOU buscando CPF/nome do político
- [ ] Scraper de portais jornalísticos (coleta por nome)
- [ ] Toda URL coletada arquivada no Internet Archive (obrigatório)
- [ ] IA para extrair: data, tipo de ato, fato relevante, entidades mencionadas
- [ ] Sumarização automática exibida no perfil

### Fase 4 — UX e Descoberta
*A informação só tem valor se for fácil de encontrar e entender*

- [ ] Timeline do político (todos os eventos em ordem cronológica)
- [ ] Scoring de relevância/notoriedade — prioriza quem aparece na home
- [ ] Busca semântica entre perfis (LanceDB)
- [ ] Filtros por: partido, estado, cargo, tags temáticas, fontes disponíveis
- [ ] Indicador de "nível de cobertura" — quais fontes já foram coletadas para cada perfil
- [ ] Feed de atualizações — o que mudou recentemente

### Fase 5 — Plataforma Aberta

- [ ] Exportação dos Parquets enriquecidos como dataset público
- [ ] Página `/dados` explicando cada fonte utilizada
- [ ] Alertas automáticos quando nova informação aparece sobre um político monitorado

---

## Comparação com causaganha

O [causaganha](https://github.com/franklinbaldo/causaganha) é o projeto irmão mais maduro (~1.400 commits). Compartilha o mesmo stack (Astro + Svelte + DuckDB WASM + Python + ibis + Parquet + Internet Archive) e serve como referência de arquitetura.

| O que trazer do causaganha | Motivo |
|---|---|
| CLI modular com `typer` | Cada fonte vira um comando; fácil adicionar novas |
| `pytest` + `pytest-bdd` | Pipelines de dados falham silenciosamente sem testes |
| `ruff` + `pre-commit` | Qualidade de código, base para contribuições |
| `google-genai` + `pydantic-ai` | Extrair estrutura de textos não-estruturados |
| `structlog` | Auditar o que foi coletado e quando |
| Scoring/ranking | Priorizar quem mostrar, baseado em relevância |
