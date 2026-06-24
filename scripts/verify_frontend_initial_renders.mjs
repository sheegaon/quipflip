import { createRequire } from 'node:module';
import { resolve } from 'node:path';
import { pathToFileURL } from 'node:url';

import { createServer } from 'vite';

const apps = ['qf', 'mm', 'ir', 'tl'];

function createStorage() {
  const values = new Map();
  return {
    getItem: (key) => values.get(key) ?? null,
    setItem: (key, value) => values.set(key, String(value)),
    removeItem: (key) => values.delete(key),
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
  const requireFromApp = createRequire(pathToFileURL(resolve(appRoot, 'package.json')));
  const React = requireFromApp('react');
  const { renderToString } = requireFromApp('react-dom/server');

  installBrowserGlobals(`https://${app}.crowdcraft.test`);

  const vite = await createServer({
    root: appRoot,
    configFile: resolve(appRoot, 'vite.config.ts'),
    appType: 'custom',
    logLevel: 'error',
    server: { middlewareMode: true },
  });

  try {
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
