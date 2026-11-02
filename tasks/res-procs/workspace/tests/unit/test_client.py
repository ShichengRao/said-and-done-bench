from tallyd import client as client_module


class FakeConnection:
    def __init__(self):
        self.requests = []

    def request(self, method, path, body=None, headers=None):
        self.requests.append((method, path, body))

    def getresponse(self):
        return FakeResponse()


class FakeResponse:
    status = 200

    def read(self):
        return b'{"name": "x", "value": 1}'


def test_names_are_percent_encoded_in_paths():
    client = client_module.Client()
    client._connection = FakeConnection()
    client.incr('a b/ü')
    assert client._connection.requests[0][:2] == ('POST', '/v1/counters/a%20b%2F%C3%BC/incr')
