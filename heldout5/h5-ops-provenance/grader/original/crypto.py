import hashlib,json
def canonical(value):return json.dumps(value,sort_keys=True,separators=(',',':')).encode()
def verify_signature(body,signature,key):
    try:
        n=int(key['n'],16);e=key['e'];size=(n.bit_length()+7)//8;raw=bytes.fromhex(signature['sig'])
        if len(raw)!=size or int.from_bytes(raw,'big')>=n:return False
        tail=bytes.fromhex('3031300d060960864801650304020105000420')+hashlib.sha256(canonical(body)).digest()
        pad=size-len(tail)-3
        if pad<8:return False
        expected=b'\x00\x01'+b'\xff'*pad+b'\x00'+tail
        return pow(int.from_bytes(raw,'big'),e,n).to_bytes(size,'big')==expected
    except (ValueError,KeyError,TypeError,OverflowError):return False
