#!/usr/bin/env python3
"""Regenerate the capital pages and investor graph from insurtech-dataset.json.

Runs capital_analysis.py + timeline_extract.py + timeline_build.py, then injects their
outputs into maps/capital-flow.html, maps/capital-timeline.html and refreshes the
per-company stage/investor strings in maps/insurtech-graph.html. Republishing the
artifacts is a separate, interactive step (Artifact tool) -- this only updates the files.
"""
import json, os, re, subprocess, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BUILD = os.path.join(ROOT, 'build'); os.makedirs(BUILD, exist_ok=True)
DS = os.path.join(ROOT, 'insurtech-dataset.json')
AN = os.path.join(ROOT, 'analysis')
MAPS = ROOT  # pages sit at the site root in this repo


for s in ('capital_analysis.py', 'timeline_extract.py', 'timeline_build.py'):
    r = subprocess.run([sys.executable, os.path.join(AN, s)], capture_output=True, text=True)
    if r.returncode: print(r.stderr); sys.exit(f'{s} failed')

ca = json.load(open(f'{BUILD}/capital_analysis.json'))
p = f'{MAPS}/capital-flow.html'; h = open(p).read()
for name, key in [('BY_STAGE','by_stage'),('FUNNEL','stage_funnel'),('TOP_INVESTORS','top_investors'),('DOUBLED_DOWN','doubled_down')]:
    h, n = re.subn(rf'^const {name} = .*?;$', lambda m: f'const {name} = ' + json.dumps(ca[key], separators=(",",":")) + ';', h, count=1, flags=re.M)
    assert n == 1, name
open(p, 'w').write(h)

td = json.load(open(f'{BUILD}/timeline_data.json'))
p = f'{MAPS}/capital-timeline.html'; t = open(p).read()
t, n = re.subn(r'^const DATA = .*?;$', lambda m: 'const DATA = ' + json.dumps(td, separators=(",",":")) + ';', t, count=1, flags=re.M); assert n == 1
und, dated = td['undated_count'], td['dated_count']; tot = und + dated
t = re.sub(r'\d+ of \d+ companies \(\d+%\) have no parseable date', f'{und} of {tot} companies ({round(100*und/tot)}%) have no parseable date', t)
open(p, 'w').write(t)

ds = {c['name']: c for c in json.load(open(DS))['companies']}
p = f'{MAPS}/insurtech-graph.html'; g = open(p).read()
m = re.search(r'const DATA = (\{.*?\});\n', g, re.S); data = json.loads(m.group(1))
for c in data['companies']:
    src = ds.get(c['name'])
    if src: c['stage'] = (src.get('stage') or '')[:60]; c['investors'] = src.get('investors', [])
inv = {}
for c in data['companies']:
    for i in c['investors']: inv[i] = inv.get(i, 0) + 1
data['invCounts'] = inv
open(p, 'w').write(g[:m.start(1)] + json.dumps(data, ensure_ascii=True, separators=(",",":")) + g[m.end(1):])

bs = ca['by_stage']; tot_cap = sum(v['capital'] for v in bs.values())
print(f"rebuilt: ${tot_cap/1e9:.2f}B disclosed | new-carrier {round(100*bs['full-stack-insurer']['capital']/tot_cap)}% | dated {dated}/{tot} | funnel: "
      + ', '.join(f"{k} {v['count']}" for k, v in ca['stage_funnel'].items() if k in ('Nothing disclosed', 'Round not stated')))
