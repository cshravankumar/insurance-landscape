#!/usr/bin/env python3
"""Build the full structured timeline dataset: year x segment x company, plus investor activity by year."""
import json
from collections import defaultdict

import os
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BUILD = os.path.join(ROOT, 'build'); os.makedirs(BUILD, exist_ok=True)
DS = os.path.join(ROOT, 'insurtech-dataset.json')
total_companies = len(json.load(open(DS))['companies'])
rows = json.load(open(os.path.join(BUILD, 'timeline_rows.json')))

STAGE_LABELS = {
 "intake":"Submission intake","triage":"Triage & prioritization","risk-enrichment":"Risk enrichment",
 "pricing":"Pricing infrastructure","MGA-ops":"MGA / underwriting ops","quote-bind":"Quote–bind connectivity",
 "broker-ops":"Broker & agency ops","policy-servicing":"Policy servicing","claims-fnol":"Claims FNOL",
 "claims-guidance":"Claims guidance","fraud":"Fraud & SIU","bordereaux":"Bordereaux & MGA finance",
 "compliance":"Compliance & licensing","other":"Other",
 "full-stack-insurer":"Full-stack insurer","distribution/embedded":"Distribution & embedded",
}

years = sorted({r['year'] for r in rows})

# year x stage -> {capital, count, companies:[...]}
grid = defaultdict(lambda: defaultdict(lambda: {'capital':0.0,'count':0,'companies':[]}))
for r in rows:
    cell = grid[r['year']][r['workflow_step']]
    cell['capital'] += r['capital']
    cell['count'] += 1
    cell['companies'].append({
        'name': r['name'], 'capital': r['capital'], 'period': r['period'],
        'precision': r['precision'], 'investors': r['investors'],
    })

# investor activity by year: deal count (not $ -- can't attribute $ to one of several co-investors)
inv_year = defaultdict(lambda: defaultdict(int))
inv_year_companies = defaultdict(lambda: defaultdict(list))
for r in rows:
    for inv in r['investors']:
        inv_year[inv][r['year']] += 1
        inv_year_companies[inv][r['year']].append(r['name'])

# top investors overall (by dated deal count) for the default filter list
inv_totals = defaultdict(int)
for inv, yc in inv_year.items():
    inv_totals[inv] = sum(yc.values())
top_investors = sorted(inv_totals.items(), key=lambda x: -x[1])
top_investor_names = [i for i,c in top_investors if c >= 3]

out = {
 'years': years,
 'stage_labels': STAGE_LABELS,
 'grid': {str(y): {s: v for s, v in stages.items()} for y, stages in grid.items()},
 'investor_activity': {inv: dict(yc) for inv, yc in inv_year.items() if inv_totals[inv] >= 2},
 'investor_companies': {inv: {str(y): cos for y, cos in yc.items()} for inv, yc in inv_year_companies.items() if inv_totals[inv] >= 2},
 'top_investor_names': top_investor_names,
 'undated_count': total_companies - len(rows),
 'dated_count': len(rows),
}
json.dump(out, open(os.path.join(BUILD, 'timeline_data.json'),'w'))
print('years:', years)
print('top investors (dated deal count):', top_investors[:15])
print('total investors with 2+ dated deals:', len(out['investor_activity']))
