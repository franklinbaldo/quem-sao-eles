import { mkdir, writeFile } from 'node:fs/promises';

const debuggerBase = process.env.CHROME_DEBUGGER ?? 'http://127.0.0.1:9222';
const pepUrl = process.env.PEP_URL;
const outDir = process.env.CAPTURE_DIR ?? 'artifacts';
const timeoutMs = Number(process.env.CAPTURE_TIMEOUT_MS ?? 30000);

if (!pepUrl) throw new Error('PEP_URL is required');

await mkdir(outDir, { recursive: true });

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

let targets;
for (let attempt = 0; attempt < 60; attempt += 1) {
  try {
    targets = await fetch(`${debuggerBase}/json`).then((response) => {
      if (!response.ok) throw new Error(`DevTools HTTP ${response.status}`);
      return response.json();
    });
    if (targets.length) break;
  } catch {
    // Chrome may still be starting.
  }
  await sleep(250);
}

const target = targets?.find((item) => item.type === 'page' && item.url.includes('/pep'));
if (!target?.webSocketDebuggerUrl) {
  throw new Error('Could not find the /pep DevTools page target');
}

const socket = new WebSocket(target.webSocketDebuggerUrl);
const pending = new Map();
let nextId = 1;

await new Promise((resolve, reject) => {
  const timer = setTimeout(() => reject(new Error('DevTools WebSocket timed out')), 5000);
  socket.addEventListener('open', () => {
    clearTimeout(timer);
    resolve();
  }, { once: true });
  socket.addEventListener('error', (event) => {
    clearTimeout(timer);
    reject(event.error ?? new Error('DevTools WebSocket error'));
  }, { once: true });
});

socket.addEventListener('message', (event) => {
  const message = JSON.parse(event.data);
  if (!message.id) return;
  const waiter = pending.get(message.id);
  if (!waiter) return;
  pending.delete(message.id);
  if (message.error) waiter.reject(new Error(message.error.message));
  else waiter.resolve(message.result);
});

function command(method, params = {}) {
  const id = nextId++;
  return new Promise((resolve, reject) => {
    pending.set(id, { resolve, reject });
    socket.send(JSON.stringify({ id, method, params }));
  });
}

async function evaluate(expression) {
  const result = await command('Runtime.evaluate', {
    expression,
    returnByValue: true,
    awaitPromise: true,
  });
  if (result.exceptionDetails) {
    throw new Error(result.exceptionDetails.text ?? 'Browser evaluation failed');
  }
  return result.result?.value;
}

await command('Runtime.enable');
await command('Page.enable');

const inspectExpression = `(() => {
  const text = document.body?.innerText ?? '';
  const parquet = document.querySelector('a[href$="_pep.parquet"]');
  const time = document.querySelector('time[datetime]');
  return {
    source_visible: text.includes('Portal da Transparência / CGU'),
    competence_machine_readable: !!time && /^\\d{4}-\\d{2}$/.test(time.getAttribute('datetime') ?? ''),
    exact_parquet_link_visible: !!parquet && /\\/quem-sao-eles\\/data\\/\\d{6}_pep\\.parquet$/.test(parquet.getAttribute('href') ?? ''),
    parquet_href: parquet?.getAttribute('href') ?? null,
    search_control_rendered: !!document.querySelector('#pep-query'),
    engine_loading: text.includes('Carregando engine de busca (DuckDB-WASM)...'),
    runtime_error: text.includes('Erro ao inicializar o banco de dados:'),
  };
})()`;

const deadline = Date.now() + timeoutMs;
let observed;
let state = 'incomplete';

while (Date.now() < deadline) {
  observed = await evaluate(inspectExpression);
  if (observed.runtime_error) {
    state = 'runtime-error';
    break;
  }
  if (observed.search_control_rendered && !observed.engine_loading) {
    state = 'search-ready';
    break;
  }
  await sleep(500);
}

if (state === 'incomplete' && observed?.search_control_rendered && observed?.engine_loading) {
  state = 'engine-timeout';
}

const html = await evaluate('document.documentElement.outerHTML');
await writeFile(`${outDir}/pep-dom.html`, html, 'utf8');

const screenshot = await command('Page.captureScreenshot', {
  format: 'png',
  captureBeyondViewport: true,
  fromSurface: true,
});
await writeFile(`${outDir}/pep-1280x900.png`, Buffer.from(screenshot.data, 'base64'));

const evidence = {
  state,
  url: pepUrl,
  ...observed,
};
await writeFile(`${outDir}/capture-state.json`, `${JSON.stringify(evidence, null, 2)}\n`, 'utf8');
console.log(evidence);

socket.close();

const contractComplete = evidence.search_control_rendered
  && evidence.source_visible
  && evidence.competence_machine_readable
  && evidence.exact_parquet_link_visible;

if (!contractComplete) {
  throw new Error('Rendered PEP contract is incomplete');
}
if (state === 'incomplete') {
  throw new Error('Browser state could not be classified');
}
