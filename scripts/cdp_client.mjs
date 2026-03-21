#!/usr/bin/env node
import http from 'node:http';
import process from 'node:process';
import WebSocket from 'ws';

function httpGetJson(host, port, path) {
  return new Promise((resolve, reject) => {
    const req = http.request({ host, port, path, method: 'GET' }, (res) => {
      let data = '';
      res.setEncoding('utf8');
      res.on('data', (chunk) => (data += chunk));
      res.on('end', () => {
        try {
          resolve(JSON.parse(data || 'null'));
        } catch (err) {
          reject(err);
        }
      });
    });
    req.on('error', reject);
    req.end();
  });
}

async function withSession(host, port, targetId, fn) {
  const targets = await httpGetJson(host, port, '/json/list');
  const target = (targets || []).find((t) => t.id === targetId || t.targetId === targetId);
  if (!target?.webSocketDebuggerUrl) throw new Error(`target not found: ${targetId}`);
  const ws = new WebSocket(target.webSocketDebuggerUrl);
  let nextId = 0;
  const pending = new Map();
  let attachedSessionId = null;

  const send = (method, params = {}, sessionId) =>
    new Promise((resolve, reject) => {
      const id = ++nextId;
      pending.set(id, { resolve, reject });
      ws.send(JSON.stringify(sessionId ? { id, method, params, sessionId } : { id, method, params }));
    });

  ws.on('message', (raw) => {
    const msg = JSON.parse(String(raw));
    if (msg.id && pending.has(msg.id)) {
      const { resolve, reject } = pending.get(msg.id);
      pending.delete(msg.id);
      if (msg.error) reject(new Error(msg.error.message || JSON.stringify(msg.error)));
      else resolve(msg.result || {});
      return;
    }
    if (msg.method === 'Target.attachedToTarget') {
      attachedSessionId = msg.params.sessionId;
    }
  });

  await new Promise((resolve, reject) => {
    ws.once('open', resolve);
    ws.once('error', reject);
  });

  try {
    await send('Target.setAutoAttach', { autoAttach: true, waitForDebuggerOnStart: false, flatten: true });
    const attach = await send('Target.attachToTarget', { targetId, flatten: true });
    const sessionId = attach.sessionId || attachedSessionId;
    if (!sessionId) throw new Error('failed to attach to target');
    await send('Runtime.enable', {}, sessionId);
    await send('Page.enable', {}, sessionId);
    const out = await fn(send, sessionId);
    ws.close();
    return out;
  } catch (err) {
    ws.close();
    throw err;
  }
}

async function main() {
  const [, , mode, payloadJson] = process.argv;
  const input = JSON.parse(payloadJson || '{}');
  const host = input.host || '127.0.0.1';
  const port = Number(input.port || 9222);

  let result;
  if (mode === 'list') {
    const targets = await httpGetJson(host, port, '/json/list');
    result = { success: true, targets };
  } else if (mode === 'new-page') {
    const created = await httpGetJson(host, port, '/json/new');
    result = { success: true, targetId: created.id || created.targetId, url: created.url };
  } else {
    const targetId = input.targetId;
    result = await withSession(host, port, targetId, async (send, sessionId) => {
      if (mode === 'navigate') {
        await send('Page.navigate', { url: input.url }, sessionId);
        return { success: true, targetId, url: input.url };
      }
      if (mode === 'evaluate') {
        const res = await send('Runtime.evaluate', {
          expression: input.expression,
          returnByValue: true,
          awaitPromise: true,
        }, sessionId);
        return { success: true, targetId, value: res.result?.value };
      }
      if (mode === 'keypress') {
        await send('Input.dispatchKeyEvent', {
          type: 'rawKeyDown',
          key: input.key,
          code: input.code,
          windowsVirtualKeyCode: input.keyCode,
          nativeVirtualKeyCode: input.keyCode,
        }, sessionId);
        if (input.text) {
          await send('Input.dispatchKeyEvent', {
            type: 'char',
            text: input.text,
            unmodifiedText: input.text,
            key: input.key || input.text,
            code: input.code,
            windowsVirtualKeyCode: input.keyCode,
            nativeVirtualKeyCode: input.keyCode,
          }, sessionId);
        }
        await send('Input.dispatchKeyEvent', {
          type: 'keyUp',
          key: input.key,
          code: input.code,
          windowsVirtualKeyCode: input.keyCode,
          nativeVirtualKeyCode: input.keyCode,
        }, sessionId);
        return { success: true, targetId };
      }
      if (mode === 'set-file-input-files') {
        const { root } = await send('DOM.getDocument', {}, sessionId);
        const { nodeId } = await send('DOM.querySelector', { nodeId: root.nodeId, selector: input.selector }, sessionId);
        if (!nodeId) return { success: false, targetId, error: 'selector not found' };
        await send('DOM.setFileInputFiles', { nodeId, files: input.files || [] }, sessionId);
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
