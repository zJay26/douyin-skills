#!/usr/bin/env node
import { spawn, spawnSync } from 'node:child_process';
import { existsSync, mkdtempSync, mkdirSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import http from 'node:http';
import { tmpdir } from 'node:os';
import { basename, dirname, join, resolve, sep } from 'node:path';
import process from 'node:process';
import { fileURLToPath, pathToFileURL } from 'node:url';
import WebSocket from 'ws';

const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const DEFAULT_OUTPUT = join(ROOT, 'assets', 'demo.gif');
const DEMO_PAGE = join(ROOT, 'assets', 'demo', 'index.html');
const WIDTH = 960;
const HEIGHT = 540;

function parseArgs(argv) {
  const options = { output: DEFAULT_OUTPUT, fps: 5, duration: 40 };
  for (let index = 0; index < argv.length; index += 1) {
    const value = argv[index];
    if (value === '--output') options.output = resolve(argv[++index]);
    else if (value === '--fps') options.fps = Number(argv[++index]);
    else if (value === '--duration') options.duration = Number(argv[++index]);
    else throw new Error(`unknown argument: ${value}`);
  }
  if (!Number.isInteger(options.fps) || options.fps < 1 || options.fps > 15) {
    throw new Error('--fps must be an integer between 1 and 15');
  }
  if (
    !Number.isFinite(options.duration)
    || options.duration < 30
    || options.duration > 45
  ) {
    throw new Error('--duration must be between 30 and 45 seconds');
  }
  return options;
}

function findChrome() {
  const candidates = [
    process.env.CHROME_BIN,
    process.platform === 'win32'
      && join(
        process.env.PROGRAMFILES || '',
        'Google',
        'Chrome',
        'Application',
        'chrome.exe',
      ),
    process.platform === 'win32'
      && join(
        process.env['PROGRAMFILES(X86)'] || '',
        'Google',
        'Chrome',
        'Application',
        'chrome.exe',
      ),
    process.platform === 'darwin'
      && '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
    '/usr/bin/google-chrome',
    '/usr/bin/google-chrome-stable',
    '/usr/bin/chromium',
    '/usr/bin/chromium-browser',
  ].filter(Boolean);
  const found = candidates.find((candidate) => existsSync(candidate));
  if (!found) {
    throw new Error('Chrome/Chromium was not found; set CHROME_BIN explicitly');
  }
  return found;
}

function commandExists(command) {
  const probe = spawnSync(command, ['-version'], {
    encoding: 'utf8',
    windowsHide: true,
  });
  return !probe.error && probe.status === 0;
}

function requestJson(port, path) {
  return new Promise((resolvePromise, reject) => {
    const request = http.get(
      { host: '127.0.0.1', port, path, timeout: 3000 },
      (response) => {
        let body = '';
        response.setEncoding('utf8');
        response.on('data', (chunk) => {
          body += chunk;
        });
        response.on('end', () => {
          if (
            (response.statusCode || 0) < 200
            || (response.statusCode || 0) >= 300
          ) {
            reject(
              new Error(`Chrome returned HTTP ${response.statusCode} for ${path}`),
            );
            return;
          }
          try {
            resolvePromise(JSON.parse(body));
          } catch (error) {
            reject(new Error(`Chrome returned invalid JSON: ${error.message}`));
          }
        });
      },
    );
    request.on('timeout', () => {
      request.destroy(new Error('Chrome request timed out'));
    });
    request.on('error', reject);
  });
}

async function waitForDebugPort(profileDir, chromeProcess) {
  const activePortFile = join(profileDir, 'DevToolsActivePort');
  for (let attempt = 0; attempt < 100; attempt += 1) {
    if (chromeProcess.exitCode !== null) {
      throw new Error(`Chrome exited with code ${chromeProcess.exitCode}`);
    }
    if (existsSync(activePortFile)) {
      const [port] = readFileSync(activePortFile, 'utf8')
        .trim()
        .split(/\r?\n/);
      if (Number(port) > 0) return Number(port);
    }
    await new Promise((resolvePromise) => setTimeout(resolvePromise, 100));
  }
  throw new Error('Chrome did not expose a debugging port');
}

async function connectTarget(target) {
  const socket = new WebSocket(target.webSocketDebuggerUrl, {
    handshakeTimeout: 10_000,
  });
  const pending = new Map();
  let nextId = 0;

  await new Promise((resolvePromise, reject) => {
    socket.once('open', resolvePromise);
    socket.once('error', reject);
  });

  socket.on('message', (raw) => {
    const message = JSON.parse(String(raw));
    if (!message.id || !pending.has(message.id)) return;
    const { resolvePromise, reject, timer } = pending.get(message.id);
    clearTimeout(timer);
    pending.delete(message.id);
    if (message.error) {
      reject(new Error(message.error.message || JSON.stringify(message.error)));
    } else {
      resolvePromise(message.result || {});
    }
  });

  const send = (method, params = {}) => new Promise((resolvePromise, reject) => {
    const id = ++nextId;
    const timer = setTimeout(() => {
      pending.delete(id);
      reject(new Error(`CDP command timed out: ${method}`));
    }, 20_000);
    pending.set(id, { resolvePromise, reject, timer });
    socket.send(JSON.stringify({ id, method, params }));
  });

  return { send, close: () => socket.close() };
}

async function waitForDemo(send) {
  for (let attempt = 0; attempt < 100; attempt += 1) {
    const result = await send('Runtime.evaluate', {
      expression:
        'document.readyState === "complete"'
        + ' && typeof window.setDemoTime === "function"',
      returnByValue: true,
    });
    if (result.result?.value === true) return;
    await new Promise((resolvePromise) => setTimeout(resolvePromise, 100));
  }
  throw new Error('demo page did not become ready');
}

async function removeTemporaryRoot(path) {
  const resolvedPath = resolve(path);
  const resolvedTemp = resolve(tmpdir());
  if (
    !resolvedPath.startsWith(`${resolvedTemp}${sep}`)
    || !basename(resolvedPath).startsWith('douyin-skills-demo-')
  ) {
    throw new Error(`refusing to remove unexpected temporary path: ${resolvedPath}`);
  }
  for (let attempt = 0; attempt < 30; attempt += 1) {
    try {
      rmSync(resolvedPath, { recursive: true, force: true });
      return;
    } catch (error) {
      if (!['EBUSY', 'EPERM'].includes(error.code) || attempt === 29) throw error;
      await new Promise((resolvePromise) => setTimeout(resolvePromise, 100));
    }
  }
}

async function stopChrome(client, chromeProcess) {
  try {
    await client?.send('Browser.close');
  } catch {
    // The process may already be closing after the target WebSocket disconnects.
  }
  client?.close();
  for (let attempt = 0; attempt < 30 && chromeProcess.exitCode === null; attempt += 1) {
    await new Promise((resolvePromise) => setTimeout(resolvePromise, 100));
  }
  if (chromeProcess.exitCode === null) chromeProcess.kill();
  for (let attempt = 0; attempt < 30 && chromeProcess.exitCode === null; attempt += 1) {
    await new Promise((resolvePromise) => setTimeout(resolvePromise, 100));
  }
}

async function render(options) {
  if (!existsSync(DEMO_PAGE)) {
    throw new Error(`demo source is missing: ${DEMO_PAGE}`);
  }
  if (!commandExists('ffmpeg')) {
    throw new Error('ffmpeg is required to render the animated GIF');
  }

  const tempRoot = mkdtempSync(join(tmpdir(), 'douyin-skills-demo-'));
  const profileDir = join(tempRoot, 'chrome-profile');
  const framesDir = join(tempRoot, 'frames');
  mkdirSync(profileDir);
  mkdirSync(framesDir);
  mkdirSync(dirname(options.output), { recursive: true });

  const chromeArgs = [
    '--headless=new',
    '--remote-debugging-address=127.0.0.1',
    '--remote-debugging-port=0',
    `--user-data-dir=${profileDir}`,
    `--window-size=${WIDTH},${HEIGHT}`,
    '--force-device-scale-factor=1',
    '--hide-scrollbars',
    '--disable-gpu',
    '--disable-dev-shm-usage',
    '--disable-background-timer-throttling',
    '--no-first-run',
    '--no-default-browser-check',
    'about:blank',
  ];
  if (
    process.platform !== 'win32'
    && typeof process.getuid === 'function'
    && process.getuid() === 0
  ) {
    chromeArgs.push('--no-sandbox');
  }

  const chromeProcess = spawn(findChrome(), chromeArgs, {
    stdio: 'ignore',
    windowsHide: true,
  });
  let client;
  try {
    const port = await waitForDebugPort(profileDir, chromeProcess);
    const targets = await requestJson(port, '/json/list');
    const target = targets.find((item) => item.type === 'page');
    if (!target?.webSocketDebuggerUrl) {
      throw new Error('Chrome did not expose a page target');
    }
    client = await connectTarget(target);
    const { send } = client;
    await send('Page.enable');
    await send('Runtime.enable');
    await send('Emulation.setDeviceMetricsOverride', {
      width: WIDTH,
      height: HEIGHT,
      deviceScaleFactor: 1,
      mobile: false,
      screenWidth: WIDTH,
      screenHeight: HEIGHT,
    });
    await send('Page.navigate', { url: pathToFileURL(DEMO_PAGE).href });
    await waitForDemo(send);
    await send('Runtime.evaluate', {
      expression: 'document.fonts && document.fonts.ready',
      awaitPromise: true,
    });

    const frameCount = Math.round(options.duration * options.fps);
    for (let frame = 0; frame < frameCount; frame += 1) {
      const time = (frame + 0.5) / options.fps;
      await send('Runtime.evaluate', {
        expression: `window.setDemoTime(${time.toFixed(3)})`,
        returnByValue: true,
      });
      const screenshot = await send('Page.captureScreenshot', {
        format: 'png',
        fromSurface: true,
        captureBeyondViewport: false,
      });
      const filename = join(
        framesDir,
        `frame-${String(frame).padStart(4, '0')}.png`,
      );
      writeFileSync(filename, Buffer.from(screenshot.data, 'base64'));
      if ((frame + 1) % 25 === 0 || frame + 1 === frameCount) {
        process.stdout.write(`Rendered ${frame + 1}/${frameCount} frames\n`);
      }
    }

    const ffmpegArgs = [
      '-y',
      '-hide_banner',
      '-loglevel',
      'warning',
      '-framerate',
      String(options.fps),
      '-i',
      join(framesDir, 'frame-%04d.png'),
      '-filter_complex',
      '[0:v]split[a][b];'
        + '[a]palettegen=max_colors=96:stats_mode=diff[p];'
        + '[b][p]paletteuse=dither=bayer:bayer_scale=3:diff_mode=rectangle',
      '-loop',
      '0',
      options.output,
    ];
    const encoded = spawnSync('ffmpeg', ffmpegArgs, {
      stdio: 'inherit',
      windowsHide: true,
    });
    if (encoded.status !== 0) {
      throw new Error(`ffmpeg exited with code ${encoded.status}`);
    }
    process.stdout.write(`Created ${options.output}\n`);
  } finally {
    await stopChrome(client, chromeProcess);
    await removeTemporaryRoot(tempRoot);
  }
}

render(parseArgs(process.argv.slice(2))).catch((error) => {
  process.stderr.write(`${error.stack || error.message || String(error)}\n`);
  process.exit(1);
});
