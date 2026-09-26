#!/usr/bin/env python3
"""Write data/mine_coordinates.csv from geocode_cache.json.

Columns: mine_name,country,latitude,longitude,confidence,source
(blank lat/lon where confidence=none; join key matches build_spreadsheet.py's
_normkey on the ORIGINAL mine/country strings).
"""
import csv, json, os

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE = os.path.join(REPO, 'data', 'geocode_cache.json')
PAIRS_MOD = os.path.join(REPO, 'scripts', 'geocode_mines.py')
OUT = os.path.join(REPO, 'data', 'mine_coordinates.csv')

import importlib.util
spec = importlib.util.spec_from_file_location('gm', PAIRS_MOD)
gm = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gm)

pairs = gm.load_pairs()
cache = json.load(open(CACHE))

with open(OUT, 'w', newline='') as f:
    w = csv.writer(f)
    w.writerow(['mine_name', 'country', 'latitude', 'longitude', 'confidence', 'source'])
    for k in sorted(pairs):
        p = pairs[k]
        v = cache.get(k, {})
        lat, lon = v.get('lat'), v.get('lon')
        w.writerow([p['mine'], p['country'],
                    '' if lat is None else round(lat, 6),
                    '' if lon is None else round(lon, 6),
                    v.get('confidence', 'none'), v.get('source', 'none')])

# stats
import collections
conf = collections.Counter()
blank_reasons = collections.Counter()
for k in pairs:
    v = cache.get(k, {})
    conf[v.get('confidence', 'missing')] += 1
    if not v.get('lat'):
        blank_reasons[v.get('reason', 'missing')] += 1
print('rows:', len(pairs))
print('confidence:', dict(conf))
print('blank reasons:', dict(blank_reasons))
print('wrote', OUT)
