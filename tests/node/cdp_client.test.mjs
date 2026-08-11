import assert from 'node:assert/strict';
import { execFile } from 'node:child_process';
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
  const navigated = await invoke('navigate', {
    port,
    targetId: 'target-1',
    url: 'https://www.douyin.com/search/demo?type=video',
  });

  assert.equal(listed.targets[0].id, 'target-1');
  assert.equal(created.targetId, 'target-1');
  assert.equal(evaluated.value, 'evaluated');
  assert.equal(navigated.recovered, true);
  assert.equal(targetUrl, 'https://www.douyin.com/search/demo?type=video');
  assert.ok(requests.some((request) => request.url === '/json/new' && request.method === 'PUT'));
  assert.deepEqual(
    commands.slice(0, 3).map((command) => command.method),
    ['Runtime.enable', 'Page.enable', 'Runtime.evaluate'],
  );
  assert.ok(commands.every((command) => !('sessionId' in command)));
});
