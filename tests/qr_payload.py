"""Offline VietQR encoding checked against a published independent example."""
import binascii
from media_payments import vietqr_payload

# Reference: https://github.com/subiz/vietqr (120000 VND example).
expected='00020101021238570010A00000072701270006970415011300110019324180208QRIBFTTA530370454061200005802VN62170813ung ho lu lut6304C15C'
assert vietqr_payload('970415','0011001932418',120000,'ung ho lu lut')==expected


def parse(value):
    fields={};i=0
    while i<len(value):
        tag=value[i:i+2];size=int(value[i+2:i+4]);fields[tag]=value[i+4:i+4+size];i+=4+size
    assert i==len(value)
    return fields


payload=vietqr_payload('970436','9398142181',75000,'TX1 ABCD1234')
fields=parse(payload);merchant=parse(fields['38']);account=parse(merchant['01'])
assert fields['00']=='01' and fields['01']=='12' and fields['53']=='704' and fields['58']=='VN'
assert merchant['00']=='A000000727' and merchant['02']=='QRIBFTTA'
assert account['00']=='970436' and account['01']=='9398142181'
assert fields['54']=='75000' and parse(fields['62'])['08']=='TX1 ABCD1234'
assert int(fields['63'],16)==binascii.crc_hqx(payload[:-4].encode(),0xffff)
for args in [('97043','9398142181',75000,'TX1'),('970436','12345',75000,'TX1'),('970436','9398142181',0,'TX1'),('970436','9398142181',75000,'X'*26)]:
    try:vietqr_payload(*args)
    except ValueError:pass
    else:raise AssertionError('invalid QR fields accepted')
print('PASS: offline VietQR published vector, bank/account/amount/reference fields, CRC and invalid input')
