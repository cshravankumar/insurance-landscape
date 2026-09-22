#!/usr/bin/env python3
"""Extract a best-effort (date, amount) per company for a capital-deployment timeline."""
import json, re
from capital_parse import parse_money, parse_stage_label
from collections import defaultdict

import os
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BUILD = os.path.join(ROOT, 'build'); os.makedirs(BUILD, exist_ok=True)
DS = os.path.join(ROOT, 'insurtech-dataset.json')
d = json.load(open(DS))
companies = d['companies']

MONTHS = {'jan':1,'feb':2,'mar':3,'apr':4,'may':5,'jun':6,'jul':7,'aug':8,'sep':9,'oct':10,'nov':11,'dec':12}
MONTH_YEAR_RE = re.compile(r'\b(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+(20[12]\d)\b', re.I)
YEAR_RE = re.compile(r'\b(20[12]\d)\b')
YC_RE = re.compile(r'\bYC\s+([WSF])(20[12]\d)\b', re.I)  # W=winter(~Jan), S=summer(~Jun)
MONEY_RE = re.compile(r'\$([\d,.]+)\s*([MBK])\b')

def _old_parse_money(s):
    vals = []
    for num, unit in MONEY_RE.findall(s):
        try:
            n = float(num.replace(',', ''))
        except ValueError:
            continue
        mult = {'K': 1e3, 'M': 1e6, 'B': 1e9}[unit]
        vals.append(n * mult)
    return vals

def latest_date(s):
    """Return (year, month_or_None, precision, quarter_label) for the LATEST date found."""
    candidates = []  # (year, month, precision)
    for mo, yr in MONTH_YEAR_RE.findall(s):
        candidates.append((int(yr), MONTHS[mo[:3].lower()], 'month'))
    for st, yr in YC_RE.findall(s):
        m = 1 if st.upper() == 'W' else (6 if st.upper() == 'S' else 9)
        candidates.append((int(yr), m, 'yc-batch'))
    if not candidates:
        for yr in YEAR_RE.findall(s):
            candidates.append((int(yr), None, 'year'))
    if not candidates:
        return None
    # pick latest by (year, month-or-6-as-midyear-default)
    candidates.sort(key=lambda t: (t[0], t[1] if t[1] else 6))
    y, m, prec = candidates[-1]
    q = ((m-1)//3 + 1) if m else None
    return {'year': y, 'month': m, 'precision': prec, 'quarter': q}

rows = []
undated = 0
for c in companies:
    stage_txt = c.get('stage','') or ''
    dt = latest_date(stage_txt)
    monies = parse_money(stage_txt)
    cap = max(monies) if monies else 0.0
    if dt is None:
        undated += 1
        continue
    period = f"{dt['year']}" if dt['precision'] == 'year' else f"{dt['year']}-Q{dt['quarter']}"
    rows.append({
        'name': c['name'],
        'year': dt['year'],
        'quarter': dt['quarter'],
        'period': period,
        'precision': dt['precision'],
        'capital': cap,
        'workflow_step': c.get('workflow_step','other') or 'other',
        'buyer': c.get('buyer',''),
        'investors': c.get('investors', []),
        'stage_text': stage_txt,
    })

print(f"dated: {len(rows)} / {len(companies)}  ({undated} undated, excluded)")
by_year = defaultdict(lambda: {'capital':0.0,'count':0})
for r in rows:
    by_year[r['year']]['capital'] += r['capital']
    by_year[r['year']]['count'] += 1
for y in sorted(by_year):
    print(y, f"{by_year[y]['count']:3d} cos", f"${by_year[y]['capital']/1e6:,.0f}M")

json.dump(rows, open(os.path.join(BUILD, 'timeline_rows.json'),'w'), indent=1)
print(f"\nsaved {len(rows)} dated rows")
print(f"precision breakdown:", {p: sum(1 for r in rows if r['precision']==p) for p in ['month','yc-batch','year']})
