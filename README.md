# Quem São Eles?

Catálogo estático de políticos brasileiros — perfis monitorados diariamente por agentes jornalistas, servindo como registro público de suas atuações e histórico.

## Propósito

**Quem São Eles?** é um projeto focado em transparência e memória política. O objetivo é manter perfis atualizados e documentados de figuras públicas do Brasil.

- **Cobertura:** Congresso Nacional, ministros e cortes superiores (STF, STJ, TSE, TCU).
- **Metodologia:** Fontes secundárias (jornais, portais de notícias). Nenhuma informação é de primeira mão, e todas as fontes originais são obrigatoriamente arquivadas no [Internet Archive](https://archive.org/) para garantir a preservação a longo prazo.
- **Design:** O site segue uma estética jornalística limpa e sóbria (preto, branco e cinza), inspirada em publicações como ProPublica e The Intercept.
- **Agente Jornalista:** Os dados do projeto podem ser atualizados via interações de agentes como o [bob-woodward](https://github.com/franklinbaldo/bob-woodward) — persona ancorada em Bob Woodward (*All the President's Men*).

## Como rodar localmente

O site é construído com [Astro](https://astro.build/) usando um layout focado em estética jornalística.

### Pré-requisitos
- Node.js (v22.12.0 ou superior, conforme definido no `package.json`)
- npm (gerenciador de pacotes)

### Passos

1. Clone o repositório e acesse a pasta do projeto:
   ```sh
   git clone https://github.com/franklinbaldo/quem-sao-eles.git
   cd quem-sao-eles
   ```
2. Instale as dependências:
   ```sh
   npm install
   ```
3. Inicie o servidor de desenvolvimento:
   ```sh
   npm run dev
   ```
4. Acesse o site localmente (geralmente em `http://localhost:4321/quem-sao-eles`).

Para gerar a versão de produção (build estático) e testá-la, execute:
```sh
npm run build
npm run preview
```

## Como contribuir

O projeto armazena os dados através das [*Content Collections*](https://docs.astro.build/en/guides/content-collections/) do Astro, localizadas nas pastas `src/content/politicos/` e `src/content/noticias/`. Toda informação é gerenciada como arquivos Markdown (`.md` ou `.mdx`) com metadados (*Frontmatter*).

Qualquer pessoa ou agente pode contribuir adicionando novos políticos ou notícias. Basta criar um arquivo Markdown na pasta correspondente, seguindo os esquemas de dados.

### Adicionando um Político

Crie um arquivo em `src/content/politicos/<nome-do-politico>.md`.

**Exemplo de Frontmatter:**
```yaml
---
name: "Nome Completo do Político"
cpf: "000.000.000-00" # Opcional
party: "Sigla do Partido"
role: "Cargo Atual (ex: Senador, Ministro)"
chamber: "Câmara/Órgão (ex: Senado Federal, STF)"
since: 2023-01-01 # Data de início no cargo
photo: "./caminho/para/foto.jpg" # Opcional (Imagem na mesma pasta ou caminho válido)
tags: ["economia", "meio-ambiente"] # Opcional
---

Corpo do texto opcional com uma biografia ou detalhes adicionais sobre o político.
```

### Adicionando uma Notícia

Crie um arquivo em `src/content/noticias/<slug-da-noticia>.md`. A notícia precisa referenciar o ID do político, que é o nome do arquivo do político correspondente em `src/content/politicos` (sem a extensão `.md`).

**Exemplo de Frontmatter:**
```yaml
---
title: "Título da Notícia ou Evento"
politician: "nome-do-politico" # O ID do arquivo do político
date: 2023-10-15 # Data da publicação da notícia original
source_url: "https://site-de-noticia.com/artigo" # Link original da notícia
archive_url: "https://web.archive.org/web/.../artigo" # Link arquivado no Internet Archive (obrigatório)
summary: "Um breve resumo sobre os fatos relatados na notícia."
---

Corpo de texto expandindo os detalhes da notícia.
```

### Diretrizes de Contribuição
- **Sempre utilize fontes secundárias**: Adicione apenas informações publicamente veiculadas em jornais ou portais reconhecidos.
- **Arquivamento rígido**: Todo link adicionado deve ter uma cópia no Internet Archive (`archive_url`).
- **Sóbriedade**: Mantenha o tom enciclopédico e jornalístico sem juízo de valor.

## Deploy

O deploy é feito automaticamente no GitHub Pages sempre que há um novo commit na branch `main`, gerenciado pelo GitHub Actions (`.github/workflows/deploy.yml`).
