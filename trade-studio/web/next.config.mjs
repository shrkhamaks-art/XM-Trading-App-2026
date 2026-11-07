const configured = process.env.TRADE_STUDIO_BACKEND_ORIGIN;
const backend = configured ? new URL(configured) : new URL('http://127.0.0.1:8000');

if (!['http:', 'https:'].includes(backend.protocol) || backend.username || backend.password ||
    backend.pathname !== '/' || backend.search || backend.hash) {
  throw new Error('TRADE_STUDIO_BACKEND_ORIGIN must be an HTTP(S) origin');
}

export default {
  poweredByHeader: false,
  async rewrites() {
    return [
      { source: '/api/markets/btc-usd', destination: backend.origin + '/api/markets/btc-usd' },
      { source: '/app', destination: backend.origin + '/' },
      { source: '/api/:operation(code|verify|me|logout|logout-all)', destination: backend.origin + '/api/:operation' },
    ];
  },
};
