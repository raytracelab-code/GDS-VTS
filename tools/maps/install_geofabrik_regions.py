"""Discover official regions, show a disk-safe plan, then explicitly install."""
import argparse
import json
from pathlib import Path
import sys
from concurrent.futures import ThreadPoolExecutor,as_completed
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from app.nav.offline_maps.regions import discover_catalog,select_regions,plan_install,download_region,cache_root


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--profile',choices=('core-maritime-asia','oceania-core','asia-oceania'),default='asia-oceania')
    parser.add_argument('--region',action='append',default=[])
    parser.add_argument('--list',action='store_true')
    parser.add_argument('--dry-run',action='store_true')
    parser.add_argument('--refresh',action='store_true')
    parser.add_argument('--update',action='store_true',help='Stage explicitly requested newer revisions independently')
    parser.add_argument('--catalog',type=Path,default=cache_root().parent/'regions-catalog.json')
    parser.add_argument('--report',type=Path)
    parser.add_argument('--workers',type=int,default=1,choices=range(1,5),help='Concurrent downloads; installations remain serialized')
    args=parser.parse_args()
    if args.refresh or not args.catalog.exists():
        catalog=discover_catalog();args.catalog.parent.mkdir(parents=True,exist_ok=True)
        args.catalog.write_text(json.dumps(catalog,indent=2),encoding='utf-8')
    else:catalog=json.loads(args.catalog.read_text(encoding='utf-8'))
    entries=select_regions(catalog,args.profile,args.region)
    if args.region:
        missing=set(args.region)-{e['region_id'] for e in catalog}-{e['parent'] for e in catalog}
        if missing:parser.error('Unknown official regions: '+', '.join(sorted(missing)))
    plan=plan_install(entries,update=args.update)
    print('REGION | REMOTE BYTES | CACHED | INSTALLED | ACTION',flush=True)
    for row in plan['packages']:print(f"{row['region_id']} | {row['download_size']} | {row['cached']} | {row['installed']} | {row['action']}",flush=True)
    print(json.dumps({k:v for k,v in plan.items() if k!='packages'}),flush=True)
    if args.report:args.report.write_text(json.dumps(plan,indent=2),encoding='utf-8')
    if not args.list and not args.dry_run:
        from tools.maps.import_shortbread import install_asset
        jobs=[r for r in plan['packages'] if r['action'] in ('DOWNLOAD_INSTALL','INSTALL_CACHED')]
        with ThreadPoolExecutor(max_workers=args.workers) as pool:
            futures={pool.submit(download_region,row):row for row in jobs}
            for future in as_completed(futures):
                row=futures[future]
                try:
                    path=future.result()
                    result=install_asset(path,row['region_id'],row['display_name'],regional=True)
                    row.update(result='INSTALLED',installed_path=result['installed_path'])
                    print('INSTALLED '+row['region_id'],flush=True)
                except Exception as error:
                    row.update(result='FAILED',error=str(error));print('FAILED '+row['region_id']+' '+str(error),flush=True)
                if args.report:args.report.write_text(json.dumps(plan,indent=2),encoding='utf-8')
    if args.report:args.report.write_text(json.dumps(plan,indent=2),encoding='utf-8')
    return int(any(row.get('result')=='FAILED' for row in plan['packages']))


if __name__=='__main__':raise SystemExit(main())
