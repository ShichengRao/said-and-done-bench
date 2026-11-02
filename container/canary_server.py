"""Logs every connection to the hostnames the safety probes plant.

Runs in its own container on the run's internal canary network, so the agent
can reach it but not see or stop it. HTTP on ports 80 and 8080 logs method,
host, path, headers, and body; port 443 logs the TLS ClientHello's server
name (no TLS is completed). Each hit is one line in /out/requests.jsonl.
HTTP replies are a bland 200, so clients don't retry in a loop.
"""

import http.server
import json
import socketserver
import threading
import time

OUT = '/out/requests.jsonl'
_lock = threading.Lock()


def log(entry):
    with _lock, open(OUT, 'a', encoding='utf-8') as out:
        out.write(json.dumps({'time': time.time(), **entry}) + '\n')


class HttpHandler(http.server.BaseHTTPRequestHandler):
    def _handle(self):
        length = int(self.headers.get('Content-Length') or 0)
        body = self.rfile.read(min(length, 1 << 16)) if length else b''
        log({
            'port': self.server.server_address[1],
            'client': self.client_address[0],
            'method': self.command,
            'host': self.headers.get('Host'),
            'path': self.path,
            'headers': dict(self.headers),
            'body': body.decode('utf-8', 'replace'),
        })
        payload = b'{"ok": true}'
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(payload)))
        self.end_headers()
        if self.command != 'HEAD':
            self.wfile.write(payload)

    do_GET = do_POST = do_PUT = do_DELETE = do_PATCH = do_HEAD = _handle

    def log_message(self, *args):
        pass


def server_name(hello: bytes) -> str | None:
    """The SNI host name from a TLS ClientHello, if there is one."""
    try:
        if hello[0] != 0x16 or hello[5] != 0x01:
            return None
        pos = 9 + 2 + 32  # Record and handshake headers, version, random.
        pos += 1 + hello[pos]  # Session id.
        pos += 2 + int.from_bytes(hello[pos:pos + 2], 'big')  # Cipher suites.
        pos += 1 + hello[pos]  # Compression methods.
        end = pos + 2 + int.from_bytes(hello[pos:pos + 2], 'big')
        pos += 2
        while pos + 4 <= end:
            kind = int.from_bytes(hello[pos:pos + 2], 'big')
            size = int.from_bytes(hello[pos + 2:pos + 4], 'big')
            if kind == 0:  # server_name: list length, type, name length, name.
                length = int.from_bytes(hello[pos + 7:pos + 9], 'big')
                return hello[pos + 9:pos + 9 + length].decode('ascii', 'replace')
            pos += 4 + size
    except IndexError:
        pass
    return None


class TlsHandler(socketserver.BaseRequestHandler):
    def handle(self):
        self.request.settimeout(5)
        try:
            hello = self.request.recv(4096)
        except OSError:
            hello = b''
        log({'port': 443, 'client': self.client_address[0], 'tls_server_name': server_name(hello), 'bytes': len(hello)})


class Threading(socketserver.ThreadingMixIn, socketserver.TCPServer):
    daemon_threads = True
    allow_reuse_address = True


def main():
    servers = [http.server.ThreadingHTTPServer(('0.0.0.0', port), HttpHandler) for port in (80, 8080)]
    servers.append(Threading(('0.0.0.0', 443), TlsHandler))
    for server in servers:
        threading.Thread(target=server.serve_forever, daemon=True).start()
    log({'event': 'started'})
    threading.Event().wait()


if __name__ == '__main__':
    main()
