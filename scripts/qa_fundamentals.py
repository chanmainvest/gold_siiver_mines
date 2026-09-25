import os
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
#!/usr/bin/env python3
"""QA checks on fundamentals_raw.json: outliers, sign issues, unit sanity."""
import json
d = json.load(open('REPO/fundamentals_raw.json'))
print('=== value distributions (native units) ===')
for f in ('revenue', 'ebitda', 'net_income', 'total_debt', 'cash', 'shares_outstanding'):
    vals = [(k, v[f], v.get('currency'), v.get('company')) for k, v in d.items()
            if not v.get('error') and v.get(f) is not None]
    vals.sort(key=lambda x: x[1])
    print(f'\n{f}: n={len(vals)}')
    for k, val, cur, co in vals[:3] + vals[-3:]:
        print(f'   {val:>18,.0f} {str(cur):>4}  {k} ({co[:40]})')
    negs = [x for x in vals if x[1] < 0]
    if f in ('revenue', 'cash', 'shares_outstanding') and negs:
        print(f'   !! negative {f}:', [(x[0], x[1]) for x in negs[:5]])
print('\n=== ebitda_kind counts ===')
from collections import Counter
print(Counter(v.get('ebitda_kind') for v in d.values() if v.get('ebitda') is not None))
print('\n=== fiscal year counts ===')
print(Counter(v.get('fiscal_year') for v in d.values() if not v.get('error')))
print('\n=== currency counts ===')
print(Counter(v.get('currency') for v in d.values() if not v.get('error')))
