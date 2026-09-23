const http = require('http');
const fs = require('fs');
const path = require('path');

const port = Number(process.env.VITE_FRONTEND_PORT || 5100);
const backend = process.env.BACKEND_URL || 'http://127.0.0.1:5101';
const dist = path.join(__dirname, 'dist');
const types = { '.html': 'text/html; charset=utf-8', '.js': 'text/javascript; charset=utf-8', '.css': 'text/css; charset=utf-8', '.json': 'application/json', '.png': 'image/png', '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg', '.svg': 'image/svg+xml' };

function proxy(req, res) {
  const target = new URL(req.url, backend);
  const upstream = http.request(target, { method: req.method, headers: { ...req.headers, host: target.host } }, (upstreamRes) => {
    res.writeHead(upstreamRes.statusCode || 502, upstreamRes.headers);
    upstreamRes.pipe(res);
  });
  upstream.on('error', () => {
    res.writeHead(502, { 'content-type': 'application/json' });
    res.end(JSON.stringify({ message: 'Backend tidak tersedia' }));
  });
  req.pipe(upstream);
}

http.createServer((req, res) => {
  if (req.url.startsWith('/api') || req.url === '/health') return proxy(req, res);
  const cleanPath = decodeURIComponent(new URL(req.url, 'http://local').pathname);
  const requested = cleanPath === '/' ? '/index.html' : cleanPath;
  const filePath = path.normalize(path.join(dist, requested));
  const safePath = filePath.startsWith(dist) && fs.existsSync(filePath) && fs.statSync(filePath).isFile() ? filePath : path.join(dist, 'index.html');
  res.writeHead(200, { 'content-type': types[path.extname(safePath)] || 'application/octet-stream', 'cache-control': safePath.endsWith('index.html') ? 'no-cache' : 'public, max-age=31536000, immutable' });
  fs.createReadStream(safePath).pipe(res);
}).listen(port, '0.0.0.0', () => console.log(`SPP frontend proxy on ${port}, backend ${backend}`));
