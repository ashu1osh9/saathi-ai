// Layout-only preview when Python is unavailable. API calls fail explicitly with 503.
// This server is never used to run Saathi or to claim backend/speech verification.
const http = require('node:http');
const fs = require('node:fs');
const path = require('node:path');
const root = path.resolve(__dirname, '..');
const files = new Map([
  ['/', ['src/saathi/static/index.html', 'text/html; charset=utf-8']],
  ['/static/app.js', ['src/saathi/static/app.js', 'text/javascript; charset=utf-8']],
  ['/static/audio.js', ['src/saathi/static/audio.js', 'text/javascript; charset=utf-8']],
  ['/static/styles.css', ['src/saathi/static/styles.css', 'text/css; charset=utf-8']],
]);
http.createServer((request, response) => {
  if (request.url.startsWith('/api/')) {
    response.writeHead(503, {'Content-Type': 'application/json'});
    response.end(JSON.stringify({detail: 'Layout preview only. Start the Python backend for app features.'}));
    return;
  }
  const file = files.get(request.url);
  if (!file) { response.writeHead(404); response.end(); return; }
  response.writeHead(200, {'Content-Type': file[1], 'Cache-Control': 'no-store'});
  response.end(fs.readFileSync(path.join(root, file[0])));
}).listen(8766, '127.0.0.1', () => console.log('Layout-only preview: http://127.0.0.1:8766 (all API requests return 503)'));
