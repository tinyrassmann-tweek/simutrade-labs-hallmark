#!/bin/bash
cd "$(dirname "$0")"
if ! command -v python3 >/dev/null; then
 echo 'Python 3.12 or later is required. Install from python.org, then open this launcher again.'
 read -r -p 'Press Enter to close.'
 exit 1
fi
open 'http://localhost:3000'
python3 server.py
