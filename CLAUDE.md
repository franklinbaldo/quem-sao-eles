# CLAUDE.md — Quem São Eles?

Guia de contexto para agentes de IA trabalhando neste repositório.

## O que é este projeto

**Quem São Eles?** é uma plataforma de transparência sobre pessoas expostas politicamente (PEPs) no Brasil. O objetivo é cruzar múltiplos datasets públicos para construir perfis completos e úteis — não apenas um catálogo, mas um hub de inteligência sobre figuras políticas.

**Objetivo meta:** sempre buscar novas fontes que destrancam mais informações sobre "eles" e melhorar a UX para que essa informação seja útil e acessível.

## Stack

| Camada | Tecnologia |
|---|---|
| Frontend | Astro 6 + Svelte 5 + TypeScript |
| Busca client-side | DuckDB WASM + Parquet |
| Validação frontend | Zod 4 |
| Backend/pipelines | Python 3.12+ |
| Abstração de dados | ibis-framework (backend DuckDB) |
| Validação backend | Pydantic 2 |
| Formato canônico | Parquet |
| Hosting | GitHub Pages (estático) |
| CI/CD | GitHub Actions |
| Arquivamento | Internet Archive |
| Node mínimo | v22.12.0 |

## Arquitetura

```
src/
  content/
    politicos/     # Markdown com frontmatter — perfil editorial (bio, foto, tags)
    noticias/      # Markdown com frontmatter — notícias linkadas a políticos
  pages/
    index.astro    # Home — últimas atualizações + políticos recentes
    pep.astro      # Busca interativa no dataset PEP via DuckDB WASM
    perfil/[slug].astro  # Página de perfil do político
  components/
    PepSearch.svelte     # Componente de busca (Svelte + DuckDB WASM)
public/
  data/            # Parquets servidos estaticamente para o frontend
scripts/
  pep_pipeline.py  # Pipeline Python: download → normalização → Parquet → IA
.github/workflows/
  deploy.yml       # Build e deploy automático no GitHub Pages
  pep.yml          # Atualização mensal do dataset PEP
```

## Padrão de dados: CPF como chave universal

O dataset PEP (Portal da Transparência) contém o CPF de toda pessoa exposta politicamente. Esse é o identificador usado para cruzar com todas as outras fontes:

- **TSE**: candidaturas, doações, bens declarados
- **Portal da Transparência**: salários, viagens, contratos
- **Receita Federal/CNPJ**: quadro societário de empresas
- **DJEN** (via [causaganha](https://github.com/franklinbaldo/causaganha)): processos judiciais
- **CEIS/CNEP**: sanções e impedimentos
- **DOU/DOE**: nomeações e atos oficiais

## Padrão de pipeline

Cada nova fonte de dados segue o mesmo padrão:

```
fetch → normalize → to_parquet → upload_ia
```

1. Baixar dados brutos (ZIP, CSV, etc.)
2. Normalizar com ibis/DuckDB
3. Salvar como Parquet em `public/data/`
4. Upload opcional para Internet Archive (requer `IA_ACCESS_KEY` e `IA_SECRET_KEY`)

## Esquema de conteúdo (Astro Content Collections)

### Político (`src/content/politicos/<slug>.md`)

```yaml
---
name: "Nome Completo"
cpf: "000.000.000-00"   # opcional, mas importante para cruzamentos
party: "PT"
role: "Senador"
chamber: "Senado Federal"
since: 2023-01-01
photo: "./foto.jpg"     # opcional
tags: ["economia", "meio-ambiente"]
---
Bio em Markdown.
```

### Notícia (`src/content/noticias/<slug>.md`)

```yaml
---
title: "Título da Notícia"
politician: "slug-do-politico"
date: 2024-03-15
source_url: "https://..."
archive_url: "https://web.archive.org/web/..."  # OBRIGATÓRIO
summary: "Resumo breve."
---
Detalhes em Markdown.
```

> **Regra inviolável:** toda URL externa deve ter cópia arquivada no Internet Archive (`archive_url`).

## Comandos de desenvolvimento

```sh
# Frontend
npm install
npm run dev          # dev server em localhost:4321/quem-sao-eles
npm run build        # build estático para /dist
npm run preview      # preview do build

# Pipeline Python
uv run python scripts/pep_pipeline.py
```

## Variáveis de ambiente

| Variável | Uso |
|---|---|
| `IA_ACCESS_KEY` | Upload para Internet Archive |
| `IA_SECRET_KEY` | Upload para Internet Archive |

## Projeto irmão: causaganha

[franklinbaldo/causaganha](https://github.com/franklinbaldo/causaganha) coleta e processa o DJEN (Diário da Justiça Eletrônico Nacional). Compartilha o mesmo stack. **Não reimplementar** coleta do DJEN — consumir os Parquets públicos que o causaganha publica.

## Natureza incremental do projeto

Este projeto cresce de forma incremental e deliberada. Cada ciclo adiciona uma nova fonte de dados ou melhora a UX — nunca os dois ao mesmo tempo. O critério de "pronto" para qualquer ciclo é:

- [ ] A nova informação aparece no perfil do político
- [ ] A fonte está documentada na página `/dados`
- [ ] O pipeline tem teste automatizado
- [ ] Toda URL externa está arquivada no Internet Archive

**Não tente resolver tudo de uma vez.** Um Parquet a mais, uma fonte a mais, um campo a mais no perfil — isso já é uma contribuição válida. Perfeito é inimigo do publicado.

## Regras para agentes

1. **Nunca remover `archive_url`** de notícias — é requisito de integridade do projeto.
2. **CPF como chave** — ao adicionar dados de qualquer nova fonte, cruzar por CPF.
3. **Parquet como formato canônico** — novos dados vão para `public/data/` como Parquet.
4. **Estética jornalística** — o design é sóbrio (preto, branco, cinza). Não adicionar cores vivas, gradientes ou ícones decorativos.
5. **Sem backend** — o projeto é 100% estático. Busca e análise rodam no cliente via DuckDB WASM.
6. **Commit direto em `main`** não é recomendado — usar PRs para features novas.
