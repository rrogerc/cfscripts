import type { Plugin } from 'vite';
import type { IncomingMessage, ServerResponse } from 'node:http';
import { createDemoApi } from './demo-api';

export function demoPlugin(): Plugin {
  const api = createDemoApi();
  const middleware = (req: IncomingMessage, res: ServerResponse, next: () => void) => {
    const pathname = new URL(req.url ?? '/', 'http://localhost').pathname;
    if (!pathname.startsWith('/api/')) return next();
    const result = api(pathname, req.method);
    res.writeHead(result.status, { 'Content-Type': 'application/json', 'Cache-Control': 'no-store' });
    res.end(JSON.stringify(result.body));
  };
  return {
    name: 'local-phone-demo',
    configureServer(server) {
      server.middlewares.use(middleware);
    },
    configurePreviewServer(server) {
      server.middlewares.use(middleware);
    },
  };
}
