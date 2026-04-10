<script lang="ts">
  import { onMount } from 'svelte';
  import * as duckdb from '@duckdb/duckdb-wasm';
  import { z } from 'zod';

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

  // The astro config uses base: '/quem-sao-eles', so public files are at '/quem-sao-eles/...'
  const PARQUET_URL = '/quem-sao-eles/data/202602_pep.parquet';

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

      // Register the file
      // In production, we can use DuckDB to directly query the HTTP endpoint of the internet archive
      // For this step, we'll query the static parquet we just generated locally
      // For local development it will be available at base + /data/...

      // We don't necessarily need to register the file, duckdb can read from url
      // but registering might be more robust depending on setup. Let's just run an http query.
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
      const url = new URL(PARQUET_URL, window.location.href).href;

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

      // Validate via Zod
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

<div class="search-box">
  <input
    type="text"
    bind:value={query}
    placeholder="Busque por Nome ou CPF (min 3 caracteres)..."
    on:keydown={(e) => e.key === 'Enter' && handleSearch()}
  />
  <button on:click={handleSearch} disabled={!dbReady || isSearching || query.length < 3}>
    {isSearching ? 'Buscando...' : 'Buscar'}
  </button>
</div>

{#if errorMessage}
  <div class="error">{errorMessage}</div>
{/if}

{#if results.length > 0}
  <div class="results">
    <p class="count">Encontrados {results.length} registros</p>
    {#each results as row}
      <div class="card">
        <h3>{row.nome || 'Nome Indisponível'}</h3>
        <p class="role"><strong>Cargo:</strong> {row.descricao_funcao || row.sigla_funcao} - {row.nome_orgao}</p>
        <p class="dates"><strong>Exercício:</strong> {row.data_inicio_exercicio} a {row.data_fim_exercicio || 'Atual'}</p>
        {#if row.cpf}
          <p class="cpf"><strong>CPF Mascarado:</strong> {row.cpf}</p>
        {/if}
      </div>
    {/each}
  </div>
{:else if query && !isSearching && dbReady && results.length === 0 && !errorMessage}
  <p>Nenhum resultado encontrado para "{query}".</p>
{/if}

{#if !dbReady}
  <p class="loading-db">Carregando engine de busca (DuckDB-WASM)...</p>
{/if}

<style>
  .search-box {
    display: flex;
    gap: 0.5rem;
    margin-bottom: 2rem;
  }
  input {
    flex: 1;
    padding: 0.75rem;
    font-size: 1rem;
    border: 1px solid #ccc;
    border-radius: 4px;
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
    color: red;
    margin-bottom: 1rem;
    padding: 1rem;
    background-color: #fee;
    border: 1px solid #fcc;
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
</style>