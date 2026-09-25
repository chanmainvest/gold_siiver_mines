import os
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
#!/usr/bin/env python3
"""Section-based fundamentals extraction from annual report text.
Each metric is taken from its own financial-statement section with that
section's units/currency, so MDA highlights (millions) can't mix with
statement values (thousands)."""
import json, os, re

BASE = 'REPO'
REPORTS = os.path.join(BASE, 'reports')

CUR_MAP = [
    ('united states', 'USD'), ('u.s.', 'USD'), ('us dollar', 'USD'),
    ('canadian', 'CAD'), ('australian', 'AUD'),
    ('hong kong', 'HKD'), ('hk\\$', 'HKD'), ('us\\$', 'USD'), ('mexican', 'MXN'),
    ('south african', 'ZAR'), ('indonesian', 'IDR'), ('rupiah', 'IDR'),
    ('philippine', 'PHP'), ('turkish', 'TRY'), ('lira', 'TRY'),
    ('swedish', 'SEK'), ('krona', 'SEK'), ('polish', 'PLN'), ('zloty', 'PLN'),
    (r'\bpln\b', 'PLN'),
    ('korean', 'KRW'), ('won', 'KRW'), ('sterling', 'GBP'), ('pound sterling', 'GBP'),
    ('euro', 'EUR'), ('swiss', 'CHF'), ('brazilian', 'BRL'),
    ('peruvian', 'PEN'), ('nuevo sol', 'PEN'), ('soles', 'PEN'),
    ('chilean', 'CLP'), ('chinese', 'CNY'), ('renminbi', 'CNY'), ('rmb', 'CNY'),
    ('singapore', 'SGD'), ('japanese', 'JPY'), ('yen', 'JPY'), ('colombian', 'COP'),
]
MONTHS = 'january|february|march|april|may|june|july|august|september|october|november|december'
NUM = r'\(?\s*\$?\s*\d[\d,]*(?:\.\d+)?\s*\)?'

def parse_num(s):
    s = s.strip()
    if s in ('-', '–', '—', 'nil', 'Nil', 'NIL', '', '$', '--', '−'):
        return 0.0
    neg = s.startswith('(') and s.endswith(')')
    s = s.strip('()$').replace(',', '').replace(' ', '').replace('\u2212', '-')
    try:
        v = float(s)
    except ValueError:
        return None
    return -v if neg else v

def first_num(line):
    m = re.search(NUM, line)
    return parse_num(m.group(0)) if m else None

def norm(s):
    return re.sub(r'\s+', ' ', s).strip()

def get_text(folder):
    files = sorted(os.listdir(folder))
    txts = [f for f in files if f.lower().endswith('.txt')]
    pdfs = [f for f in files if f.lower().endswith('.pdf')]
    KW = ['CONSOLIDATED STATEMENT', 'CONSOLIDATED BALANCE', 'STATEMENT OF FINANCIAL POSITION',
          'STATEMENTS OF INCOME', 'STATEMENT OF OPERATIONS', 'STATEMENT OF PROFIT OR LOSS',
          'INCOME STATEMENT', 'STATEMENTS OF CASH FLOWS', 'BALANCE SHEET']
    def score(t):
        tu = t.upper()
        return sum(1 for k in KW if k in tu)
    best = (-1, '', '')
    for f in txts:
        p = os.path.join(folder, f)
        try:
            t = open(p, encoding='utf-8', errors='replace').read()
        except Exception:
            continue
        sc = score(t)
        if sc > best[0]:
            best = (sc, t, f)
        if sc >= 3:
            break
    cands = []
    if best[0] >= 0 and best[1]:
        cands.append((best[0], best[1], best[2]))
    if pdfs:
        from pypdf import PdfReader
        import signal
        def _timeout(signum, frame):
            raise TimeoutError('pdf read timeout')
        for f in pdfs:
            p = os.path.join(folder, f)
            try:
                with open(p, 'rb') as fh:
                    if fh.read(5) != b'%PDF-':
                        continue  # not a real PDF (e.g. mislabeled download)
                signal.signal(signal.SIGALRM, _timeout)
                signal.alarm(60)
                try:
                    r = PdfReader(p)
                    t = '\n'.join((pg.extract_text() or '') for pg in r.pages)
                finally:
                    signal.alarm(0)
            except Exception:
                try:
                    signal.alarm(0)
                except Exception:
                    pass
                continue
            sc = score(t)
            if t and len(t) > 2000:
                cands.append((sc, t, f))
            if sc >= 3:
                break
    cands.sort(key=lambda x: -x[0])
    if not cands:
        return []
    # compatibility: also usable as single best
    return cands

def detect_units_currency(header):
    units, cur, ev = 1, None, ''
    umap = {'thousands': 1e3, 'millions': 1e6, 'billions': 1e9}
    m = re.search(r"\$'000|\$’000|\$\(000\)|US\$\(000\)", header)
    if m:
        units, ev = 1e3, m.group(0)
    else:
        m = re.search(r"['’]000\b", header)
        if m:
            units, ev = 1e3, m.group(0)
        else:
            m = re.search(r'(\$|USD|US\$)\s*(thousands|millions|billions)\b', header, re.I)
            if m:
                units, ev = umap[m.group(2).lower()], m.group(0).strip()
            else:
                m = re.search(r'(thousands|millions|billions)\s+of\s+([^()\n]{3,70})', header, re.I)
                if m:
                    units, ev = umap[m.group(1).lower()], m.group(0).strip()
                else:
                    m = re.search(r'(in|all amounts in)\s+(thousands|millions|billions)', header, re.I)
                    if m:
                        units, ev = umap[m.group(2).lower()], m.group(0).strip()
    h = header.lower()
    for pat, code in CUR_MAP:
        if re.search(pat, h):
            cur = code
            break
    return units, cur, ev

SEC_PATTERNS = [
    ('income', r'CONSOLIDATED STATEMENTS? OF (INCOME|OPERATIONS|COMPREHENSIVE (INCOME|EARNINGS)|PROFIT OR LOSS|EARNINGS)|CONSOLIDATED (INCOME STATEMENT|STATEMENT OF PROFIT OR LOSS|STATEMENT OF OPERATIONS)'),
    ('balance', r'CONSOLIDATED BALANCE SHEETS?|CONSOLIDATED STATEMENTS? OF FINANCIAL POSITION'),
]

def split_sections(text):
    """Find statement sections via ALL-CAPS standalone heading lines.
    Returns {name: (header_text, body_lines)}. 'income' falls back to a
    statement of comprehensive income (truncated before OCI subsection)."""
    lines = text.split('\n')
    heads = []  # (line_idx, name)
    for i, ln in enumerate(lines):
        s = ln.strip()
        if len(s) < 10 or len(s) > 90 or re.search(r'\d', s):
            continue
        # heading-style lines: ALL CAPS or starting with 'Consolidated'/'Condensed Consolidated'
        if not (s == s.upper() or re.match(r'(?i)^((condensed|interim)\s+)*consolidated\s', s)):
            continue
        if s.endswith('.') or re.search(r'(?i)information|notes? to the|see note', s):
            continue
        su = s.upper()
        # merged-column artifact: two different statements on one line (e.g.
        # "Consolidated balance sheet   Consolidated income statement")
        groups = sum(1 for g in ('BALANCE SHEET', 'FINANCIAL POSITION') if g in su) > 0
        groups += sum(1 for g in ('INCOME STATEMENT', 'STATEMENT OF OPERATIONS', 'PROFIT OR LOSS') if g in su) > 0
        groups += ('CASH FLOW' in su) + ('CHANGES IN EQUITY' in su)
        if groups >= 2:
            continue
        if re.search(r'INCOME STATEMENT', su):
            heads.append((i, 'income'))
        elif re.search(r'STATEMENTS? OF (INCOME|OPERATIONS|EARNINGS)', su):
            heads.append((i, 'income'))
        elif re.search(r'STATEMENTS? OF LOSS', su):
            if 'COMPREHENSIVE' in su:
                heads.append((i, 'income_ci'))
            else:
                heads.append((i, 'income'))
        elif re.search(r'STATEMENT OF PROFIT OR LOSS', su):
            if 'OTHER COMPREHENSIVE' in su:
                heads.append((i, 'income_ci'))
            else:
                heads.append((i, 'income'))
        elif re.search(r'BALANCE SHEETS?|STATEMENTS? OF FINANCIAL POSITION', su):
            heads.append((i, 'balance'))
        elif re.search(r'STATEMENT OF COMPREHENSIVE INCOME', su):
            heads.append((i, 'income_ci'))
        elif re.search(r'STATEMENT OF COMPREHENSIVE EARNINGS', su):
            heads.append((i, 'income'))  # Endeavour Mining titles its P&L this way
        elif re.search(r'STATEMENTS? OF CASH FLOWS?', su):
            heads.append((i, 'cashflow'))
        elif re.search(r'STATEMENTS? OF (CHANGES IN )?EQUITY', su):
            heads.append((i, 'equity'))
    sections = {}
    # when several candidates share a name (e.g. TOC mentions), pick the one
    # whose following lines look most like a financial statement
    _num5 = re.compile(r'[\d,]{5,}')
    _kw = re.compile(r'(?i)(revenue|profit|loss|asset|liabilit|equity|cash|income|expense|receiv|payable|borrow|sales|turnover)')
    def cand_score(li):
        sc = 0
        for ln in lines[li + 1:li + 40]:
            if _num5.search(ln) and _kw.search(ln):
                sc += 1
        return sc
    by_name = {}
    for li, name in heads:
        grp = 'income' if name in ('income', 'income_ci') else name
        by_name.setdefault(grp, []).append((li, name))
    picked = []
    for grp, cands in by_name.items():
        li, name = max(cands, key=lambda x: (cand_score(x[0]), x[0]))
        picked.append((li, grp, name))
    picked.sort()
    for j, (li, grp, name) in enumerate(picked):
        end_li = picked[j + 1][0] if j + 1 < len(picked) else li + 250
        body = lines[li:min(end_li, li + 250)]
        if name == 'income_ci':
            cut = [k for k, b in enumerate(body) if k >= 2 and re.match(r'\s*OTHER COMPREHENSIVE', b, re.I)]
            if cut:
                body = body[:cut[0]]
        header = '\n'.join(lines[li:li + 8])
        sections[grp] = (header, body)
    return sections

def clean_line(s):
    s = re.sub(r'\(\s*notes?\s+[^)]*\)', '', s, flags=re.I)
    s = re.sub(r'\(Note \d+[A-Z]?\)', '', s, flags=re.I)
    s = re.sub(r'\bNote\s+\d+(\.\d+)?\b', '', s)  # "Note 2.3", "Note 4.1"
    s = re.sub(r'\)\(\d{1,2}\)', ')', s)  # footnote "(2)" after parens
    s = re.sub(r'\b\d+\.\d+\([a-z]\)', '', s)  # "2.4(c)" note refs (before the shorter pattern)
    s = re.sub(r'\b\d{1,2}\([a-z]\)', '', s)  # "6(a)" note refs
    s = re.sub(r'\b\d{1,2}[A-Z]\b', '', s)  # "5A", "21D" note refs
    s = re.sub(r'\b[A-Z]\.\d{1,2}\b', '', s)  # "C.1", "D.5" note refs
    s = re.sub(r'(["\')])\d{1,2}(?=\s)', r'\1', s)  # footnote digit after quote/paren: ("EBITDA")1
    s = re.sub(r'(?<=\d) (?=\d{3}\b)', '', s)  # space thousand-separators: "10 495" -> "10495"
    s = re.sub(r'(?<=\s)[–—−-](?=\s*$)', '0', s)  # trailing dash -> nil -> 0
    s = re.sub(r'(?<=\s)[–—−-](?=\s)', '', s)  # mid-line dash -> column placeholder, drop
    # bare note-reference digits before the figures, e.g. "Sales revenue 2 5,558,774"
    # ([1-9]: never strip a zero produced by the dash rule above)
    s = re.sub(r'(?<![\d.,])[1-9]\d?(?=\s+\$?\s*[\d,]{3,})', '', s)
    return s

def join_wrapped(lines):
    """Merge a digit-less label line with a following line that carries figures
    (wrapped statement labels like '...shareholders of Evolution' / 'Mining Limited 1,475,055')."""
    out = []
    i = 0
    while i < len(lines):
        ln = lines[i]
        if (ln.strip() and not ln.rstrip().endswith(':') and not re.search(r'\d', ln)
                and i + 1 < len(lines) and (
                    re.search(r'[\d,]{5,}', lines[i + 1])
                    or len(re.findall(r'\d{2,}', lines[i + 1])) >= 3)):
            out.append(ln + ' ' + lines[i + 1])
            i += 2
        else:
            out.append(ln)
            i += 1
    return out

def pick(lines, pattern, exclude=None, strip_parens=False, num_idx=0):
    # num_idx: which number on the line to take (0=first). Used for multi-column
    # layouts where the current-year annual figure is not the first column.
    cands = []
    for ln in lines:
        s = norm(clean_line(ln))
        tries = [s]
        if strip_parens:
            s2 = re.sub(r'^(?:[(][^)]*[)]\s*)+', '', s)
            if s2 != s:
                tries.append(s2)
        hit = None
        for t in tries:
            if re.search(pattern, t, re.I):
                hit = t
        if hit is None:
            continue
        s = hit
        if exclude and re.search(exclude, s, re.I):
            continue
        if first_num(s) is None and not re.search(r'\d', s):
            continue
        cands.append(s)
    for c in cands:
        v = first_num(c)
        if v is not None and num_idx:
            nums = [parse_num(x.group(0)) for x in re.finditer(NUM, c)]
            nums = [x for x in nums if x is not None]
            if len(nums) > num_idx:
                v = nums[num_idx]
        if v is not None:
            if not num_idx:
                # "Total" column layout: X (Y) Z where Z == X+Y (e.g. Fresnillo
                # pre-Silverstream / Silverstream / Total) -> use the total
                nums = list(re.finditer(NUM, c))
                if len(nums) >= 3:
                    vals = [parse_num(x.group(0)) for x in nums[:3]]
                    if vals[0] is not None and vals[1] is not None and vals[2] is not None:
                        s1 = -abs(vals[1]) if nums[1].group(0).strip().startswith('(') else vals[1]
                        if abs(vals[0] + s1 - vals[2]) < 0.01 * max(1, abs(vals[2])):
                            v = vals[2]
            return v, c
    return None, (cands[0] if cands else None)

def ebitda_from_line(line):
    """(value, had_unit_word) for the number nearest AFTER the word EBITDA."""
    s = norm(clean_line(line))
    m = re.search(r'\bebitda\b', s, re.I)
    if not m:
        return None
    tail = s[m.end():]
    tail = re.sub(r'(?i)(year ended |for the year ended |quarter ended )?(january|february|march|april|may|june|july|august|september|october|november|december)\s+\d{1,2},?\s+\d{4}', ' ', tail)
    tail_nums = list(re.finditer(NUM, tail))
    if not tail_nums:
        return None
    nm = tail_nums[0]
    if len(tail_nums) >= 2 and re.search(r'\bfrom\b', tail) and re.search(r'\bto\b', tail):
        # "increased from $X to $Y": take Y (the number right after "to")
        m2 = re.search(r'\bto\b[^\d\(]*', tail)
        if m2:
            nm2 = re.compile(NUM).search(tail, m2.end())
            if nm2:
                nm = nm2
    v = parse_num(nm.group(0))
    if v is None:
        return None
    um = re.search(r'\b(billions?|millions?|thousands?)\b', tail, re.I)
    if um:
        v *= {'billion': 1e9, 'million': 1e6, 'thousand': 1e3}[um.group(1).lower().rstrip('s')]
        return v, True
    return v, False

def find_ebitda(text_lines, fy=None, require_unit=True):
    cands = []
    for ln in text_lines:
        s = norm(clean_line(ln))
        if not re.search(r'\bebitda\b', s, re.I) or not re.search(r'\d', s):
            continue
        if re.search(r'guidance|outlook', s, re.I):
            continue
        if re.search(r'\bebitda\b.{0,30}\b(margin|ratio|multiple)\b|\b(margin|ratio)\b.{0,30}\bebitda\b', s, re.I):
            continue
        r = ebitda_from_line(s)
        if r is None:
            continue
        v, had_unit = r
        if require_unit and not had_unit:
            continue
        if v == 0:
            continue
        score = 1 if fy and fy in s else 0
        cands.append((score, v, had_unit, s))
    if not cands:
        return None, None, None
    cands.sort(key=lambda x: -x[0])
    return cands[0][1], cands[0][2], cands[0][3]

DEBT_PATS = [
    r'long-?term debt',
    r'non-?current portion of (long-?term )?debt',
    r'non-?current (borrowings|loans|debt)\b',
    r'current (portion|maturities) of (long-?term )?debt',
    r'short-?term (debt|borrowings|loans)',
    r'current (borrowings|loans|debt)\b',
    r'interest[- ]bear(ing)? (liabilities|borrowings|bank)',
    r'borrowings\b',
    r'\bdebentures\b',
    r'convertible notes?\b',
    r'notes payable\b',
    r'bank loans?\b',
    r'lease liabilit',
    r'lease obligations?\b',
]
DEBT_EXCLUDE = r'receivable|deferred |repayment|proceeds|principal payments|\bincome\b|total '

def extract_debt(body, units):
    """Prefer an explicit 'total debt' line; else sum debt component lines."""
    for ln in body:
        s = norm(clean_line(ln))
        if re.search(r'^\s*total (debt|borrowings|interest[- ]bearing)', s, re.I):
            v = first_num(s)
            if v is not None:
                return v * units, 'total debt line', s
    parts = []
    seen = set()
    for ln in body:
        s = norm(clean_line(ln))
        if re.search(DEBT_EXCLUDE, s, re.I):
            continue
        if any(re.search(p, s, re.I) for p in DEBT_PATS):
            v = first_num(s)
            if v is None:
                continue
            key = (s[:40].lower(), round(v, 1))
            if key in seen:
                continue
            seen.add(key)
            parts.append((v, s))
    if not parts:
        return None, None, None
    total = sum(v for v, _ in parts) * units
    method = 'sum of debt line items: ' + '; '.join(s[:50].strip() for _, s in parts[:6])
    return total, method, [s for _, s in parts]

def extract_shares(lines):
    # R1/R2: "N common shares issued and outstanding" / "Outstanding - N common shares issued"
    for ln in lines:
        s = norm(ln)
        m = re.search(r'([\d,]{5,})\s+(common )?shares (issued and )?outstanding', s, re.I)
        if not m and re.search(r'outstanding', s, re.I):
            m = re.search(r'([\d,]{5,})\s+common shares issued\b', s, re.I)
        if m:
            vv = parse_num(m.group(1))
            if vv and vv > 10000:
                return vv, s
    # R3: 'ordinary shares on issue' movement table -> last 'Balance as at'
    for idx, ln in enumerate(lines):
        if re.search(r'ordinary shares on issue', ln, re.I):
            last = None
            for j in range(idx + 1, min(idx + 40, len(lines))):
                s2 = norm(lines[j])
                m2 = re.search(r'balance as at.{0,60}?([\d,]{7,})', s2, re.I)
                if m2:
                    vv = parse_num(m2.group(1))
                    if vv:
                        last = (vv, s2)
            if last:
                return last
            break
    # R5: 'N ordinary shares in issue'
    for ln in lines:
        s = norm(ln)
        m = re.search(r'([\d,]{7,})\s+ordinary shares in issue', s, re.I)
        if m:
            vv = parse_num(m.group(1))
            if vv:
                return vv, s
    # R4: sum HK-style 'N (YYYY: M) ... shares' class lines
    total = 0
    evs = []
    for ln in lines:
        s = norm(ln)
        if 'shares' not in s.lower():
            continue
        m = re.search(r'^([\d,]{8,})\s+\(\d{4}:', s)
        if m:
            vv = parse_num(m.group(1))
            if vv:
                total += vv
                evs.append(s)
    if total:
        return total, ' + '.join(e[:60] for e in evs)
    return None, None

CORE_FIELDS = ('revenue', 'ebitda', 'net_income', 'total_debt', 'cash', 'shares_outstanding')

def _extract_one(text, src):
    sections = split_sections(text)
    if 'income' not in sections and 'balance' not in sections:
        return {'error': 'no financial statements found', 'source': src}
    out = {'source': src}
    ev = {}
    # income section
    if 'income' in sections:
        header, body = sections['income']
        body = join_wrapped(body)
        units, cur, cev = detect_units_currency(header)
        out['units_income'] = units
        out['currency'] = cur
        out['currency_evidence'] = cev
        # 4-column layout (Q4'25, Q4'24, FY'25, FY'24): annual figure is the 3rd number
        hl = header.lower()
        ni4 = 2 if ('1 october' in hl and '1 january' in hl) else 0
        v, e = pick(body, r'^\s*(total\s+)?(revenues?|net sales|sales)( from (mining )?operations| of (gold|metals|concentrates))?\b',
                    r'deferred|receivable|hedg|stream|other (income|revenue)|finance|interest|recogniz', strip_parens=True, num_idx=ni4)
        if v is None:
            # fallback: revenue word not at line start (e.g. column headers merged into the line)
            v, e = pick(body, r'(revenues?|net sales|sales)( from (mining )?operations| of (gold|metals|concentrates))?\b',
                        r'deferred|receivable|hedg|stream|other (income|revenue)|finance|interest|recogniz|as revenue|revenue (was|of \$)|cost of sales', strip_parens=True, num_idx=ni4)
        # avoid "revenue" subtotal lines like "total other revenue": require it be the main revenue line
        out['revenue'] = v * units if v is not None else None
        ev['revenue'] = e
        v, e = pick(body, r'^\s*(net (income|earnings|profit)(\s*\(loss\))?|profit\s*(/+\s*\(loss\)|\(loss\))?\s+for the (year|period)|profit after (income )?tax|net (loss|income) attributable|net (loss|profit) for)',
                    r'comprehensive|per share|non-?controlling|before|from (dis)?continu|attributable to owners.{0,20}non', num_idx=ni4)
        out['net_income'] = v * units if v is not None else None
        ev['net_income'] = e
        # operating income fallback (section units)
        v, e = pick(body, r'^\s*(operating (income|profit|earnings)|income from operations|earnings from operations|operating (loss|profit))\b',
                    r'margin|segment')
        out['operating_income'] = v * units if v is not None else None
        ev['operating_income'] = e
        # fiscal year
        fytxt = header + '\n' + '\n'.join(body[:12])
        fy = None
        m = re.search(r'year ended[\s\S]{0,60}?(%s)\s+\d{1,2}\s*,?\s*(20\d{2})' % MONTHS, fytxt, re.I)
        if not m:
            m = re.search(r'year ended\s+\d{1,2}\s+(%s)\s*,?\s*(20\d{2})' % MONTHS, fytxt, re.I)
        if m:
            fy = m.group(2)
        else:
            m2 = re.search(r'for the (?:year|period) ended[^\n]{0,80}?(20\d{2})', fytxt, re.I)
            if m2:
                fy = m2.group(1)
        out['fiscal_year'] = fy
    fy = out.get('fiscal_year')
    # ebitda: income section first (section units if no unit word), then whole text (unit words only)
    ebitda, ebitda_ev, ebitda_kind = None, None, None
    if 'income' in sections:
        units = out.get('units_income', 1)
        v, had_unit, e = find_ebitda(sections['income'][1], fy, require_unit=False)
        if v is not None:
            if not had_unit:
                v = v * units
            ebitda, ebitda_ev, ebitda_kind = v, e, 'EBITDA'
    if ebitda is None:
        v, had_unit, e = find_ebitda(text.split('\n'), fy, require_unit=True)
        if v is not None:
            ebitda, ebitda_ev = v, e
            ebitda_kind = 'Adjusted EBITDA' if re.search(r'adjusted', e, re.I) else 'EBITDA'
    if ebitda is None and out.get('operating_income') is not None:
        ebitda, ebitda_ev, ebitda_kind = out['operating_income'], ev.get('operating_income'), 'operating income (EBITDA undisclosed)'
    out['ebitda'] = ebitda
    out['ebitda_kind'] = ebitda_kind
    ev['ebitda'] = ebitda_ev
    # balance section
    if 'balance' in sections:
        header, body = sections['balance']
        body = join_wrapped(body)
        units, cur, cev = detect_units_currency(header)
        out['units_balance'] = units
        if not out.get('currency'):
            out['currency'] = cur
            out['currency_evidence'] = cev
        v, e = pick(body, r'cash( and cash equivalents)?\b', r'settl|\bflows?\b|dividend')
        out['cash'] = v * units if v is not None else None
        ev['cash'] = e
        total_debt, debt_method, debt_ev = extract_debt(body, units)
        out['total_debt'] = total_debt
        out['debt_method'] = debt_method
        ev['total_debt'] = debt_ev
        # shares outstanding from equity part of balance section
        shares, sev = extract_shares(body)
        out['shares_outstanding'] = shares
        ev['shares'] = sev
    # fallback shares: whole doc
    if not out.get('shares_outstanding'):
        sh, sev = extract_shares(text.split('\n'))
        out['shares_outstanding'] = sh
        ev['shares'] = sev
    # fallback currency: presentation currency mention (whole text)
    if not out.get('currency'):
        m = re.search(r'\bin\s+(PLN|USD|CAD|AUD|HKD|CNY|MXN|ZAR|GBP|EUR|CHF|SEK|NOK|DKK|TRY|IDR|PHP|KRW|JPY)\b', text)
        if m:
            out['currency'] = m.group(1)
            out['currency_evidence'] = 'fallback: ' + m.group(0).strip()
    if not out.get('currency'):
        m = re.search(r'(?:presentation|functional) currency.{0,60}?(dollar|peso|rand|rupiah|lira|krona|zloty|won|yen|franc)', text, re.I)
        if not m:
            m = re.search(r'present\w*\s+in\s+([\w\s]+?)(dollars|pesos|rand|rupiah|lira|krona|zloty|won|yen|francs)', text, re.I)
        if not m:
            m = re.search(r'financial statements.{0,80}?([\w\s]+?)(dollars|pesos|rand|rupiah|lira)', text, re.I)
        if m:
            for pat, code in CUR_MAP:
                if re.search(pat, m.group(0).lower()):
                    out['currency'] = code
                    out['currency_evidence'] = 'fallback: ' + m.group(0)[:80].strip()
                    break
    # KGHM SRR: statements in PLN millions (verified by scale: total assets 58,240
    # = PLN 58.2B; revenue 36,366 = PLN 36.4B). Units not labeled in extracted text.
    if out.get('currency') == 'PLN' and 'kghm' in text[:3000].lower():
        if out.get('units_income') == 1 or out.get('units_balance') == 1:
            for k in ('revenue', 'net_income', 'ebitda', 'total_debt', 'cash'):
                if out.get(k) is not None and out.get(k) < 1e9:
                    out[k] *= 1e6
            out['units_note'] = 'PLN millions (KGHM SRR convention; verified by balance-sheet scale)'
    out['evidence'] = ev
    return out

def extract(folder):
    cands = [(sc, t, s) for sc, t, s in get_text(folder) if t and len(t) >= 2000]
    if not cands:
        return {'error': 'no usable text', 'source': ''}
    best, best_n = None, -1
    for _sc, t, s in cands:
        r = _extract_one(t, s)
        if r.get('error'):
            if best is None:
                best = r
            continue
        n = sum(1 for f in CORE_FIELDS if r.get(f) is not None)
        if n > best_n:
            best, best_n = r, n
        if n >= 5:
            break
    return best

def main():
    rows = json.load(open(os.path.join(REPO, 'data', 'webapp', 'companies.json')))['rows']
    folders = {f.lower(): f for f in os.listdir(REPORTS)}
    def find_folder(stem):
        first = stem.split(',')[0].strip().lower()
        cands = [stem.lower(), first]
        for sfx in ['ax', 'to', 'v', 'l', 'hk', 'ks', 'mx', 'jk', 'wa', 'si', 'is', 'ps', 'st', 'jo', 'lm', 'cl', 'cn']:
            cands.append(first + '.' + sfx)
        for c in cands:
            if c in folders:
                return folders[c]
        for fl, f in folders.items():
            if fl == first or fl.startswith(first + '.') or fl.startswith(first + ','):
                return f
        return None
    out = {}
    for i, r in enumerate(rows):
        stem = r['Tickers']
        f = find_folder(stem)
        key = stem
        if not f:
            out[key] = {'company': r['Company'], 'error': 'report not obtained'}
            continue
        fpath = os.path.join(REPORTS, f)
        files = os.listdir(fpath)
        if not any(x.lower().endswith(('.pdf', '.txt')) for x in files):
            out[key] = {'company': r['Company'], 'error': 'no PDF or text file in report folder'}
            continue
        try:
            out[key] = {'company': r['Company'], 'folder': f, **extract(os.path.join(REPORTS, f))}
        except Exception as e:
            out[key] = {'company': r['Company'], 'error': 'extract failed: %s' % e}
        if (i + 1) % 10 == 0:
            json.dump(out, open(os.path.join(BASE, 'fundamentals_raw.json'), 'w'), indent=1)
            print(f'{i+1}/{len(rows)} done', flush=True)
    json.dump(out, open(os.path.join(BASE, 'fundamentals_raw.json'), 'w'), indent=1)
    n = sum(1 for v in out.values() if v.get('revenue') is not None)
    print('revenue extracted: %d/%d' % (n, len(out)))

if __name__ == '__main__':
    main()
