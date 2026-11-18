# VDR native assets

The three TTFs are local static 400-weight conversions and Unicode-subset merges
of the existing project Manrope, Inter and JetBrains Mono WOFF2 files in
`../theme/deep-current/fonts`. They include Latin, extended Latin and Vietnamese.
Native Qt synthesizes heading bold weights. OFL notices are included alongside
the derived fonts. There are no remote font requests.

`catalogs.json`, `flags.png` and `flag_offsets.json` retain the user-supplied
reference's movement, country, location and rank vocabularies and embedded flag
sprite. These are selection catalogs, never prefilled production report values.

Regeneration: install development-only `fonttools` and `brotli`, then run
`python tools/build_vdr_assets.py <confirmed-reference-path>` from the project.
Normal application operation does not import fonttools or read the reference.
