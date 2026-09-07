#!/usr/bin/env node
import http from 'node:http';
import { isIP } from 'node:net';
import process from 'node:process';
import WebSocket from 'ws';

const HTTP_TIMEOUT_MS = 10_000;
const CDP_TIMEOUT_MS = 30_000;
const MAX_BYTES = 5_000_000;
const MODES = new Set(['list', 'version', 'new-page', 'navigate', 'evaluate', 'keypress', 'insert-text', 'set-file-input-files']);

class BridgeError extends Error {
  constructor(code, message) {
    super(message);
    this.code = code;
  }
}

function loopbackHost(value) {
  const host = String(value).trim().toLowerCase();
  if (host === 'localhost') return '127.0.0.1';
  if (isIP(host) === 4 && host.startsWith('127.')) return host;
  if (isIP(host) === 6 && new URL(`http://[${host}]`).hostname === '[::1]') return '::1';
  throw new BridgeError('invalid_endpoint', 'CDP host must be a loopback address');
}

function debuggerUrl(value, host, port) {
  const url = new URL(value);
  const advertisedHost = url.hostname.replace(/^\[|\]$/g, '');
  if (url.protocol !== 'ws:' || url.username || url.password || url.hash
      || loopbackHost(advertisedHost) !== host || Number(url.port || 80) !== port) {
    throw new BridgeError('invalid_endpoint', 'Debugger WebSocket must use the selected loopback endpoint');
  }
  url.hostname = host.includes(':') ? `[${host}]` : host;
  return url.href;
}

async function readPayload(value) {
  if (value !== '-') return JSON.parse(value || '{}');
  const chunks = [];
  let size = 0;
  for await (const chunk of process.stdin) {
    size += chunk.length;
    if (size > MAX_BYTES) throw new BridgeError('invalid_input', 'CDP payload is too large');
    chunks.push(chunk);
  }
  return JSON.parse(Buffer.concat(chunks).toString('utf8'));
}

function sameUrl(actual, expected) {
  try {
    return new URL(actual).href === new URL(expected).href;
  } catch {
    return actual === expected;
  }
}

function httpRequestJson(host, port, path, method = 'GET') {
  return new Promise((resolve, reject) => {
    let size = 0;
    const req = http.request({ host, port, path, method }, (res) => {
      let data = '';
      res.setEncoding('utf8');
      res.on('data', (chunk) => {
        data += chunk;
        size += Buffer.byteLength(chunk);
        if (size > MAX_BYTES) req.destroy(new BridgeError('invalid_response', 'CDP HTTP response is too large'));
      });
      res.on('error', reject);
      res.on('aborted', () => reject(new BridgeError('connection_closed', 'CDP HTTP response was interrupted')));
      res.on('end', () => {
        clearTimeout(timer);
        const statusCode = res.statusCode || 0;
        if (statusCode < 200 || statusCode >= 300) {
          reject(new BridgeError('http_error', `CDP HTTP ${method} ${path} failed with ${statusCode}`));
          return;
        }
        try {
          resolve(JSON.parse(data || 'null'));
        } catch (err) {
          reject(new BridgeError('invalid_response', `CDP HTTP ${method} ${path} returned invalid JSON`));
        }
      });
    });
    const timer = setTimeout(() => req.destroy(new BridgeError('timeout', `CDP HTTP ${method} ${path} timed out`)), HTTP_TIMEOUT_MS);
    req.on('close', () => clearTimeout(timer));
    req.on('error', reject);
    req.end();
  });
}

async function withTarget(host, port, targetId, fn) {
  const targets = await httpRequestJson(host, port, '/json/list');
  if (!Array.isArray(targets)) throw new BridgeError('invalid_response', 'CDP target list must be an array');
  const target = targets.find((t) => t?.type === 'page' && (t.id === targetId || t.targetId === targetId));
  if (!target?.webSocketDebuggerUrl) throw new BridgeError('target_not_found', 'Requested page target was not found');
  const ws = new WebSocket(debuggerUrl(target.webSocketDebuggerUrl, host, port), {
    handshakeTimeout: HTTP_TIMEOUT_MS, maxPayload: MAX_BYTES, followRedirects: false,
  });
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
      if (ws.readyState !== WebSocket.OPEN) {
        reject(new BridgeError('connection_closed', 'CDP WebSocket is not open'));
        return;
      }
      const id = ++nextId;
      const timer = setTimeout(() => {
        pending.delete(id);
        reject(new BridgeError('timeout', `CDP command timed out: ${method}`));
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
      failPending(new BridgeError('invalid_response', 'CDP WebSocket returned invalid JSON'));
      return;
    }
    if (!msg || typeof msg !== 'object' || Array.isArray(msg)) {
      failPending(new BridgeError('invalid_response', 'CDP WebSocket returned an invalid message'));
      return;
    }
    if (msg.id && pending.has(msg.id)) {
      const { resolve, reject, timer } = pending.get(msg.id);
      clearTimeout(timer);
      pending.delete(msg.id);
      if (msg.error) reject(new BridgeError('protocol_error', msg.error.message || 'CDP protocol error'));
      else if (!msg.result || typeof msg.result !== 'object' || Array.isArray(msg.result)) {
        reject(new BridgeError('invalid_response', 'CDP command returned an invalid result'));
      } else resolve(msg.result);
    }
  });
  ws.on('error', failPending);
  ws.on('close', () => failPending(new BridgeError('connection_closed', 'CDP WebSocket closed')));

  try {
    await new Promise((resolve, reject) => {
      ws.once('open', resolve);
      ws.once('error', reject);
      ws.once('close', () => reject(new BridgeError('connection_closed', 'CDP WebSocket closed before opening')));
    });
    await send('Runtime.enable');
    await send('Page.enable');
    return await fn(send);
  } finally {
    failPending(new BridgeError('connection_closed', 'CDP session ended'));
    ws.terminate();
  }
}

async function main() {
  const [, , mode, payloadJson] = process.argv;
  if (!MODES.has(mode)) throw new BridgeError('invalid_input', 'Unsupported CDP mode');
  const input = await readPayload(payloadJson);
  if (!input || typeof input !== 'object' || Array.isArray(input)) throw new BridgeError('invalid_input', 'CDP payload must be an object');
  const host = loopbackHost(input.host ?? '127.0.0.1');
  const port = input.port ?? 9222;
  if (!Number.isInteger(port) || port < 1 || port > 65535) throw new BridgeError('invalid_endpoint', 'CDP port must be an integer from 1 to 65535');

  let result;
  if (mode === 'list') {
    const targets = await httpRequestJson(host, port, '/json/list');
    if (!Array.isArray(targets) || targets.some((target) => !target || typeof target !== 'object' || Array.isArray(target))) {
      throw new BridgeError('invalid_response', 'CDP target list must contain objects');
    }
    result = { success: true, targets };
  } else if (mode === 'version') {
    const version = await httpRequestJson(host, port, '/json/version');
    if (!version || typeof version !== 'object' || !version.Browser || !version['Protocol-Version']) {
      throw new BridgeError('invalid_response', 'CDP version response is incomplete');
    }
    result = { success: true, browser: version.Browser, protocol_version: version['Protocol-Version'] };
  } else if (mode === 'new-page') {
    // Modern Chrome rejects GET for /json/new and requires PUT.
    const created = await httpRequestJson(host, port, '/json/new', 'PUT');
    if (!created || typeof (created.id || created.targetId) !== 'string' || !(created.id || created.targetId)) throw new BridgeError('invalid_response', 'CDP did not return a new target ID');
    result = { success: true, targetId: created.id || created.targetId, url: created.url };
  } else {
    const targetId = input.targetId;
    if (!targetId) throw new Error('targetId is required');
    result = await withTarget(host, port, targetId, async (send) => {
      if (mode === 'navigate') {
        try {
          const navigation = await send('Page.navigate', { url: input.url });
          if (navigation.errorText) throw new BridgeError('navigation_failed', `Navigation failed: ${navigation.errorText}`);
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
        if (res.exceptionDetails || res.result?.subtype === 'error') {
          throw new BridgeError('evaluation_failed', 'JavaScript evaluation failed in the page');
        }
        if (!res.result || res.result.unserializableValue !== undefined) {
          throw new BridgeError('invalid_response', 'JavaScript result is not JSON serializable');
        }
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
      if (mode === 'insert-text') {
        await send('Input.insertText', { text: String(input.text || '') });
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

function outputError(err) {
  process.stdout.write(`${JSON.stringify({ success: false, error: err.message || String(err), error_code: err.code || 'bridge_error' })}\n`);
  process.exitCode = 1;
}

// A total deadline also bounds handshakes, setup commands and stalled stdin.
const deadline = setTimeout(() => {
  outputError(new BridgeError('timeout', 'CDP operation exceeded its total deadline'));
  process.exit(1);
}, 40_000);
main().catch(outputError).finally(() => clearTimeout(deadline));
