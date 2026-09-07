import assert from 'node:assert/strict';
import { execFile, spawn } from 'node:child_process';
import http from 'node:http';
import path from 'node:path';
import { test } from 'node:test';
import { fileURLToPath } from 'node:url';
import { promisify } from 'node:util';

import { WebSocketServer } from 'ws';

const execFileAsync = promisify(execFile);
const here = path.dirname(fileURLToPath(import.meta.url));
const client = path.resolve(here, '../../scripts/cdp_client.mjs');

async function invoke(mode, payload) {
  const { stdout } = await execFileAsync(process.execPath, [client, mode, JSON.stringify(payload)], {
    timeout: 10_000,
  });
  return JSON.parse(stdout);
}

test('CDP bridge uses modern HTTP verbs and direct target commands', async (t) => {
  const requests = [];
  const commands = [];
  let targetUrl = 'about:blank';
  const server = http.createServer((req, res) => {
    requests.push({ method: req.method, url: req.url });
    const address = server.address();
    const target = {
      id: 'target-1',
      type: 'page',
      url: targetUrl,
      webSocketDebuggerUrl: `ws://127.0.0.1:${address.port}/devtools/page/target-1`,
    };
    if (req.url === '/json/list') {
      res.writeHead(200, { 'content-type': 'application/json' });
      res.end(JSON.stringify([target]));
      return;
    }
    if (req.url === '/json/new' && req.method === 'PUT') {
      res.writeHead(200, { 'content-type': 'application/json' });
      res.end(JSON.stringify(target));
      return;
    }
    res.writeHead(405, { 'content-type': 'application/json' });
    res.end(JSON.stringify({ error: 'method not allowed' }));
  });
  const sockets = new WebSocketServer({ noServer: true });
  server.on('upgrade', (request, socket, head) => {
    sockets.handleUpgrade(request, socket, head, (websocket) => sockets.emit('connection', websocket, request));
  });
  sockets.on('connection', (websocket) => {
    websocket.on('message', (raw) => {
      const message = JSON.parse(String(raw));
      commands.push(message);
      if (message.method === 'Page.navigate') {
        targetUrl = message.params.url;
        websocket.send(
          JSON.stringify({
            id: message.id,
            error: { message: 'Inspected target navigated or closed' },
          }),
        );
        return;
      }
      const result =
        message.method === 'Runtime.evaluate'
          ? { result: { value: 'evaluated' } }
          : {};
      websocket.send(JSON.stringify({ id: message.id, result }));
    });
  });

  await new Promise((resolve) => server.listen(0, '127.0.0.1', resolve));
  t.after(async () => {
    for (const clientSocket of sockets.clients) clientSocket.terminate();
    await new Promise((resolve) => sockets.close(resolve));
    await new Promise((resolve) => server.close(resolve));
  });
  const { port } = server.address();

  const listed = await invoke('list', { port });
  const created = await invoke('new-page', { port });
  const evaluated = await invoke('evaluate', {
    port,
    targetId: 'target-1',
    expression: '42',
  });
  const inserted = await invoke('insert-text', {
    port,
    targetId: 'target-1',
    text: 'native input',
  });
  const navigated = await invoke('navigate', {
    port,
    targetId: 'target-1',
    url: 'https://www.douyin.com/search/demo?type=video',
  });

  assert.equal(listed.targets[0].id, 'target-1');
  assert.equal(created.targetId, 'target-1');
  assert.equal(evaluated.value, 'evaluated');
  assert.equal(inserted.success, true);
  assert.equal(navigated.recovered, true);
  assert.equal(targetUrl, 'https://www.douyin.com/search/demo?type=video');
  assert.ok(requests.some((request) => request.url === '/json/new' && request.method === 'PUT'));
  assert.deepEqual(
    commands.slice(0, 3).map((command) => command.method),
    ['Runtime.enable', 'Page.enable', 'Runtime.evaluate'],
  );
  assert.ok(
    commands.some(
      (command) => command.method === 'Input.insertText' && command.params.text === 'native input',
    ),
  );
  assert.ok(commands.every((command) => !('sessionId' in command)));
});

async function fixture(t, options = {}) {
  const commands = [];
  const requests = [];
  const server = http.createServer((req, res) => {
    requests.push(req.url);
    if (options.http) return options.http(req, res, server.address().port);
    if (req.url === '/json/version') {
      res.end(JSON.stringify({ Browser: 'Chrome/test', 'Protocol-Version': '1.3', webSocketDebuggerUrl: 'ws://private-browser-endpoint' }));
      return;
    }
    const target = {
      id: 'target', type: 'page', url: 'about:blank',
      webSocketDebuggerUrl: `ws://127.0.0.1:${server.address().port}/devtools/page/target`,
      ...options.target,
    };
    res.end(JSON.stringify([target]));
  });
  const sockets = new WebSocketServer({ server });
  sockets.on('connection', (socket) => {
    socket.on('message', (raw) => {
      const command = JSON.parse(String(raw));
      commands.push(command);
      if (['Runtime.enable', 'Page.enable'].includes(command.method)) {
        socket.send(JSON.stringify({ id: command.id, result: {} }));
      } else if (options.reply) {
        options.reply(socket, command);
      } else {
        socket.send(JSON.stringify({ id: command.id, result: { result: { type: 'string', value: command.params.expression } } }));
      }
    });
  });
  await new Promise((resolve) => server.listen(0, '127.0.0.1', resolve));
  t.after(async () => {
    for (const socket of sockets.clients) socket.terminate();
    await new Promise((resolve) => sockets.close(resolve));
    await new Promise((resolve) => server.close(resolve));
  });
  return { port: server.address().port, requests, commands };
}

async function failure(mode, payload) {
  let error;
  try {
    await invoke(mode, payload);
  } catch (caught) {
    error = caught;
  }
  assert.ok(error, 'bridge should exit with a failure');
  assert.equal(error.code, 1, error.stderr);
  const result = JSON.parse(error.stdout);
  assert.equal(result.success, false);
  return result;
}

test('bridge rejects remote hosts and invalid ports before connecting', async () => {
  for (const payload of [{ host: 'example.test' }, { host: '0.0.0.0' }, { host: '::ffff:192.0.2.1' }, { port: 0 }, { port: 65536 }, { port: '9222' }, { port: true }]) {
    assert.equal((await failure('list', payload)).error_code, 'invalid_endpoint');
  }
});

test('bridge validates advertised WebSocket endpoints before connecting', async (t) => {
  for (const url of ['ws://example.test/page', 'ws://127.0.0.1:1/page', 'http://127.0.0.1/page', 'ws://user:pass@127.0.0.1/page']) {
    const mock = await fixture(t, { target: { webSocketDebuggerUrl: url } });
    const result = await failure('evaluate', { port: mock.port, targetId: 'target', expression: '42' });
    assert.equal(result.error_code, 'invalid_endpoint');
    assert.equal(mock.commands.length, 0);
  }
});

test('bridge rejects JavaScript exceptions and nonserializable results', async (t) => {
  for (const [result, code] of [
    [{ result: { subtype: 'error' }, exceptionDetails: { text: 'Uncaught' } }, 'evaluation_failed'],
    [{ result: { type: 'bigint', unserializableValue: '1n' } }, 'invalid_response'],
    [{}, 'invalid_response'],
  ]) {
    const mock = await fixture(t, { reply: (socket, command) => socket.send(JSON.stringify({ id: command.id, result })) });
    assert.equal((await failure('evaluate', { port: mock.port, targetId: 'target', expression: '42' })).error_code, code);
    assert.equal(mock.commands.filter((command) => command.method === 'Runtime.evaluate').length, 1);
  }
});

test('bridge rejects Page.navigate errorText', async (t) => {
  const mock = await fixture(t, { reply: (socket, command) => socket.send(JSON.stringify({ id: command.id, result: { errorText: 'net::ERR_NAME_NOT_RESOLVED' } })) });
  const result = await failure('navigate', { port: mock.port, targetId: 'target', url: 'https://example.test/' });
  assert.equal(result.error_code, 'navigation_failed');
});

test('navigation recovery never accepts a different target URL', async (t) => {
  const mock = await fixture(t, { reply: (socket, command) => socket.send(JSON.stringify({ id: command.id, error: { message: 'Inspected target navigated or closed' } })) });
  const result = await failure('navigate', { port: mock.port, targetId: 'target', url: 'https://example.test/' });
  assert.equal(result.error_code, 'protocol_error');
  assert.equal(mock.commands.filter((command) => command.method === 'Page.navigate').length, 1);
});

test('malformed and interrupted WebSocket responses fail promptly', async (t) => {
  for (const [reply, code] of [
    [(socket) => socket.send('invalid JSON'), 'invalid_response'],
    [(socket) => socket.send('null'), 'invalid_response'],
    [(socket, command) => socket.send(JSON.stringify({ id: command.id, result: [] })), 'invalid_response'],
    [(socket) => socket.terminate(), 'connection_closed'],
    [(socket, command) => socket.send(JSON.stringify({ id: command.id, error: { message: 'protocol refused' } })), 'protocol_error'],
  ]) {
    const mock = await fixture(t, { reply });
    assert.equal((await failure('evaluate', { port: mock.port, targetId: 'target', expression: '42' })).error_code, code);
  }
});

test('malformed HTTP and non-page targets are rejected', async (t) => {
  for (const body of ['not JSON', '{}', '[null]']) {
    const mock = await fixture(t, { http: (_req, res) => res.end(body) });
    assert.equal((await failure('list', { port: mock.port })).error_code, 'invalid_response');
  }
  const mock = await fixture(t, { target: { type: 'service_worker' } });
  assert.equal((await failure('evaluate', { port: mock.port, targetId: 'target' })).error_code, 'target_not_found');
});

test('HTTP status and truncated responses are not successful JSON', async (t) => {
  const failed = await fixture(t, { http: (_req, res) => { res.writeHead(403); res.end('private body'); } });
  const result = await failure('list', { port: failed.port });
  assert.equal(result.error_code, 'http_error');
  assert.ok(!result.error.includes('private body'));
  const truncated = await fixture(t, { http: (_req, res) => { res.writeHead(200, { 'Content-Length': '100' }); res.write('['); setImmediate(() => res.destroy()); } });
  assert.equal((await failure('list', { port: truncated.port })).success, false);
});

test('version is read-only and omits the debugger address', async (t) => {
  const mock = await fixture(t);
  const result = await invoke('version', { port: mock.port });
  assert.deepEqual(result, { success: true, browser: 'Chrome/test', protocol_version: '1.3' });
  assert.deepEqual(mock.requests, ['/json/version']);
  assert.equal(mock.commands.length, 0);
});

test('stdin transports large Unicode expressions without command-line limits', async (t) => {
  const mock = await fixture(t);
  const expression = '中文内容😀'.repeat(12_000);
  const payload = { port: mock.port, targetId: 'target', expression };
  const result = await new Promise((resolve, reject) => {
    const child = spawn(process.execPath, [client, 'evaluate', '-'], { timeout: 10_000 });
    let stdout = '';
    let stderr = '';
    child.stdout.setEncoding('utf8');
    child.stdout.on('data', (chunk) => { stdout += chunk; });
    child.stderr.on('data', (chunk) => { stderr += chunk; });
    child.on('error', reject);
    child.on('close', (code) => code === 0 ? resolve(JSON.parse(stdout)) : reject(new Error(stderr || stdout)));
    child.stdin.end(JSON.stringify(payload));
  });
  assert.equal(result.value, expression);
});
