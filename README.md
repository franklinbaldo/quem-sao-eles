# Quem São Eles?

Catálogo de políticos brasileiros — perfis monitorados diariamente por agentes jornalistas.

**Cobertura:** Congresso Nacional, ministros, cortes superiores (STF, STJ, TSE, TCU).

**Metodologia:** fontes secundárias (jornais, portais), arquivadas no Internet Archive. Nunca informação de primeira mão.

**Agente jornalista:** [bob-woodward](https://github.com/franklinbaldo/bob-woodward) — persona ancorada em Bob Woodward (All the President's Men).

## Estrutura do Projeto

O site é construído com [Astro](https://astro.build/) usando um layout focado em estética jornalística. Os dados são armazenados como *content collections* nas pastas `src/content/politicos` e `src/content/noticias`.

## Desenvolvimento Local

Para rodar o projeto localmente:

1. Clone o repositório.
2. Instale as dependências:
   ```sh
   npm install
   ```
3. Inicie o servidor de desenvolvimento:
   ```sh
   npm run dev
   ```
4. Acesse o site localmente (geralmente em `http://localhost:4321/quem-sao-eles`).

## Deploy

O deploy é feito automaticamente no GitHub Pages sempre que há um commit na branch `main`, via GitHub Actions (`.github/workflows/deploy.yml`).
