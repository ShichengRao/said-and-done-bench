def mul(a,b):
    out=0
    for _ in range(8):
        if b&1: out^=a
        a=(a<<1)^ (0x11b if a&128 else 0)
        b>>=1
    return out

def inv(a):
    if a==0: raise ValueError('zero has no inverse')
    result=1;power=254
    while power:
        if power&1: result=mul(result,a)
        a=mul(a,a);power>>=1
    return result
