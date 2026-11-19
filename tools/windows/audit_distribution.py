"""Release evidence, not a substitute for executing on each target OS."""
import argparse
import hashlib
import json
import os
from pathlib import Path

import pefile

FORBIDDEN={b'GetSystemTimePreciseAsFileTime',b'GetCurrentPackageFullName',b'GetDpiForWindow',
           b'GetThreadDescription',b'SetThreadDescription',b'GetSystemCpuSetInformation',
           b'CreateFile2',b'VirtualAlloc2',b'GetTempPath2W'}


def audit(root):
    root=Path(root).resolve();records=[];risks=[];missing=[]
    bundled={p.name.lower() for p in root.rglob('*') if p.is_file()}
    system=Path(os.environ.get('WINDIR','C:/Windows'))/'System32'
    for path in sorted(root.rglob('*')):
        if not path.is_file() or path.suffix.lower() not in ('.exe','.dll','.pyd'):continue
        pe=pefile.PE(str(path),fast_load=True)
        pe.parse_data_directories(directories=[pefile.DIRECTORY_ENTRY['IMAGE_DIRECTORY_ENTRY_IMPORT']])
        relative=str(path.relative_to(root))
        imports=[entry.name for dll in getattr(pe,'DIRECTORY_ENTRY_IMPORT',[]) for entry in dll.imports if entry.name]
        for dll in getattr(pe,'DIRECTORY_ENTRY_IMPORT',[]):
            name=dll.dll.decode()
            if name.lower() not in bundled and not name.lower().startswith(('api-ms-','ext-ms-')) and not (system/name).is_file():
                missing.append({'importer':relative,'dll':name})
        unsupported=sorted(name.decode() for name in imports if name in FORBIDDEN)
        record={'path':relative,'machine':hex(pe.FILE_HEADER.Machine),
                'subsystem_version':[pe.OPTIONAL_HEADER.MajorSubsystemVersion,pe.OPTIONAL_HEADER.MinorSubsystemVersion],
                'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'modern_api_imports':unsupported}
        records.append(record)
        if unsupported:risks.append(record)
        pe.close()
    return {'warning':'Static inspection cannot prove Windows 7 compatibility; real-OS tests required.',
            'pe_files':records,'modern_api_candidates':risks,'unresolved_import_candidates':missing,
            'file_count':sum(p.is_file() for p in root.rglob('*')),
            'bytes':sum(p.stat().st_size for p in root.rglob('*') if p.is_file()),
            'longest_path':max((len(str(p)),str(p.relative_to(root))) for p in root.rglob('*') if p.is_file())}


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('distribution');parser.add_argument('output')
    args=parser.parse_args();result=audit(args.distribution)
    Path(args.output).write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps({key:value for key,value in result.items() if key!='pe_files'},indent=2))
