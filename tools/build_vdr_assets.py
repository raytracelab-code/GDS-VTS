"""One-time conversion of existing OFL webfonts and reference list/flag assets.

Run with the user-confirmed reference path. No reference file is used at runtime.
Requires fonttools[woff] only when regenerating native fonts.
"""
import ast
import base64
import json
from pathlib import Path
import re
import sys


def build(reference):
    from fontTools.ttLib import TTFont
    from fontTools.varLib.instancer import instantiateVariableFont
    root = Path(__file__).resolve().parents[1]
    dest = root / 'app/resources/vdr'
    dest.mkdir(exist_ok=True)
    source = Path(reference).read_text(encoding='utf-8')
    lists = {}
    for name, start, end in [('movement', 'St=[', '],At='), ('countries', 'At=[', '],kt='),
                             ('locations', 'kt=[', '],Lt='), ('ranks', 'Lt=[', '],Nt=')]:
        raw = source.split(start, 1)[1].split(end, 1)[0]
        lists[name] = ast.literal_eval('[' + raw + ']')
    raw_codes = '{' + source.split('],Nt={', 1)[1].split('},Pt=', 1)[0] + '}'
    raw_codes = re.sub(r'([,{])([A-Za-z]+):', r'\1"\2":', raw_codes)
    lists['countryCodes'] = ast.literal_eval(raw_codes)
    (dest/'catalogs.json').write_text(json.dumps(lists, ensure_ascii=False, indent=2), encoding='utf-8')
    sprite = re.search(r'background-image:url\(data:image/png;base64,([^)]*)\)', source)
    if sprite:
        (dest/'flags.png').write_bytes(base64.b64decode(sprite[1]))
    offsets = dict(re.findall(r'\.flag16\.([a-z]{2})\{background-position:0 (-?\d+)px;', source))
    (dest/'flag_offsets.json').write_text(json.dumps(offsets), encoding='utf-8')
    fonts = root / 'app/resources/theme/deep-current/fonts'
    for family, stem in [('Manrope', 'manrope'), ('Inter', 'inter'), ('JetBrains Mono', 'jetbrains-mono')]:
        # Merge static Unicode subsets, so native Qt and PDF use the same full face.
        from fontTools.merge import Merger
        parts = []
        for subset in ('latin', 'latin-ext', 'vietnamese'):
            font = TTFont(fonts/f'{stem}-{subset}.woff2')
            axes = {axis.axisTag: (400 if axis.axisTag == 'wght' else axis.defaultValue) for axis in font['fvar'].axes}
            font = instantiateVariableFont(font, axes, inplace=True)
            font.flavor = None
            part = dest/f'.{stem}-{subset}.ttf'
            font.save(part)
            parts.append(part)
        merged = Merger().merge([str(p) for p in parts])
        for record in merged['name'].names:
            if record.nameID in (1, 4, 6, 16):
                value = family.replace(' ', '') if record.nameID == 6 else family
                record.string = value.encode(record.getEncoding(), errors='replace')
        merged.save(dest/f'{stem}.ttf')
        for part in parts:
            part.unlink()


if __name__ == '__main__':
    build(sys.argv[1])
