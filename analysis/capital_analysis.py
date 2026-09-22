#!/usr/bin/env python3
import json, re
from capital_parse import parse_money, parse_stage_label
from collections import defaultdict, Counter

import os
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BUILD = os.path.join(ROOT, 'build'); os.makedirs(BUILD, exist_ok=True)
DS = os.path.join(ROOT, 'insurtech-dataset.json')
d = json.load(open(DS))
companies = d['companies']

# --- parse capital raised from free-text "stage" field ---
STAGE_RE = re.compile(r'\b(Pre-?[Ss]eed|Seed|Series [A-G]\+?|Unfunded|IPO)\b')
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

def _old_parse_stage_label(s):
    if re.search(r'\bIPO\b', s, re.I):
        return 'IPO/public'
    if re.search(r'\bunfunded\b', s, re.I) or s.strip() == '' :
        return 'Unfunded/undisclosed'
    m = STAGE_RE.search(s)
    if not m:
        return 'Unfunded/undisclosed'
    lbl = m.group(1)
    lbl = lbl.replace('Pre-seed', 'Pre-Seed').replace('Preseed','Pre-Seed').replace('presee','Pre-Seed')
    return lbl

rows = []
for c in companies:
    stage_txt = c.get('stage', '') or ''
    monies = parse_money(stage_txt)
    total = max(monies) if monies else 0.0  # take largest figure mentioned as the "total raised" proxy
    stage_label = parse_stage_label(stage_txt)
    rows.append({
        'name': c['name'],
        'workflow_step': c.get('workflow_step', 'other') or 'other',
        'buyer': c.get('buyer', ''),
        'stage_label': ('Round not stated' if total > 0 else 'Nothing disclosed') if stage_label == 'Unfunded/undisclosed' else stage_label,
        'capital': total,
        'investors': c.get('investors', []),
        'source': c.get('source', 'original-snowball'),
    })

# --- 1. capital by value-chain stage (workflow_step) ---
by_stage = defaultdict(lambda: {'capital':0.0, 'count':0, 'funded_count':0})
for r in rows:
    b = by_stage[r['workflow_step']]
    b['capital'] += r['capital']
    b['count'] += 1
    if r['capital'] > 0:
        b['funded_count'] += 1

print("="*100)
print("CAPITAL BY VALUE-CHAIN STAGE (workflow_step)")
print("="*100)
for step, b in sorted(by_stage.items(), key=lambda x: -x[1]['capital']):
    print(f"{step:35s} ${b['capital']/1e6:9,.1f}M  |  {b['count']:3d} companies  |  {b['funded_count']:3d} w/ disclosed $")

# --- 2. funding-stage funnel (maturity) ---
print()
print("="*100)
print("STAGE-OF-MATURITY FUNNEL")
print("="*100)
stage_counts = Counter(r['stage_label'] for r in rows)
stage_capital = defaultdict(float)
for r in rows:
    stage_capital[r['stage_label']] += r['capital']
order = ['Pre-Seed','Seed','Series A','Series B','Series C','Series D','Series D+','Series E','Series F','Series G','IPO/public','Unfunded/undisclosed']
for s in order:
    if s in stage_counts:
        print(f"{s:22s} {stage_counts[s]:3d} companies   ${stage_capital[s]/1e6:9,.1f}M")
extra = set(stage_counts) - set(order)
for s in extra:
    print(f"{s:22s} {stage_counts[s]:3d} companies   ${stage_capital[s]/1e6:9,.1f}M")

# --- 3. investor leaderboard ---
inv_companies = defaultdict(set)
inv_stage_spread = defaultdict(lambda: Counter())
for r in rows:
    for inv in r['investors']:
        inv_companies[inv].add(r['name'])
        inv_stage_spread[inv][r['workflow_step']] += 1

print()
print("="*100)
print("TOP 30 INVESTORS BY PORTFOLIO COMPANY COUNT (in this dataset)")
print("="*100)
top_investors = sorted(inv_companies.items(), key=lambda x: -len(x[1]))[:30]
for inv, comps in top_investors:
    spread = inv_stage_spread[inv]
    top_cluster, top_n = spread.most_common(1)[0]
    concentration = top_n / len(comps)
    tag = "CONCENTRATED" if concentration >= 0.6 and len(comps) >= 3 else ("GENERALIST" if len(spread) >= 4 else "")
    print(f"{inv:35s} {len(comps):3d} cos  | top segment: {top_cluster:20s} ({top_n}/{len(comps)})  {tag}")

# --- 4. "doubled down" -- investors with 3+ portfolio companies, esp. concentrated ---
print()
print("="*100)
print("DOUBLED-DOWN INVESTORS (3+ companies) BY SEGMENT CONCENTRATION")
print("="*100)
doubled = [(inv, comps, inv_stage_spread[inv]) for inv, comps in inv_companies.items() if len(comps) >= 3]
doubled.sort(key=lambda x: -len(x[1]))
for inv, comps, spread in doubled:
    top_cluster, top_n = spread.most_common(1)[0]
    print(f"{inv:35s} {len(comps):3d} cos across {len(spread)} segments | concentrated in: {top_cluster} ({top_n})")
    print(f"    -> {', '.join(sorted(comps))}")

# --- 5. companies with no funding disclosed / unfunded, by segment (who did NOT get chased) ---
print()
print("="*100)
print("SEGMENTS WITH LOWEST FUNDED SHARE (capital didn't chase these as hard)")
print("="*100)
for step, b in sorted(by_stage.items(), key=lambda x: (x[1]['funded_count']/max(x[1]['count'],1))):
    pct = 100*b['funded_count']/max(b['count'],1)
    print(f"{step:35s} {pct:5.1f}% funded  ({b['funded_count']}/{b['count']})")

json.dump({
    'by_stage': {k: v for k,v in by_stage.items()},
    'stage_funnel': {k: {'count': stage_counts[k], 'capital': stage_capital[k]} for k in stage_counts},
    'top_investors': [{'investor': inv, 'company_count': len(comps), 'companies': sorted(comps),
                        'segment_spread': dict(inv_stage_spread[inv])} for inv, comps in top_investors],
    'doubled_down': [{'investor': inv, 'company_count': len(comps), 'companies': sorted(comps),
                       'segment_spread': dict(spread)} for inv, comps, spread in doubled],
}, open(os.path.join(BUILD, 'capital_analysis.json'),'w'), indent=1)
print("\nsaved: capital_analysis.json")
print(f"\nTotal disclosed capital across dataset: ${sum(r['capital'] for r in rows)/1e9:.2f}B")
print(f"Companies with $0 disclosed (unfunded/undisclosed/no $ in text): {sum(1 for r in rows if r['capital']==0)}")
