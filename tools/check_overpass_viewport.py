"""Real Overpass bbox diagnostic. Emits metadata/counts, never credentials or objects."""
import argparse
from collections import Counter
import json
import os
from pathlib import Path
import sys
import time
from urllib.parse import urlsplit,urlunsplit
from urllib.parse import quote
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.nav.maritime.area_controller import MaritimeAreaController
from app.nav.maritime.adapters.overpass import query,OverpassAdapter
from app.nav.maritime.adapters.base import SourceConfig,MAX_RESPONSE_BYTES
from app.nav.maritime.adapters.provider_common import query_url,network_reason
from urllib.request import Request,urlopen


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bounds',nargs=4,type=float,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--method',choices=('GET','POST'),default='POST')
    args=parser.parse_args();area=MaritimeAreaController().viewport(*args.bounds)
    if area is None:parser.error('invalid bounded viewport')
    endpoint=os.environ.get('GDS_OVERPASS_ENDPOINT','https://overpass-api.de/api/interpreter')
    public=urlsplit(query_url(endpoint,{}));result={'bounds':args.bounds,'endpoint':urlunsplit((public.scheme,public.netloc,public.path,'','')),'method':args.method}
    started=time.monotonic()
    try:
        text=query(area,[args.bounds])
        request=Request(query_url(endpoint,{'data':text} if args.method=='GET' else {}),data=None if args.method=='GET' else ('data='+quote(text)).encode(),
            headers={'User-Agent':'GDS-VTS-Maritime/4R','Content-Type':'application/x-www-form-urlencoded'})
        with urlopen(request,timeout=35) as response:
            result['http_status']=response.status;content=response.read(MAX_RESPONSE_BYTES+1)
            result['headers']={k:response.headers.get(k) for k in ('Content-Type','Content-Length','Retry-After','Server') if response.headers.get(k)}
        result['bytes']=len(content)
        if len(content)>MAX_RESPONSE_BYTES:raise ValueError('response limit')
        payload=json.loads(content);result['raw_elements']=len(payload.get('elements',[]))
        remark=str(payload.get('remark','')).lower()
        result['incomplete']=bool(remark)
        result['reason']='OUT_OF_MEMORY' if 'memory' in remark else 'TIMEOUT' if 'timed out' in remark or 'timeout' in remark else 'PROVIDER_ERROR' if remark else None
        objects=OverpassAdapter(SourceConfig('overpass',endpoint)).normalize(payload,area)
        result['normalized']=len(objects);result['categories']=dict(Counter(str(o.category) for o in objects));result['types']=dict(Counter(o.object_type for o in objects))
    except Exception as error:
        result['error']=network_reason(error) if isinstance(error,OSError) else type(error).__name__
        if getattr(error,'code',None):result['http_status']=error.code
        if getattr(error,'headers',None):
            result['headers']={k:error.headers.get(k) for k in ('Content-Type','Content-Length','Retry-After','Server') if error.headers.get(k)}
            try:result['bytes']=len(error.read(MAX_RESPONSE_BYTES+1))
            except OSError:pass
    result['elapsed_seconds']=round(time.monotonic()-started,2)
    args.output.write_text(json.dumps(result,indent=2),encoding='utf8');print(json.dumps(result),flush=True)
    return int('error' in result)


if __name__=='__main__':raise SystemExit(main())
