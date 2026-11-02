from restore import recover
from restore.catalog import checksum

def test_normal_generation_round_trip():
    data={'width':2,'tenant':'test','generation':'normal','fault_budget':1,'fragments':[]}
    for i,(coefficients,value) in enumerate([([1,0],7),([0,1],9),([1,1],14),([2,0],14),([0,2],18)]):
        data['fragments'].append(dict(id=str(i),revision=1,tenant='test',generation='normal',live=True,
                                     coefficients=coefficients,value=value,sha256=checksum(coefficients,value)))
    assert recover(data)==bytes([7,9])
