"""Read-only native dump triage; emit module names/offsets, never memory contents."""
import argparse
import json
from pathlib import Path
import struct


def inspect(path):
    raw=Path(path).read_bytes()
    def u32(at):return struct.unpack_from('<I',raw,at)[0]
    def u64(at):return struct.unpack_from('<Q',raw,at)[0]
    assert raw[:4]==b'MDMP'
    count,table=u32(8),u32(12)
    streams={u32(table+i*12):(u32(table+i*12+8),u32(table+i*12+4)) for i in range(count)}
    modules=[];at=streams[4][0]
    for i in range(u32(at)):
        item=at+4+i*108;name_at=u32(item+20)
        name=raw[name_at+4:name_at+4+u32(name_at)].decode('utf-16-le')
        modules.append((u64(item),u32(item+8),Path(name).name))
    def locate(address):
        for base,size,name in modules:
            if base<=address<base+size:return name+'+'+hex(address-base)
        return 'unmapped+'+hex(address)
    at=streams[6][0];thread=u32(at);code=u32(at+8);address=u64(at+24)
    context_at=u32(at+164);rsp=u64(context_at+152)
    stack=[];at=streams[3][0]
    for i in range(u32(at)):
        item=at+4+i*48
        if u32(item)!=thread:continue
        start,size,rva=u64(item+24),u32(item+32),u32(item+36)
        offset=rsp-start
        for n in range(max(0,offset),min(size,offset+4096),8):
            value=u64(rva+n);name=locate(value)
            if not name.startswith('unmapped') and (not stack or stack[-1]!=name):stack.append(name)
    return {'dump':Path(path).name,'exception':hex(code),'instruction':locate(address),
            'stack_address_candidates':stack,'qt_modules':sorted(name for _,_,name in modules if 'qt' in name.lower() or 'pyside' in name.lower() or 'shiboken' in name.lower())}


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('dump');args=parser.parse_args()
    print(json.dumps(inspect(args.dump),indent=2))
