import {spawn} from 'node:child_process';
import './server.mjs';

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
