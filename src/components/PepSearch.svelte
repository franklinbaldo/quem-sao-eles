<script lang="ts">
  import { onMount } from 'svelte';
  import * as duckdb from '@duckdb/duckdb-wasm';
  import { z } from 'zod';

  export let parquetUrl: string;
  export let dataPeriod: string;

  // Define our expected row schema based on the python pipeline output
  const formatDate = (val: any) => {
    if (!val) return null;
    if (typeof val === 'number') {
      const d = new Date(val);
      if (!isNaN(d.getTime())) return d.toLocaleDateString('pt-BR');
    }
    return String(val);
  };

  const PepRowSchema = z.object({
    cpf: z.any().nullable().optional().transform(val => val ? String(val) : null),
    nome: z.any().nullable().optional().transform(val => val ? String(val) : null),
    sigla_funcao: z.any().nullable().optional().transform(val => val ? String(val) : null),
    descricao_funcao: z.any().nullable().optional().transform(val => val ? String(val) : null),
    nivel_funcao: z.any().nullable().optional().transform(val => val ? String(val) : null),
    nome_orgao: z.any().nullable().optional().transform(val => val ? String(val) : null),
    data_inicio_exercicio: z.any().nullable().optional().transform(formatDate),
    data_fim_exercicio: z.any().nullable().optional().transform(formatDate),
    data_fim_carencia: z.any().nullable().optional().transform(formatDate),
  });

  type PepRow = z.infer<typeof PepRowSchema>;

  let query = '';
  let results: PepRow[] = [];
  let isSearching = false;
  let dbReady = false;
  let dbInstance: duckdb.AsyncDuckDB | null = null;
  let connection: duckdb.AsyncDuckDBConnection | null = null;
  let errorMessage = '';

  onMount(async () => {
    try {
      const JSDELIVR_BUNDLES = duckdb.getJsDelivrBundles();
      const bundle = await duckdb.selectBundle(JSDELIVR_BUNDLES);

      const worker_url = URL.createObjectURL(
        new Blob([`importScripts("${bundle.mainWorker!}");`], { type: 'text/javascript' })
      );

      const worker = new Worker(worker_url);
      const logger = new duckdb.ConsoleLogger();
      dbInstance = new duckdb.AsyncDuckDB(logger, worker);

      await dbInstance.instantiate(bundle.mainModule, bundle.pthreadWorker);
      URL.revokeObjectURL(worker_url);

      connection = await dbInstance.connect();
      dbReady = true;
    } catch (e: any) {
      errorMessage = "Erro ao inicializar o banco de dados: " + e.message;
      console.error(e);
    }
  });

  async function handleSearch() {
    if (!query || query.length < 3 || !dbReady || !connection) return;

    isSearching = true;
    errorMessage = '';

    try {
      // Escape single quotes for SQL
      const safeQuery = query.replace(/'/g, "''");
      const url = new URL(parquetUrl, window.location.href).href;

      const sql = `
        SELECT *
        FROM read_parquet('${url}')
        WHERE
          nome ILIKE '%${safeQuery}%' OR
          cpf ILIKE '%${safeQuery}%'
        LIMIT 100
      `;

      const result = await connection.query(sql);

      // Convert Apache Arrow table to JS array and validate
      const rawRows = result.toArray().map(row => row.toJSON());
      const parsedRows = z.array(PepRowSchema).safeParse(rawRows);

      if (parsedRows.success) {
        results = parsedRows.data;
      } else {
        console.error('Validation error:', parsedRows.error);
        errorMessage = 'Erro ao validar os dados retornados do arquivo.';
        results = [];
      }
    } catch (e: any) {
      errorMessage = "Erro na busca: " + e.message;
      console.error(e);
    } finally {
      isSearching = false;
    }
  }
</script>

<div class="search-control">
  <label for="pep-query">Nome ou CPF</label>
  <p id="pep-query-help">Digite ao menos 3 caracteres. A busca consulta a competência {dataPeriod}.</p>
  <div class="search-box">
    <input
      id="pep-query"
      type="text"
      bind:value={query}
      placeholder="Ex.: nome ou CPF mascarado"
      aria-describedby="pep-query-help"
      on:keydown={(e) => e.key === 'Enter' && handleSearch()}
    />
    <button on:click={handleSearch} disabled={!dbReady || isSearching || query.length < 3}>
      {isSearching ? 'Buscando...' : 'Buscar'}
    </button>
  </div>
</div>

{#if errorMessage}
  <div class="error" role="alert">{errorMessage}</div>
{/if}

{#if results.length > 0}
  <div class="results">
    <p class="count" aria-live="polite">Encontrados {results.length} registros</p>
    {#each results as row}
      <article class="card">
        <h3>{row.nome || 'Nome Indisponível'}</h3>
        <p class="role"><strong>Cargo:</strong> {row.descricao_funcao || row.sigla_funcao} - {row.nome_orgao}</p>
        <p class="dates"><strong>Exercício:</strong> {row.data_inicio_exercicio} a {row.data_fim_exercicio || 'Atual'}</p>
        {#if row.cpf}
          <p class="cpf"><strong>CPF Mascarado:</strong> {row.cpf}</p>
        {/if}
      </article>
    {/each}
  </div>
{:else if query && !isSearching && dbReady && results.length === 0 && !errorMessage}
  <p aria-live="polite">Nenhum resultado encontrado para "{query}".</p>
{/if}

{#if !dbReady && !errorMessage}
  <p class="loading-db" role="status">Carregando engine de busca (DuckDB-WASM)...</p>
{/if}

<style>
  .search-control {
    margin-bottom: 2rem;
  }
  label {
    display: block;
    font-weight: bold;
    margin-bottom: 0.25rem;
  }
  #pep-query-help {
    color: #555;
    font-size: 0.9rem;
    margin: 0 0 0.75rem;
  }
  .search-box {
    display: flex;
    gap: 0.5rem;
  }
  input {
    flex: 1;
    padding: 0.75rem;
    font-size: 1rem;
    border: 1px solid #ccc;
    border-radius: 4px;
  }
  input:focus-visible,
  button:focus-visible {
    outline: 2px solid #111;
    outline-offset: 2px;
  }
  button {
    padding: 0.75rem 1.5rem;
    background-color: #000;
    color: #fff;
    border: none;
    border-radius: 4px;
    font-size: 1rem;
    cursor: pointer;
    font-weight: bold;
  }
  button:disabled {
    background-color: #666;
    cursor: not-allowed;
  }
  .error {
    color: #8b0000;
    margin-bottom: 1rem;
    padding: 1rem;
    background-color: #fff2f2;
    border: 1px solid #d88;
  }
  .loading-db {
    color: #666;
    font-style: italic;
  }
  .card {
    border: 1px solid #ddd;
    padding: 1rem;
    margin-bottom: 1rem;
    border-radius: 4px;
    background: #fff;
  }
  .card h3 {
    margin: 0 0 0.5rem 0;
    font-size: 1.25rem;
  }
  .card p {
    margin: 0.25rem 0;
    font-size: 0.95rem;
  }
  .role {
    color: #333;
  }
  .dates {
    color: #555;
  }
  .cpf {
    color: #666;
    font-family: monospace;
  }
  .count {
    font-weight: bold;
    margin-bottom: 1rem;
  }
  @media (max-width: 600px) {
    .search-box {
      align-items: stretch;
      flex-direction: column;
    }
  }
</style>