const MANTLE_NS = 'iits-menu-1784065700396';
const MANTLE_KEY = process.env.MANTLE_KEY || '2eac674f1e7e507087fb122fd79180a2188a531a9ef060681697ad29ddbc2b68';
const MANTLE_URL = `https://mantledb.sh/v2/${MANTLE_NS}/menu`;
const GITHUB_MENU_URL =
  'https://raw.githubusercontent.com/harrisqazi/islandsinthestream/main/menu.json';
const ADMIN_PASSWORD = process.env.MENU_ADMIN_PASSWORD || 'islands2026';

function send(res, status, body) {
  res.statusCode = status;
  res.setHeader('Content-Type', 'application/json; charset=utf-8');
  res.setHeader('Cache-Control', 'no-store, max-age=0, must-revalidate');
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'GET, PUT, POST, OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type');
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

function normalizeMenu(payload) {
  if (Array.isArray(payload)) return payload;
  if (payload && Array.isArray(payload.data)) return payload.data;
  if (payload && Array.isArray(payload.value)) return payload.value;
  if (payload && Array.isArray(payload.menu)) return payload.menu;
  return null;
}

async function fetchJson(url, options) {
  const r = await fetch(url, { cache: 'no-store', ...options });
  const text = await r.text();
  let json = null;
  try {
    json = text ? JSON.parse(text) : null;
  } catch {
    json = null;
  }
  return { ok: r.ok, status: r.status, text, json };
}

async function loadMenu() {
  const primary = await fetchJson(MANTLE_URL);
  const menu = normalizeMenu(primary.json);
  if (primary.ok && menu) return menu;

  const fallback = await fetchJson(GITHUB_MENU_URL + '?t=' + Date.now());
  const fallbackMenu = normalizeMenu(fallback.json);
  if (fallback.ok && fallbackMenu) return fallbackMenu;

  throw new Error(
    'Failed to load menu (mantle ' +
      primary.status +
      ', github ' +
      fallback.status +
      ')'
  );
}

async function saveMenu(menu) {
  const r = await fetchJson(MANTLE_URL, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-Mantle-Key': MANTLE_KEY,
    },
    body: JSON.stringify(menu),
  });
  if (!r.ok) {
    throw new Error(
      'Failed to save menu (' + r.status + '): ' + String(r.text || '').slice(0, 200)
    );
  }
  // Ensure public visitors can keep reading without the key.
  await fetchJson(`https://mantledb.sh/v2/visibility/${MANTLE_NS}/menu`, {
    method: 'PUT',
    headers: {
      'Content-Type': 'application/json',
      'X-Mantle-Key': MANTLE_KEY,
    },
    body: JSON.stringify({ public_read: true }),
  });
}

module.exports = async function handler(req, res) {
  try {
    if (req.method === 'OPTIONS') {
      return send(res, 204, {});
    }

    if (req.method === 'GET') {
      const menu = await loadMenu();
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

      await saveMenu(body.menu);
      return send(res, 200, { ok: true });
    }

    res.setHeader('Allow', 'GET, PUT, POST, OPTIONS');
    return send(res, 405, { error: 'Method not allowed' });
  } catch (err) {
    return send(res, 500, { error: err.message || 'Server error' });
  }
};
