#!/usr/bin/env python3
"""Freshness probe: detect funding news newer than each record's last verification.

Same architecture as probe.py: the script DETECTS candidates cheaply and deterministically;
a human/Claude VERIFIES at the primary source before anything changes in the dataset.

Source: Google News RSS search with a date operator (no key, no ToS-gated scraping; ~1 req/s).
Writes:  data/freshness/<date>.json        raw hits (gitignored)
         data/freshness/seen.json          links already surfaced (gitignored)
         FRESHNESS.md                      the human queue (committed), newest first

Usage:   python3 analysis/freshness_probe.py            # all companies
         python3 analysis/freshness_probe.py --limit 20 # smoke test
"""
import json, os, re, sys, time, urllib.parse, urllib.request, xml.etree.ElementTree as ET
from datetime import date, datetime, timedelta
from email.utils import parsedate_to_datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DS = os.path.join(ROOT, 'insurtech-dataset.json')
OUT_DIR = os.path.join(ROOT, 'data', 'freshness')
QUEUE = os.path.join(ROOT, 'FRESHNESS.md')
SEEN = os.path.join(OUT_DIR, 'seen.json')

# A headline counts only if it names the company AND carries a hard funding signal: a money amount,
# an explicit raise phrase, or an exit phrase that also mentions insurance. Bare "acquires" is not
# enough -- "Strada acquires a business park" and "Harper Fire acquires a YA novel" both passed a looser filter.
MONEY = re.compile(r'(\$|£|€|USD|GBP|EUR)\s?\d[\d,.]*\s?(m|mn|million|b|bn|billion)\b', re.I)
RAISE = re.compile(r'\b(raises?|raised|raising|secures?|closes?|lands?|nabs?|bags?)\b.{0,40}\b(funding|round|seed|series [a-g]|capital|investment|financing)\b|\b(series [a-g]|seed|pre-seed)\b.{0,30}\b(round|funding|financing)\b', re.I)
EXIT = re.compile(r'\b(acqui[rs]\w*|to be acquired|merges? with|merger|shuts? down|shutting down|winds? down|ceases? operations|ipo|goes public|take[sn]? private)\b', re.I)
INSURANCE = re.compile(r'\b(insur\w*|mga|broker\w*|claims|underwrit\w*|carrier|reinsur\w*|benefits|actuar\w*)\b', re.I)
NOISE = re.compile(r'\b(revenue 20\d\d|est\. arr|getlatka|job|hiring|webinar|podcast|stock price|share price)\b', re.I)

def is_funding_signal(title):
    if NOISE.search(title): return False
    if MONEY.search(title) or RAISE.search(title): return True
    return bool(EXIT.search(title) and INSURANCE.search(title))
SLACK_DAYS = 45   # look back a bit before the record date so a round announced just before it isn't missed

def fetch(company, after):
    q = f'"{company}" (raises OR raised OR funding OR "Series" OR seed OR acquired OR acquires)'
    if after: q += f' after:{after}'
    url = 'https://news.google.com/rss/search?q=' + urllib.parse.quote(q) + '&hl=en-US&gl=US&ceid=US:en'
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (appetite-probe freshness check; contact in repo)'})
    xml = urllib.request.urlopen(req, timeout=25).read()
    out = []
    for it in ET.fromstring(xml).findall('.//item'):
        title, link, pub = it.findtext('title') or '', it.findtext('link') or '', it.findtext('pubDate') or ''
        try: d = parsedate_to_datetime(pub).date()
        except Exception: continue
        out.append({'date': d.isoformat(), 'title': title, 'link': link, 'source': (it.findtext('source') or '').strip()})
    return out

def record_date(c):
    return c.get('funding_refreshed') or c.get('funding_as_of') or '2026-09-09'

def main():
    limit = None
    if '--limit' in sys.argv: limit = int(sys.argv[sys.argv.index('--limit') + 1])
    os.makedirs(OUT_DIR, exist_ok=True)
    seen = set(json.load(open(SEEN))) if os.path.exists(SEEN) else set()
    companies = json.load(open(DS))['companies']
    if limit: companies = companies[:limit]
    today = date.today().isoformat()
    candidates, errors = [], []
    for i, c in enumerate(companies):
        base = datetime.fromisoformat(record_date(c)).date()
        after = (base - timedelta(days=SLACK_DAYS)).isoformat()
        try:
            hits = fetch(c['name'], after)
        except Exception as e:
            errors.append((c['name'], str(e)[:80])); continue
        for h in hits:
            if h['date'] < base.isoformat(): continue                 # older than what the record already reflects
            if c['name'].lower() not in h['title'].lower(): continue   # title must actually name the company (name-collision guard)
            if not is_funding_signal(h['title']): continue
            key = h['link']
            if key in seen: continue
            seen.add(key)
            candidates.append({'company': c['name'], 'record_date': base.isoformat(), 'current_stage': c.get('stage', ''), **h})
        time.sleep(1.1)
        if (i + 1) % 25 == 0: print(f'  {i+1}/{len(companies)} checked, {len(candidates)} candidates so far', flush=True)

    json.dump(candidates, open(os.path.join(OUT_DIR, f'{today}.json'), 'w'), indent=1)
    json.dump(sorted(seen), open(SEEN, 'w'))

    # human queue, newest first
    prev = open(QUEUE).read() if os.path.exists(QUEUE) else ''
    header = (f"# Funding freshness queue\n\nCandidates surfaced by `analysis/freshness_probe.py` (Google News RSS, funding keywords, "
              f"newer than each record's `funding_refreshed`/`funding_as_of`). **Nothing here is verified.** To act on one: open the link, "
              f"confirm at the primary source, then update the record's `stage` text (standard format: `$XM Series Y, Mon YYYY (led by Z); $T total`), "
              f"set `funding_source` + `funding_refreshed`, run `python3 analysis/rebuild_pages.py`, commit. Delete the row once handled.\n\n")
    body = prev[len(header):] if prev.startswith(header) else re.sub(r'^# Funding freshness queue.*?\n\n(?:.*?\n\n)?', '', prev, count=1, flags=re.S)
    new = f"## Run {today} — {len(candidates)} candidates across {len(companies)} companies" + (f", {len(errors)} fetch errors" if errors else '') + "\n\n"
    if candidates:
        new += "| Company | Record as of | News date | Headline | Source |\n|---|---|---|---|---|\n"
        for h in sorted(candidates, key=lambda x: x['date'], reverse=True):
            new += f"| {h['company']} | {h['record_date']} | {h['date']} | [{h['title'][:110].replace('|','/')}]({h['link']}) | {h['source']} |\n"
        new += "\n"
    else:
        new += "_No new funding news newer than the records._\n\n"
    open(QUEUE, 'w').write(header + new + body)
    print(f"done: {len(candidates)} candidates, {len(errors)} errors -> FRESHNESS.md")
    for n, e in errors[:5]: print('  error:', n, e)

if __name__ == '__main__':
    main()
