import { existsSync } from 'node:fs';
import { resolve } from 'node:path';

import { createServer } from 'vite';

const apps = ['qf', 'mm', 'ir', 'tl'];
const renderRuntimeId = 'virtual:crowdcraft-render-runtime';
const resolvedRenderRuntimeId = `\0${renderRuntimeId}`;

const renderRuntimePlugin = {
  name: 'crowdcraft-render-runtime',
  resolveId(id) {
    return id === renderRuntimeId ? resolvedRenderRuntimeId : null;
  },
  load(id) {
    if (id !== resolvedRenderRuntimeId) {
      return null;
    }
    return `
      import React from 'react';
      import { renderToString } from 'react-dom/server';
      export { React, renderToString };
    `;
  },
};

function createStorage() {
  const values = new Map();
  return {
    getItem: (key) => values.get(key) ?? null,
    setItem: (key, value) => values.set(key, String(value)),
    removeItem: (key) => values.delete(key),
    clear: () => values.clear(),
    key: (index) => Array.from(values.keys())[index] ?? null,
    get length() {
      return values.size;
    },
  };
}

function installBrowserGlobals(origin) {
  const localStorage = createStorage();
  const sessionStorage = createStorage();
  const location = {
    pathname: '/',
    search: '',
    hash: '',
    href: `${origin}/`,
    origin,
    assign() {},
    replace() {},
  };
  const history = {
    state: null,
    go() {},
    pushState() {},
    replaceState() {},
  };
  const navigator = {
    onLine: true,
    userAgent: 'Crowdcraft initial-render verification',
  };
  const window = {
    location,
    history,
    localStorage,
    sessionStorage,
    navigator,
    addEventListener() {},
    removeEventListener() {},
    dispatchEvent() {},
    matchMedia() {
      return {
        matches: false,
        addEventListener() {},
        removeEventListener() {},
      };
    },
    setTimeout,
    clearTimeout,
  };

  globalThis.window = window;
  globalThis.document = {
    defaultView: window,
    hidden: false,
    cookie: '',
    addEventListener() {},
    removeEventListener() {},
    querySelector() {
      return null;
    },
  };
  Object.defineProperty(globalThis, 'navigator', {
    value: navigator,
    configurable: true,
  });
  globalThis.localStorage = localStorage;
  globalThis.sessionStorage = sessionStorage;
}

for (const app of apps) {
  const appRoot = resolve(`frontend/${app}`);
  const tsConfigPath = resolve(appRoot, 'vite.config.ts');
  const jsConfigPath = resolve(appRoot, 'vite.config.js');
  const configFile = existsSync(tsConfigPath) ? tsConfigPath : jsConfigPath;

  installBrowserGlobals(`https://${app}.crowdcraft.test`);

  const vite = await createServer({
    root: appRoot,
    configFile,
    plugins: [renderRuntimePlugin],
    appType: 'custom',
    logLevel: 'error',
    server: { middlewareMode: true },
  });

  try {
    const { React, renderToString } = await vite.ssrLoadModule(renderRuntimeId);
    const { default: App } = await vite.ssrLoadModule('/src/App.tsx');
    const html = renderToString(React.createElement(App));
    if (!html.trim()) {
      throw new Error(`${app} produced an empty initial render`);
    }
    console.log(`${app}: initial render passed`);
  } finally {
    await vite.close();
  }
}
