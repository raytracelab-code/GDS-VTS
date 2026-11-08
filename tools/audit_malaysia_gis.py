"""Audit the installed local dataset; ignores macOS metadata and writes no source files."""
import argparse
import json
from pathlib import Path
import sys
import time

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.nav.maritime.adapters.malaysia import MalaysiaOffshoreGISProvider


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory',type=Path)
    parser.add_argument('--output',type=Path,default=Path('docs/diagnostics/malaysia-gis-audit.json'))
    args=parser.parse_args()
    provider=MalaysiaOffshoreGISProvider(args.directory)
    started=time.perf_counter();provider.load()
    elapsed=time.perf_counter()-started
    # Representative viewport timing is informational, never a brittle test threshold.
    started=time.perf_counter()
    for _ in range(100):objects=provider.query_bbox(103,4,105,8)
    query_elapsed=(time.perf_counter()-started)/100
    report=dict(metadata={**provider.metadata,'directory':str(Path(provider.metadata['directory']).relative_to(Path.cwd()))
        if Path(provider.metadata['directory']).is_relative_to(Path.cwd()) else provider.metadata['directory']},
        layers=provider.audit,performance=dict(initial_load_seconds=round(elapsed,3),
            representative_query_seconds=round(query_elapsed,6),representative_in_view=len(objects),
            load_count=provider.load_count))
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({**report['metadata'],'performance':report['performance']},indent=2))


if __name__=='__main__':main()
