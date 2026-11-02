"""A scripted OpenAI-compatible /chat/completions server for neutral-harness tests.

Each request takes the next scripted reply (status, body, optional delay) and
records the request body, so tests can check what the harness sent.
"""

import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

USAGE = {
  'prompt_tokens': 100,
  'completion_tokens': 20,
  'total_tokens': 120,
  'prompt_tokens_details': {'cached_tokens': 80},
  'completion_tokens_details': {'reasoning_tokens': 7},
  'cost': 0.001,
}


def tool_call(command, call_id='call_1', reasoning=None):
  message = {
    'role': 'assistant',
    'content': None,
    'tool_calls': [{
      'id': call_id, 'type': 'function',
      'function': {'name': 'bash', 'arguments': json.dumps({'command': command})},
    }],
  }
  if reasoning:
    message['reasoning_content'] = reasoning
  return {'body': {'provider': 'FakeProvider', 'choices': [{'message': message, 'finish_reason': 'tool_calls'}], 'usage': USAGE}}


def say(text):
  return {'body': {'choices': [{'message': {'role': 'assistant', 'content': text}, 'finish_reason': 'stop'}], 'usage': USAGE}}


def error(status, text='slow down', headers=None):
  return {'status': status, 'body': {'error': {'message': text}}, 'headers': headers or {}}


class FakeOpenAI:
  def __init__(self, script, default=None):
    self.script = list(script)
    self.default = default or say('Nothing more to do.')
    self.requests = []
    self._lock = threading.Lock()
    fake = self

    class Handler(BaseHTTPRequestHandler):
      def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
        with fake._lock:
          fake.requests.append({'path': self.path, 'auth': self.headers.get('Authorization'), 'body': body})
          reply = fake.script.pop(0) if fake.script else fake.default
        time.sleep(reply.get('delay', 0))
        payload = json.dumps(reply['body']).encode()
        try:
          self.send_response(reply.get('status', 200))
          self.send_header('Content-Type', 'application/json')
          self.send_header('Content-Length', str(len(payload)))
          for key, value in reply.get('headers', {}).items():
            self.send_header(key, value)
          self.end_headers()
          self.wfile.write(payload)
        except (BrokenPipeError, ConnectionResetError):
          pass  # The harness gave up on this request.

      def log_message(self, *args):
        pass

    self._server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    self.base_url = f'http://127.0.0.1:{self._server.server_address[1]}/v1'
    threading.Thread(target=self._server.serve_forever, daemon=True).start()

  def close(self):
    self._server.shutdown()
