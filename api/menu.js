const BIN_URL = 'https://jsonbin-zeta.vercel.app/api/bins/LHYtPGMP7F';
const ADMIN_PASSWORD = process.env.MENU_ADMIN_PASSWORD || 'islands2026';

function send(res, status, body) {
  res.statusCode = status;
  res.setHeader('Content-Type', 'application/json; charset=utf-8');
  res.setHeader('Cache-Control', 'no-store, max-age=0, must-revalidate');
  res.end(JSON.stringify(body));
}

function readBody(req) {
  return new Promise((resolve, reject) => {
    const chunks = [];
    req.on('data', (c) => chunks.push(c));
    req.on('end', () => {
      try {
        const raw = Buffer.concat(chunks).toString('utf8');
        resolve(raw ? JSON.parse(raw) : {});
      } catch (err) {
        reject(err);
      }
    });
    req.on('error', reject);
  });
}

async function fetchBin() {
  const r = await fetch(BIN_URL, { cache: 'no-store' });
  if (!r.ok) throw new Error('Failed to load menu (' + r.status + ')');
  const payload = await r.json();
  return Array.isArray(payload) ? payload : payload.data;
}

module.exports = async function handler(req, res) {
  try {
    if (req.method === 'GET') {
      const menu = await fetchBin();
      return send(res, 200, menu);
    }

    if (req.method === 'PUT' || req.method === 'POST') {
      const body = await readBody(req);
      if (!body || body.password !== ADMIN_PASSWORD) {
        return send(res, 401, { error: 'Unauthorized' });
      }
      if (!Array.isArray(body.menu)) {
        return send(res, 400, { error: 'menu must be an array' });
      }

      const r = await fetch(BIN_URL, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body.menu),
      });
      if (!r.ok) {
        const text = await r.text();
        return send(res, 502, { error: 'Failed to save menu', detail: text.slice(0, 200) });
      }

      return send(res, 200, { ok: true });
    }

    res.setHeader('Allow', 'GET, PUT, POST');
    return send(res, 405, { error: 'Method not allowed' });
  } catch (err) {
    return send(res, 500, { error: err.message || 'Server error' });
  }
};
