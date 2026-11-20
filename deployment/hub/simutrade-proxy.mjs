import {request as httpRequest} from 'node:http';

export function proxySimuTrade(request, response) {
  const prefix = '/api/simutrade';
  if (!request.url?.startsWith(prefix + '/')) return false;
  const headers = {...request.headers};
  delete headers.connection;
  delete headers['transfer-encoding'];
  const upstream = httpRequest({
    host: '127.0.0.1', port: 8081,
    path: '/api' + request.url.slice(prefix.length),
    method: request.method, headers, timeout: 30000
  }, result => {
    response.writeHead(result.statusCode || 502, result.headers);
    result.pipe(response);
  });
  upstream.on('timeout', () => upstream.destroy());
  upstream.on('error', () => {
    if (!response.headersSent) {
      response.writeHead(503, {'Content-Type': 'application/json', 'Cache-Control': 'no-store'});
      response.end(JSON.stringify({error: 'SimuTrade account service is temporarily unavailable. Please retry.'}));
    } else response.end();
  });
  let bytes = 0;
  request.on('data', chunk => {
    bytes += chunk.length;
    if (bytes > 100000) {
      upstream.destroy();
      request.destroy();
    }
  });
  request.pipe(upstream);
  return true;
}
