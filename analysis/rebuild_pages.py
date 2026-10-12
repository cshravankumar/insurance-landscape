#!/usr/bin/env python3
"""Regenerate the capital pages and investor graph from insurtech-dataset.json.

Runs capital_analysis.py + timeline_extract.py + timeline_build.py, then injects their
outputs into maps/capital-flow.html, maps/capital-timeline.html and refreshes the
per-company stage/investor strings in maps/insurtech-graph.html. Republishing the
artifacts is a separate, interactive step (Artifact tool) -- this only updates the files.
"""
import json, os, re, subprocess, sys
from datetime import date

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BUILD = os.path.join(ROOT, 'build'); os.makedirs(BUILD, exist_ok=True)
DS = os.path.join(ROOT, 'insurtech-dataset.json')
AN = os.path.join(ROOT, 'analysis')
MAPS = os.path.join(ROOT, 'maps')


for s in ('capital_analysis.py', 'timeline_extract.py', 'timeline_build.py'):
    r = subprocess.run([sys.executable, os.path.join(AN, s)], capture_output=True, text=True)
    if r.returncode: print(r.stderr); sys.exit(f'{s} failed')

ca = json.load(open(f'{BUILD}/capital_analysis.json'))
p = f'{MAPS}/capital-flow.html'; h = open(p).read()
for name, key in [('BY_STAGE','by_stage'),('FUNNEL','stage_funnel'),('TOP_INVESTORS','top_investors'),('DOUBLED_DOWN','doubled_down')]:
    h, n = re.subn(rf'^const {name} = .*?;$', lambda m: f'const {name} = ' + json.dumps(ca[key], separators=(",",":")) + ';', h, count=1, flags=re.M)
    assert n == 1, name
N = len(json.load(open(DS))['companies']); STAMP = date.today().strftime('%Y-%m')
h = re.sub(r"\d+ insurtech (?:startups|companies)'", f"{N} insurtech companies'", h)
h = re.sub(r'\d+ tracked insurtech (?:startups|companies)', f'{N} tracked insurtech companies', h)
h = re.sub(r'\(\d+ companies, this repo\)', f'({N} companies, this repo)', h)
h = re.sub(r'Compiled \d{4}-\d{2}', f'Compiled {STAMP}', h)
open(p, 'w').write(h)

td = json.load(open(f'{BUILD}/timeline_data.json'))
p = f'{MAPS}/capital-timeline.html'; t = open(p).read()
t, n = re.subn(r'^const DATA = .*?;$', lambda m: 'const DATA = ' + json.dumps(td, separators=(",",":")) + ';', t, count=1, flags=re.M); assert n == 1
und, dated = td['undated_count'], td['dated_count']; tot = und + dated
t = re.sub(r'\d+ of \d+ companies \(\d+%\) have no parseable date', f'{und} of {tot} companies ({round(100*und/tot)}%) have no parseable date', t)
t = re.sub(r'(insurtech-dataset\.json</code> )\(\d+ companies\)', rf'\g<1>({N} companies)', t)
t = re.sub(r'Compiled \d{4}-\d{2}', f'Compiled {STAMP}', t)
open(p, 'w').write(t)

ds = {c['name']: c for c in json.load(open(DS))['companies']}
p = f'{MAPS}/insurtech-graph.html'; g = open(p).read()
m = re.search(r'const DATA = (\{.*?\});\n', g, re.S); data = json.loads(m.group(1))
for c in data['companies']:
    src = ds.get(c['name'])
    if src: c['stage'] = (src.get('stage') or '')[:60]; c['investors'] = src.get('investors', [])
GROUP = {'MGA-ops': 'mga-uw', 'intake': 'mga-uw', 'triage': 'mga-uw', 'broker-ops': 'broker-ops',
         'full-stack-insurer': 'full-stack', 'claims-guidance': 'claims', 'claims-fnol': 'claims', 'fraud': 'claims',
         'policy-servicing': 'bind-service', 'quote-bind': 'bind-service', 'compliance': 'bind-service',
         'bordereaux': 'bind-service', 'risk-enrichment': 'risk-pricing', 'pricing': 'risk-pricing',
         'distribution/embedded': 'distribution', 'other': 'other'}
have = {c['name'] for c in data['companies']}
for name, src in ds.items():
    if name not in have:
        data['companies'].append({'name': name, 'what': src.get('what', ''), 'stage': (src.get('stage') or '')[:60],
                                  'g': GROUP.get(src['workflow_step'], 'other'), 'investors': src.get('investors', [])})
inv = {}
for c in data['companies']:
    for i in c['investors']: inv[i] = inv.get(i, 0) + 1
data['invCounts'] = inv
open(p, 'w').write(g[:m.start(1)] + json.dumps(data, ensure_ascii=True, separators=(",",":")) + g[m.end(1):])

bs = ca['by_stage']; tot_cap = sum(v['capital'] for v in bs.values())
print(f"rebuilt: ${tot_cap/1e9:.2f}B disclosed | new-carrier {round(100*bs['full-stack-insurer']['capital']/tot_cap)}% | dated {dated}/{tot} | funnel: "
      + ', '.join(f"{k} {v['count']}" for k, v in ca['stage_funnel'].items() if k in ('Nothing disclosed', 'Round not stated')))
