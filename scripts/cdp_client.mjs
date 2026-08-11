#!/usr/bin/env node
import http from 'node:http';
import process from 'node:process';
import WebSocket from 'ws';

const HTTP_TIMEOUT_MS = 10_000;
const CDP_TIMEOUT_MS = 30_000;

function sameUrl(actual, expected) {
  try {
    return new URL(actual).href === new URL(expected).href;
  } catch {
    return actual === expected;
  }
}

function httpRequestJson(host, port, path, method = 'GET') {
  return new Promise((resolve, reject) => {
    const req = http.request({ host, port, path, method }, (res) => {
      let data = '';
      res.setEncoding('utf8');
      res.on('data', (chunk) => {
        data += chunk;
        if (data.length > 5_000_000) req.destroy(new Error('CDP HTTP response is too large'));
      });
      res.on('end', () => {
        const statusCode = res.statusCode || 0;
        if (statusCode < 200 || statusCode >= 300) {
          reject(new Error(`CDP HTTP ${method} ${path} failed with ${statusCode}: ${data.slice(0, 500)}`));
          return;
        }
        try {
          resolve(JSON.parse(data || 'null'));
        } catch (err) {
          reject(new Error(`CDP HTTP ${method} ${path} returned invalid JSON: ${err.message}`));
        }
      });
    });
    req.setTimeout(HTTP_TIMEOUT_MS, () => req.destroy(new Error(`CDP HTTP ${method} ${path} timed out`)));
    req.on('error', reject);
    req.end();
  });
}

async function withTarget(host, port, targetId, fn) {
  const targets = await httpRequestJson(host, port, '/json/list');
  const target = (targets || []).find((t) => t.id === targetId || t.targetId === targetId);
  if (!target?.webSocketDebuggerUrl) throw new Error(`target not found: ${targetId}`);
  const ws = new WebSocket(target.webSocketDebuggerUrl, { handshakeTimeout: HTTP_TIMEOUT_MS });
  let nextId = 0;
  const pending = new Map();

  const failPending = (error) => {
    for (const { reject, timer } of pending.values()) {
      clearTimeout(timer);
      reject(error);
    }
    pending.clear();
  };

  const send = (method, params = {}) =>
    new Promise((resolve, reject) => {
      const id = ++nextId;
      const timer = setTimeout(() => {
        pending.delete(id);
        reject(new Error(`CDP command timed out: ${method}`));
      }, CDP_TIMEOUT_MS);
      pending.set(id, { resolve, reject, timer });
      ws.send(JSON.stringify({ id, method, params }), (error) => {
        if (!error) return;
        clearTimeout(timer);
        pending.delete(id);
        reject(error);
      });
    });

  ws.on('message', (raw) => {
    let msg;
    try {
      msg = JSON.parse(String(raw));
    } catch (error) {
      failPending(new Error(`CDP WebSocket returned invalid JSON: ${error.message}`));
      return;
    }
    if (msg.id && pending.has(msg.id)) {
      const { resolve, reject, timer } = pending.get(msg.id);
      clearTimeout(timer);
      pending.delete(msg.id);
      if (msg.error) reject(new Error(msg.error.message || JSON.stringify(msg.error)));
      else resolve(msg.result || {});
    }
  });
  ws.on('close', () => failPending(new Error('CDP WebSocket closed')));

  await new Promise((resolve, reject) => {
    ws.once('open', resolve);
    ws.once('error', reject);
  });

  try {
    await send('Runtime.enable');
    await send('Page.enable');
    return await fn(send);
  } finally {
    ws.close();
  }
}

async function main() {
  const [, , mode, payloadJson] = process.argv;
  const input = JSON.parse(payloadJson || '{}');
  const host = input.host || '127.0.0.1';
  const port = Number(input.port || 9222);

  let result;
  if (mode === 'list') {
    const targets = await httpRequestJson(host, port, '/json/list');
    result = { success: true, targets };
  } else if (mode === 'new-page') {
    // Modern Chrome rejects GET for /json/new and requires PUT.
    const created = await httpRequestJson(host, port, '/json/new', 'PUT');
    result = { success: true, targetId: created.id || created.targetId, url: created.url };
  } else {
    const targetId = input.targetId;
    if (!targetId) throw new Error('targetId is required');
    result = await withTarget(host, port, targetId, async (send) => {
      if (mode === 'navigate') {
        try {
          await send('Page.navigate', { url: input.url });
        } catch (error) {
          const message = error instanceof Error ? error.message : String(error);
          if (!message.includes('Inspected target navigated or closed')) throw error;
          const targets = await httpRequestJson(host, port, '/json/list');
          const target = (targets || []).find((item) => item.id === targetId || item.targetId === targetId);
          if (!target || !sameUrl(target.url, input.url)) throw error;
          return { success: true, targetId, url: input.url, recovered: true };
        }
        return { success: true, targetId, url: input.url };
      }
      if (mode === 'evaluate') {
        const res = await send('Runtime.evaluate', {
          expression: input.expression,
          returnByValue: true,
          awaitPromise: true,
        });
        return { success: true, targetId, value: res.result?.value };
      }
      if (mode === 'keypress') {
        await send('Input.dispatchKeyEvent', {
          type: 'rawKeyDown',
          key: input.key,
          code: input.code,
          windowsVirtualKeyCode: input.keyCode,
          nativeVirtualKeyCode: input.keyCode,
        });
        if (input.text) {
          await send('Input.dispatchKeyEvent', {
            type: 'char',
            text: input.text,
            unmodifiedText: input.text,
            key: input.key || input.text,
            code: input.code,
            windowsVirtualKeyCode: input.keyCode,
            nativeVirtualKeyCode: input.keyCode,
          });
        }
        await send('Input.dispatchKeyEvent', {
          type: 'keyUp',
          key: input.key,
          code: input.code,
          windowsVirtualKeyCode: input.keyCode,
          nativeVirtualKeyCode: input.keyCode,
        });
        return { success: true, targetId };
      }
      if (mode === 'set-file-input-files') {
        const { root } = await send('DOM.getDocument');
        const { nodeId } = await send('DOM.querySelector', { nodeId: root.nodeId, selector: input.selector });
        if (!nodeId) return { success: false, targetId, error: 'selector not found' };
        await send('DOM.setFileInputFiles', { nodeId, files: input.files || [] });
        return { success: true, targetId, count: (input.files || []).length };
      }
      throw new Error(`unsupported mode: ${mode}`);
    });
  }

  process.stdout.write(`${JSON.stringify(result)}\n`);
}

main().catch((err) => {
  process.stderr.write(`${err.stack || err.message || String(err)}\n`);
  process.exit(1);
});
