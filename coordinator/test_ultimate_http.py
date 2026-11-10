"""Offline-only HTTP acceptance, including request boundaries and review UI."""
import json
import os
import socket
import subprocess
import time
import unittest
import urllib.error
import urllib.request
from pathlib import Path

class UltimateHTTP(unittest.TestCase):
    def test_offline_contract(self):
        with socket.socket() as sock:
            sock.bind(('127.0.0.1', 0))
            port = sock.getsockname()[1]
        env = {**os.environ, 'PORT': str(port), 'DEMO_MODE': 'standby'}
        proc = subprocess.Popen(['node', str(Path(__file__).resolve().parent.parent / 'server.js')], env=env, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        base = f'http://127.0.0.1:{port}'
        def request(path, payload=None):
            req = urllib.request.Request(base + path, data=payload, headers={'Content-Type': 'application/json'})
            try:
                with urllib.request.urlopen(req, timeout=5) as response:
                    return response.status, response.read()
            except urllib.error.HTTPError as error:
                return error.code, error.read()
        try:
            for _ in range(100):
                try:
                    request('/health')
                    break
                except OSError:
                    time.sleep(.03)
            self.assertIn(b'Gold Precision Pro Ultimate', request('/ultimate')[1])
            self.assertEqual(request('/api/v3/ultimate')[0], 405)
            self.assertEqual(request('/api/v3/ultimate', b'bad')[0], 400)
            status, raw = request('/api/v3/ultimate', json.dumps({'asOfUTC':'2026-11-10T12:00:00Z'}).encode())
            self.assertEqual(status, 200)
            data = json.loads(raw)
            self.assertEqual(data['signal'], 'WAIT')
            self.assertFalse(data['executable'])
            self.assertEqual(data['monitoring']['readyFeeds'], 0)
            self.assertEqual(request('/api/v3/ultimate', b' ' * (1048576 + 1))[0], 413)
        finally:
            proc.terminate()
            proc.communicate(timeout=5)
