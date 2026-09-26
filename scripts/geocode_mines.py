#!/usr/bin/env python3
"""Geocode (mine, country) pairs from the miners database via Nominatim.

Strategy (validated by test): queries "{mine}, {country}" then "{mine} gold mine";
validation via address country_code (fallback: display_name substring).
Confidence: high = in-country + full name-token match + mine word in result;
medium = in-country + full name-token match; low = in-country + partial match.

Usage:
  python3 geocode_mines.py --test        # 20 diverse mines, print results
  python3 geocode_mines.py              # full run (resumes from cache)
  python3 geocode_mines.py --limit 50

Cache: ~/workspace/miners-research/geocode_cache.json keyed by
"mine_norm||country_norm". Written every 25 queries and on clean exit.
"""
import json, os, re, sys, time, unicodedata
import urllib.parse, urllib.request

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
XLSX = os.path.join(REPO, 'miners-mine-data.xlsx')
CACHE_PATH = os.path.join(REPO, 'data', 'geocode_cache.json')
LOG_PATH = os.path.join(REPO, 'data', 'geocode.log')

UA = {'User-Agent': 'miners-db-research/1.0 (research use)'}
SLEEP_S = 1.2

JV_BLOCK = {'nevada gold mines'}

MINE_WORDS = {'mine', 'mines', 'mina', 'minas', 'minera', 'minero', 'gruva',
              'gruvan', 'bergwerk', 'mijn', 'kaivos', 'kopalnia', 'důl',
              'рудник', 'منجم', 'madencilik', 'maden'}

ISO = {
    'Canada': 'ca', 'Australia': 'au', 'United States': 'us', 'Mexico': 'mx',
    'China': 'cn', 'Peru': 'pe', 'Brazil': 'br', 'Chile': 'cl',
    'South Africa': 'za', 'Turkey': 'tr', 'Argentina': 'ar', 'Sweden': 'se',
    "Côte d'Ivoire": 'ci', 'Ghana': 'gh', 'Indonesia': 'id', 'Nicaragua': 'ni',
    'Burkina Faso': 'bf', 'Colombia': 'co', 'Mali': 'ml', 'Norway': 'no',
    'Russia': 'ru', 'Bolivia': 'bo', 'Finland': 'fi', 'Philippines': 'ph',
    'Ecuador': 'ec', 'Haiti': 'ht', 'Papua New Guinea': 'pg', 'Serbia': 'rs',
    'Guyana': 'gy', 'Poland': 'pl', 'Tanzania': 'tz', 'Greece': 'gr',
    'Malaysia': 'my', 'New Zealand': 'nz', 'Zimbabwe': 'zw', 'Guinea': 'gn',
    'Mongolia': 'mn', 'Portugal': 'pt', 'Senegal': 'sn', 'Armenia': 'am',
    'Bosnia and Herzegovina': 'ba', 'Bulgaria': 'bg', 'Cambodia': 'kh',
    'Democratic Republic of the Congo': 'cd', 'Honduras': 'hn', 'Kenya': 'ke',
    'Kyrgyzstan': 'kg', 'Laos': 'la', 'Morocco': 'ma', 'Namibia': 'na',
    'Suriname': 'sr', 'Tajikistan': 'tj', 'Zambia': 'zm', 'Botswana': 'bw',
    'Dominican Republic': 'do', 'Egypt': 'eg', 'Ethiopia': 'et', 'Fiji': 'fj',
    'Guatemala': 'gt', 'Ireland': 'ie', 'Kazakhstan': 'kz', 'Liberia': 'lr',
    'Mauritania': 'mr', 'North Macedonia': 'mk', 'Pakistan': 'pk',
    'Panama': 'pa', 'Saudi Arabia': 'sa', 'Sierra Leone': 'sl',
    'Solomon Islands': 'sb', 'Sudan': 'sd', 'Thailand': 'th',
    'United Kingdom': 'gb', 'Venezuela': 've', 'Nevada': 'us', 'Arizona': 'us',
    'California': 'us', 'Lupa Goldfields': 'tz',
}

def strip_accents(s):
    return ''.join(c for c in unicodedata.normalize('NFKD', s)
                   if not unicodedata.combining(c))

def norm_ws(s):
    return re.sub(r'\s+', ' ', (s or '').strip())

def canonical_country(country):
    c = norm_ws(country)
    if not c:
        return None, None
    low = c.lower()
    if low in ('various', 'europe, middle east and africa', 'south and central america'):
        return None, None
    parts = re.split(r'\s*/\s*', c)
    if len(parts) > 1:
        cands = [canonical_country(p)[0] for p in parts]
        cands = [x for x in cands if x]
        return (cands[0] if cands else None), cands
    if ',' in c:
        tail = c.rsplit(',', 1)[1].strip()
        tl = tail.lower()
        if tl in ('canada', 'mexico', 'australia', 'brazil', 'argentina', 'peru',
                  'chile', 'u.s.a.', 'u.s.a', 'usa', 'united states'):
            return canonical_country(tail)[0], None
        return canonical_country(c.split(',', 1)[0].strip())[0], None
    c = re.sub(r'\s*\(.*?\)\s*', '', c).strip()
    low = c.lower()
    mapping = {
        'usa': 'United States', 'u.s.a.': 'United States', 'u.s.a': 'United States',
        'united states': 'United States',
        'turkey': 'Turkey', 'türkiye': 'Turkey',
        'cote d’ivoire': "Côte d'Ivoire", "cote d'ivoire": "Côte d'Ivoire",
        "côte d’ivoire": "Côte d'Ivoire", "côte d'ivoire": "Côte d'Ivoire",
        'democratic republic of the congo': 'Democratic Republic of the Congo',
        'drc': 'Democratic Republic of the Congo',
        'nevada': 'Nevada', 'arizona': 'Arizona', 'california': 'California',
        'lupa goldfields': 'Lupa Goldfields',
        'united kingdom (northern ireland)': 'United Kingdom',
    }
    return mapping.get(low, c), None

def name_tokens(s):
    s = strip_accents(s.lower())
    toks = re.findall(r'[a-z0-9]+', s)
    stop = {'mine', 'mines', 'gold', 'silver', 'project', 'deposit', 'complex',
            'operation', 'operations', 'the', 'de', 'la', 'el', 'del', 'y', 'e',
            'le', 'les', 'des', 'du', 'da', 'do', 'das', 'dos', 'na', 'no'}
    return [t for t in toks if t not in stop and len(t) > 1]

def nominatim(q, limit=5):
    params = urllib.parse.urlencode({'q': q, 'format': 'json', 'limit': limit,
                                     'addressdetails': 1})
    url = 'https://nominatim.openstreetmap.org/search?' + params
    last = None
    for _ in range(3):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=30) as resp:
                if resp.status in (429, 403):
                    time.sleep(60)
                    continue
                return json.loads(resp.read().decode('utf-8'))
        except Exception as e:
            last = e
            time.sleep(5)
    raise RuntimeError(f'nominatim failed for {q!r}: {last}')

def score_result(r, mine, isos, goldmine_query):
    """Return (result, confidence) or None. Tiers: high > medium > low."""
    dn = strip_accents(r.get('display_name', '')).lower()
    addr = r.get('address', {}) or {}
    addr_text = strip_accents(' '.join(str(v) for v in addr.values())).lower()
    text = dn + ' ' + addr_text
    cc = (addr.get('country_code') or '').lower()
    if isos and cc not in isos:
        return None
    words = set(text.split())
    has_mw = bool(words & MINE_WORDS) or any(w in dn for w in MINE_WORDS)
    mtoks = name_tokens(mine)
    if mtoks:
        hits = sum(1 for t in mtoks if t in text)
        full = hits == len(mtoks)
        partial = hits >= max(1, (len(mtoks) + 1) // 2)
    else:
        full, partial = False, False
    if full and has_mw:
        return r, 'high'
    if full:
        return r, 'medium'
    if partial and has_mw:
        return r, 'medium'
    if partial:
        return r, 'low'
    # non-latin mine names (Arabic/Chinese): query was "{mine} gold mine" and
    # the result is a mine in the right country -> accept as low
    if goldmine_query and has_mw:
        return r, 'low'
    return None

def geocode_pair(mine, country, canon, alternates):
    isos = set()
    for c in ([canon] + list(alternates or [])):
        if c and c in ISO:
            isos.add(ISO[c])
    queries = []  # (query, is_goldmine_variant)
    if canon:
        queries.append((f"{mine} mine {canon}", False))
        queries.append((f"{mine}, {canon}", False))
    queries.append((f"{mine} gold mine", True))
    tiered = {'high': [], 'medium': [], 'low': []}
    seen = set()
    for qi, (q, gmq) in enumerate(queries):
        results = nominatim(q)
        time.sleep(SLEEP_S)
        for r in results:
            key = (r.get('lat'), r.get('lon'))
            if key in seen:
                continue
            seen.add(key)
            sc = score_result(r, mine, isos, gmq)
            if sc:
                tiered[sc[1]].append((qi, sc[0]))
        # early exit: a high-confidence hit ends the search
        if tiered['high']:
            break
        if qi == 1 and tiered['medium']:
            break
    for tier in ('high', 'medium', 'low'):
        if tiered[tier]:
            tiered[tier].sort(key=lambda x: x[0])
            r = tiered[tier][0][1]
            return {'lat': float(r['lat']), 'lon': float(r['lon']),
                    'display_name': r.get('display_name', ''),
                    'confidence': tier, 'source': 'nominatim', 'reason': ''}
    return {'lat': None, 'lon': None, 'display_name': '',
            'confidence': 'none', 'source': 'none',
            'reason': 'no in-country match' if canon else 'no match (no country)'}

def load_pairs():
    import openpyxl
    wb = openpyxl.load_workbook(XLSX, read_only=True, data_only=True)
    ws = wb['Mines']
    rows = list(ws.iter_rows(values_only=True))
    pairs = {}
    for r in rows[1:]:
        m, c = norm_ws(str(r[1] or '')), norm_ws(str(r[2] or ''))
        if not m:
            continue
        key = m.lower() + '||' + c.lower()
        if key not in pairs:
            pairs[key] = {'mine': m, 'country': c}
    return pairs

def log(msg):
    line = f"{time.strftime('%H:%M:%S')} {msg}"
    print(line, flush=True)
    with open(LOG_PATH, 'a') as f:
        f.write(line + '\n')

TEST_MINES = ['Detour Lake', 'Peñasquito', 'Cadia', 'Lihir', 'Kibali', 'Tasiast',
              'Boddington', 'Greens Creek', 'Fruta del Norte', 'Malartic',
              'Cortez', 'Oyu Tolgoi', 'Pueblo Viejo', 'Ahafo', 'Yanacocha',
              'Cerro Verde', 'Sukari', 'Muruntau', 'Grasberg', 'Penasquito']

def main():
    args = sys.argv[1:]
    test_mode = '--test' in args
    limit = None
    for a in args:
        if a.startswith('--limit'):
            limit = int(a.split('=')[1])

    cache = {}
    if os.path.exists(CACHE_PATH):
        cache = json.load(open(CACHE_PATH))

    pairs = load_pairs()
    keys = sorted(pairs)

    if test_mode:
        test_keys = []
        for w in TEST_MINES:
            for k in keys:
                if pairs[k]['mine'].lower().startswith(w.lower()):
                    test_keys.append(k)
                    break
        log(f"TEST: {len(test_keys)} mines")
        for k in test_keys:
            p = pairs[k]
            canon, alts = canonical_country(p['country'])
            try:
                res = geocode_pair(p['mine'], p['country'], canon, alts)
                log(f"  {p['mine']} ({p['country']}) -> {res['lat']},{res['lon']} "
                    f"[{res['confidence']}] {res['display_name'][:75]} {res['reason']}")
            except Exception as e:
                log(f"  {p['mine']} ERROR: {e}")
        return

    done = 0
    new_queries = 0
    try:
        for k in keys:
            p = pairs[k]
            if k in cache:
                done += 1
                continue
            if limit is not None and new_queries >= limit:
                break
            if p['mine'].lower() in JV_BLOCK:
                cache[k] = {'lat': None, 'lon': None, 'display_name': '',
                            'confidence': 'none', 'source': 'none',
                            'reason': 'multi-asset JV'}
                done += 1
                continue
            canon, alts = canonical_country(p['country'])
            try:
                cache[k] = geocode_pair(p['mine'], p['country'], canon, alts)
            except RuntimeError as e:
                log(f"QUERY FAILED (continuing): {p['mine']} ({p['country']}): {e}")
                cache[k] = {'lat': None, 'lon': None, 'display_name': '',
                            'confidence': 'none', 'source': 'none',
                            'reason': f'query error, retryable: {e}'}
                time.sleep(30)
            new_queries += 1
            done += 1
            if new_queries % 25 == 0:
                json.dump(cache, open(CACHE_PATH, 'w'))
                log(f"progress: {done}/{len(keys)} pairs, {new_queries} new "
                    f"queries (cache saved)")
    finally:
        json.dump(cache, open(CACHE_PATH, 'w'))
        log(f"DONE: {done}/{len(keys)} pairs cached")
    conf = {}
    for v in cache.values():
        conf[v.get('confidence')] = conf.get(v.get('confidence'), 0) + 1
    log(f"confidence breakdown: {conf}")

if __name__ == '__main__':
    main()
