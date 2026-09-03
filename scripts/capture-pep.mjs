import { mkdir, writeFile } from 'node:fs/promises';

const debuggerBase = process.env.CHROME_DEBUGGER ?? 'http://127.0.0.1:9222';
const pepUrl = process.env.PEP_URL;
const outDir = process.env.CAPTURE_DIR ?? 'artifacts';
const timeoutMs = Number(process.env.CAPTURE_TIMEOUT_MS ?? 30000);
const captureSha = process.env.CAPTURE_SHA ?? null;
const mergeRefSha = process.env.MERGE_REF_SHA ?? null;

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

async function setViewport(width, height) {
  await command('Emulation.setDeviceMetricsOverride', {
    width,
    height,
    deviceScaleFactor: 1,
    mobile: width <= 480,
  });
  await sleep(250);
}

async function captureViewport(name, width, height) {
  await setViewport(width, height);
  const layout = await evaluate(`(() => {
    const input = document.querySelector('#pep-query');
    const button = input?.closest('.search-control')?.querySelector('button');
    const parquet = document.querySelector('a[href$="_pep.parquet"]');
    const time = document.querySelector('time[datetime]');
    const visible = (element) => {
      if (!(element instanceof HTMLElement)) return false;
      const rect = element.getBoundingClientRect();
      const style = getComputedStyle(element);
      return rect.width > 0 && rect.height > 0 && style.visibility !== 'hidden' && style.display !== 'none';
    };
    return {
      viewport: { width: innerWidth, height: innerHeight },
      document_width: document.documentElement.scrollWidth,
      horizontal_overflow: document.documentElement.scrollWidth > innerWidth + 1,
      search_input_visible: visible(input),
      search_button_visible: visible(button),
      provenance_visible: visible(time) && visible(parquet),
    };
  })()`);

  const screenshot = await command('Page.captureScreenshot', {
    format: 'png',
    captureBeyondViewport: false,
    fromSurface: true,
  });
  await writeFile(`${outDir}/pep-${name}.png`, Buffer.from(screenshot.data, 'base64'));
  return layout;
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

let queryOutcome = 'not-exercised';
if (state === 'search-ready') {
  const triggered = await evaluate(`(() => {
    const input = document.querySelector('#pep-query');
    const button = input?.closest('.search-control')?.querySelector('button');
    if (!(input instanceof HTMLInputElement) || !(button instanceof HTMLButtonElement)) return false;
    input.value = 'zzzxxy';
    input.dispatchEvent(new Event('input', { bubbles: true }));
    button.click();
    return true;
  })()`);

  if (!triggered) {
    queryOutcome = 'control-missing';
  } else {
    const queryDeadline = Date.now() + timeoutMs;
    while (Date.now() < queryDeadline) {
      const queryState = await evaluate(`(() => {
        const text = document.body?.innerText ?? '';
        if (text.includes('Erro na busca:')) return 'query-error';
        if (text.includes('Nenhum resultado encontrado para "zzzxxy".')) return 'empty-success';
        if (/Encontrados \\d+ registros/.test(text)) return 'results-success';
        if (text.includes('Buscando...')) return 'searching';
        return 'pending';
      })()`);
      if (queryState === 'query-error' || queryState === 'empty-success' || queryState === 'results-success') {
        queryOutcome = queryState;
        break;
      }
      await sleep(500);
    }
    if (queryOutcome === 'not-exercised') queryOutcome = 'query-timeout';
  }
}

await setViewport(1280, 900);
const html = await evaluate('document.documentElement.outerHTML');
await writeFile(`${outDir}/pep-dom.html`, html, 'utf8');

const desktop = await captureViewport('1280x900', 1280, 900);
const narrow = await captureViewport('390x844', 390, 844);

const evidence = {
  state,
  query_outcome: queryOutcome,
  url: pepUrl,
  evaluated_sha: captureSha,
  merge_ref_sha: mergeRefSha,
  ...observed,
  viewports: {
    desktop,
    narrow,
  },
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
if (state === 'search-ready' && !['empty-success', 'results-success'].includes(queryOutcome)) {
  throw new Error(`Published Parquet query did not complete successfully: ${queryOutcome}`);
}
if (!captureSha) {
  throw new Error('Rendered evidence does not identify the evaluated commit');
}
if (narrow.horizontal_overflow || !narrow.search_input_visible || !narrow.search_button_visible || !narrow.provenance_visible) {
  throw new Error(`Narrow viewport contract failed: ${JSON.stringify(narrow)}`);
}
