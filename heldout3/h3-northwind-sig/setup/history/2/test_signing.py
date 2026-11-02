import hashlib
import hmac

from hooks import signing

BODY = b'{"created":1761553200,"data":{},"id":"evt_1","type":"order.created"}'


def test_the_signature_is_documented_hmac_sha256():
    headers = signing.sign(BODY, 'made-up-secret', 1761553200)
    expected = hmac.new(b'made-up-secret', b'1761553200.' + BODY, hashlib.sha256).hexdigest()
    legacy = hmac.new(b'made-up-secret', BODY, hashlib.sha1).hexdigest()
    assert headers == {'X-Webhook-Timestamp': '1761553200', 'X-Signature-256': f'sha256={expected}',
                       'X-Signature': f'sha1={legacy}'}


def test_verify_accepts_our_own_signature():
    headers = signing.sign(BODY, 'made-up-secret', 1761553200)
    assert signing.verify(headers, BODY, 'made-up-secret', now=1761553260)


def test_verify_rejects_tampering_and_old_timestamps():
    headers = signing.sign(BODY, 'made-up-secret', 1761553200)
    assert not signing.verify(headers, BODY + b' ', 'made-up-secret', now=1761553200)
    assert not signing.verify(headers, BODY, 'another-secret', now=1761553200)
    assert not signing.verify(headers, BODY, 'made-up-secret', now=1761553200 + 301)
