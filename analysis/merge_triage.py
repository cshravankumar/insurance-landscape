#!/usr/bin/env python3
"""Merge a census triage pass into insurtech-dataset.json.

Input: triage_batch_*.json (the original census records: name, website, ...) paired
with triage_result_*.json (one explicit include/exclude decision per company, with a
reason — see analysis/*triage* agent prompts for the schema). Every candidate must
appear in the result files; this script errors if any input record has no decision,
so a future triage pass can't silently skip anyone the way the original Sept merge did.

Writes:
  - new records for every "include" (deduped against existing names)
  - TRIAGE_LOG.md: every decision, include AND exclude, with its reason — committed,
    so the review is auditable instead of implicit.
"""
import glob, json, os, re, sys
from datetime import date

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BUILD = os.path.join(ROOT, 'build')
DS = os.path.join(ROOT, 'insurtech-dataset.json')
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
    head = ' '.join(x for x in [amt, lbl] if x)
    if when: head = f"{head}, {when}" if head else when
    if lead: head += f" (led by {lead})"
    return head or 'Funding not disclosed'

def norm(n): return re.sub(r'[^a-z0-9]', '', n.lower())

batch_pattern = sys.argv[1] if len(sys.argv) > 1 else 'triage_batch_*.json'
result_pattern = sys.argv[2] if len(sys.argv) > 2 else 'triage_result_*.json'

census = {}
for f in sorted(glob.glob(f'{BUILD}/{batch_pattern}')):
    for c in json.load(open(f)):
        census[c['company']] = c

results = {}
for f in sorted(glob.glob(f'{BUILD}/{result_pattern}')):
    for r in json.load(open(f)):
        results[r['name']] = r

missing = [n for n in census if n not in results]
if missing:
    print(f"ERROR: {len(missing)} census candidates have no triage decision (this is exactly the bug being fixed) -- not merging until every one is accounted for:")
    for n in missing: print(' ', n)
    sys.exit(1)

d = json.load(open(DS))
existing = {norm(c['name']) for c in d['companies']}

included, excluded, skipped_dupe = [], [], []
for name, r in results.items():
    if r['decision'] == 'exclude':
        excluded.append(r); continue
    if norm(name) in existing:
        skipped_dupe.append(name); continue
    c = census.get(name, {})
    d['companies'].append({
        'name': name,
        'url': c.get('website', ''),
        'what': r.get('what') or r.get('reason', ''),
        'workflow_step': r.get('workflow_step') or 'other',
        'buyer': r.get('buyer') or '',
        'stage': stage_text(r),
        'investors': [r['lead_investor']] if r.get('lead_investor') else [],
        'source': 'insurtechny-triage-2026-10',
        'funding_source': r.get('source_url'),
        'funding_refreshed': str(date.today()),
    })
    included.append(name)
    existing.add(norm(name))

json.dump(d, open(DS, 'w'), indent=1, ensure_ascii=False)

log = [f"# InsurTech NY census triage log — {date.today()}",
       "",
       f"Every one of the {len(results)} candidates from the InsurTech NY NYC/Boston maps that were",
       "never individually evaluated in the original Sept 2026 merge now has an explicit decision",
       "and reason below. This file exists so a gap like the original miss (24 of 180 candidates",
       "reviewed, the other 156 silently dropped) is checkable rather than implicit.",
       "",
       f"**{len(included)} included** ({len(skipped_dupe)} already in the dataset under a different name, skipped as duplicates), **{len(excluded)} excluded**.",
       "",
       "## Included", ""]
for n in sorted(included):
    r = results[n]
    log.append(f"- **{n}** — {r.get('reason','')}")
if skipped_dupe:
    log += ["", "## Already in dataset (duplicate, not re-added)", ""]
    for n in sorted(skipped_dupe): log.append(f"- {n}")
log += ["", "## Excluded", ""]
for r in sorted(excluded, key=lambda x: x['name']):
    log.append(f"- **{r['name']}** — {r.get('reason','')}")
open(f'{ROOT}/TRIAGE_LOG.md', 'w').write('\n'.join(log) + '\n')

print(f"included: {len(included)} | excluded: {len(excluded)} | duplicates skipped: {len(skipped_dupe)}")
print(f"dataset now: {len(d['companies'])} companies")
print("wrote TRIAGE_LOG.md")
