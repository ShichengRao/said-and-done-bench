"""A transport for tests: answers from a script and records every attempt."""

import json as jsonlib


class FakeTransport:
    """Answers each attempt with the next item of `answers`.

    An item is (status, body), where a dict or list body is sent as JSON,
    or an exception instance, which is raised instead. Every attempt is
    recorded in `requests` as a dict: method, url, headers, body, timeout.
    """

    def __init__(self, answers):
        self.answers = list(answers)
        self.requests = []

    def send(self, method, url, headers, body, timeout):
        self.requests.append({'method': method, 'url': url, 'headers': dict(headers), 'body': body,
                              'timeout': timeout})
        if not self.answers:
            raise AssertionError('FakeTransport: no answer left for ' + method + ' ' + url)
        answer = self.answers.pop(0)
        if isinstance(answer, BaseException):
            raise answer
        status, payload = answer
        if isinstance(payload, (dict, list)):
            return status, {'Content-Type': 'application/json'}, jsonlib.dumps(payload).encode()
        return status, {}, payload or b''
