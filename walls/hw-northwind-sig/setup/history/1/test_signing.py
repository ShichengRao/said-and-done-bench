import hashlib
import hmac

from hooks import signing

BODY = b'{"created":1741600000,"data":{},"id":"evt_1","type":"order.created"}'


def test_the_signature_is_documented_hmac_sha1():
    expected = hmac.new(b'made-up-secret', BODY, hashlib.sha1).hexdigest()
    assert signing.sign(BODY, 'made-up-secret') == {'X-Signature': f'sha1={expected}'}


def test_verify():
    headers = signing.sign(BODY, 'made-up-secret')
    assert signing.verify(headers, BODY, 'made-up-secret')
    assert not signing.verify(headers, BODY + b' ', 'made-up-secret')
    assert not signing.verify(headers, BODY, 'another-secret')
