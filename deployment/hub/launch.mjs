import {spawn} from 'node:child_process';

let worker;
let stopping = false;
let attempts = 0;
function startPracticeService() {
  worker = spawn('python3', ['/app/simutrade/production.py'], {
    env: {...process.env, PORT: '8081', ST_BIND_HOST: '127.0.0.1'},
    stdio: ['ignore', 'inherit', 'inherit']
  });
  worker.on('error', error => console.error('SimuTrade worker could not start:', error.code));
  worker.on('exit', () => {
    if (!stopping) {
      const delay = Math.min(30000, 1000 * (2 ** Math.min(attempts++, 5)));
      setTimeout(startPracticeService, delay).unref();
    }
  });
}
startPracticeService();
process.on('SIGTERM', () => {
  stopping = true;
  worker?.kill('SIGTERM');
  setTimeout(() => process.exit(0), 800).unref();
});

// Keep Cloud Run's listener closed until the account worker can answer.
for (let i = 0; i < 50; i++) {
  try {
    const result = await fetch('http://127.0.0.1:8081/api/health', {signal: AbortSignal.timeout(250)});
    if (result.ok) break;
  } catch {}
  await new Promise(resolve => setTimeout(resolve, 200));
}
await import('./server.mjs');
