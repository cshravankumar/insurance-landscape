#!/usr/bin/env python3
"""Merge researched funding refreshes into insurtech-dataset.json.

Input: refresh_result_*.json (one object per company; see the agent prompt for keys).
Only sourced amounts (source_url present, confidence high/medium) rewrite a record's
`stage` text. Acquired/shut-down companies with no sourced raise get an outcome line.
Everything else is left untouched. Every touched record gets `funding_source` and
`funding_refreshed` so the provenance is on the record, not in a chat log.
"""
import glob, json, sys
from datetime import date

import os
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BUILD = os.path.join(ROOT, 'build'); os.makedirs(BUILD, exist_ok=True)
DS = os.path.join(ROOT, 'insurtech-dataset.json')
SP = os.environ.get('REFRESH_DIR', BUILD)  # where the research agents wrote refresh_/verify_ results
MONTHS = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec']

def fmt_date(s):
    if not s: return ''
    if len(s) >= 7 and s[4] == '-':
        try: return f"{MONTHS[int(s[5:7])-1]} {s[:4]}"
        except (ValueError, IndexError): return s[:4]
    return s[:4]

def fmt_amt(v, cur):
    if v is None: return None
    cur = cur or '$'
    v = float(v)
    return f"{cur}{v:g}M" if v < 1000 else f"{cur}{v/1000:g}B"

def stage_text(r):
    amt = fmt_amt(r.get('latest_round_amount'), r.get('currency'))
    lbl = r.get('latest_round_label') or ''
    when = fmt_date(r.get('latest_round_date'))
    lead = r.get('lead_investor')
    total = fmt_amt(r.get('total_raised_amount'), r.get('total_currency') or r.get('currency'))
    parts = []
    head = ' '.join(x for x in [amt, lbl] if x)
    if when: head = f"{head}, {when}" if head else when
    if lead: head += f" (led by {lead})"
    if head: parts.append(head)
    if total and (r.get('total_raised_amount') or 0) > (r.get('latest_round_amount') or 0):
        parts.append(f"{total} total")
    if r.get('acquirer_or_outcome'):
        parts.append(r['acquirer_or_outcome'])
    return '; '.join(parts)

pattern = sys.argv[1] if len(sys.argv) > 1 else 'refresh_result_*.json'   # e.g. verify_result_*.json
results = {}
files = sorted(glob.glob(f'{SP}/{pattern}'))
for f in files:
    for r in json.load(open(f)):
        results[r['name']] = r
print(f"loaded {len(results)} researched records from {len(files)} files ({pattern})")

p = f'{ROOT}/insurtech-dataset.json'
d = json.load(open(p))
changed, outcome_only, confirmed, untouched = [], [], [], []
for c in d['companies']:
    r = results.get(c['name'])
    if not r: continue
    sourced = r.get('source_url') and r.get('confidence') in ('high', 'medium')
    if sourced and r.get('confirms_existing') and r.get('latest_round_amount') is None:
        # agent confirmed the existing text is current and cited it: stamp provenance, keep the text
        c['funding_source'] = r['source_url']; c['funding_refreshed'] = str(date.today())
        if r.get('status') in ('acquired', 'shut_down', 'public'): c['status'] = r['status']
        confirmed.append(c['name']); continue
    if sourced and r.get('latest_round_amount') is not None:
        old = c.get('stage', '')
        c['stage'] = stage_text(r)
        c['funding_source'] = r['source_url']
        c['funding_refreshed'] = str(date.today())
        if r.get('status') in ('acquired', 'shut_down', 'public'): c['status'] = r['status']
        (confirmed if r.get('confirms_existing') else changed).append((c['name'], old, c['stage']) if not r.get('confirms_existing') else c['name'])
    elif r.get('status') in ('acquired', 'shut_down', 'public') and r.get('acquirer_or_outcome'):
        old = c.get('stage', '')
        note = r['acquirer_or_outcome']
        if note.lower() not in old.lower():
            c['stage'] = f"{old}; {note}" if old else note
        if r.get('source_url'): c['funding_source'] = r['source_url']
        c['funding_refreshed'] = str(date.today())
        c['status'] = r['status']
        outcome_only.append((c['name'], c['stage']))
    else:
        untouched.append((c['name'], r.get('confidence'), r.get('notes', '')[:70]))

json.dump(d, open(p, 'w'), indent=1, ensure_ascii=False)
print(f"\n== confirmed current (provenance stamped, text kept or re-rendered from the same round): {len(confirmed)}")
print('  ' + ', '.join(confirmed))
print(f"\n== rewrote funding text with a sourced NEWER/different amount: {len(changed)}")
for n, o, s in changed: print(f"  {n:28s} | {o[:38]:38s} -> {s[:70]}")
print(f"\n== outcome recorded, no sourced raise: {len(outcome_only)}")
for n, s in outcome_only: print(f"  {n:28s} | {s[:80]}")
print(f"\n== left as-is (nothing sourced): {len(untouched)}")
for n, conf, note in untouched: print(f"  {n:28s} | {conf} | {note}")
