"""Shared, fixed parsing of free-text funding descriptions.
Bug fixed 2026-09-22: the old parser took the LARGEST $ figure in the text, so
"$108M ... at $2.6B valuation" counted $2.6B as money raised. Valuations,
acquisition prices, lending commitments, GWP/ARR figures are now excluded."""
import re

# $ / £ / € / GBP / EUR / USD amounts; non-USD converted at a flat approximate rate (good enough for a
# capital-flow chart, wrong for accounting) -- USD_PER tells the reader which figures were converted.
MONEY_RE = re.compile(r'(?:(\$|£|€|USD|GBP|EUR)\s?)([\d,.]+)(?:\s?[-–]\s?[\d,.]+)?\s*([MBK])\b', re.I)
USD_PER = {'$':1.0,'USD':1.0,'£':1.27,'GBP':1.27,'€':1.08,'EUR':1.08}
# words that mean "this $ figure is NOT money raised by the company"
AFTER_BAD  = re.compile(r'^\W{0,3}\+?\s*(valuation|valued|post[- ]money|pre[- ]money|lending|credit|commitment|debt facility|GWP|premium|revenue|ARR|market)', re.I)
BEFORE_BAD = re.compile(r'(acquir\w*|acquisition|bought|sold|exit\w*|deal value|valued at|valuation of|worth|for)\s*(~|about|approx\.?|around|c\.)?\s*$', re.I)
TOTAL_AFTER = re.compile(r'^\W{0,3}\+?\s*(total|raised|to date|cumulative|lifetime|in total)', re.I)
TOTAL_BEFORE = re.compile(r'(total(?:ing)?|raised|cumulative)\s*(of|:)?\s*(~|about|approx\.?|around|c\.)?\s*$', re.I)

def _figures(s):
    out = []
    for m in MONEY_RE.finditer(s):
        try:
            v = float(m.group(2).replace(',', '')) * {'K':1e3,'M':1e6,'B':1e9}[m.group(3).upper()] * USD_PER[m.group(1).upper() if m.group(1).isalpha() else m.group(1)]
        except (ValueError, KeyError):
            continue
        before, after = s[max(0,m.start()-28):m.start()], s[m.end():m.end()+30]
        if AFTER_BAD.search(after) or BEFORE_BAD.search(before):
            continue
        is_total = bool(TOTAL_AFTER.search(after) or TOTAL_BEFORE.search(before))
        out.append((v, is_total, m.start(), m.end()))
    return out

def parse_money(s):
    """Best-effort total raised. Returns list with ONE value (or empty) so callers
    that do max(list) keep working."""
    figs = _figures(s or '')
    if not figs:
        return []
    totals = [v for v,t,_,_ in figs if t]
    if totals:
        return [max(totals)]
    # rounds joined with '+' ("$108M ... + $106M ...", "$185M (2021) + $20M extension") -> sum
    if len(figs) > 1 and any('+' in s[figs[i][3]:figs[i+1][2]] for i in range(len(figs)-1)):
        return [sum(v for v,_,_,_ in figs)]
    return [max(v for v,_,_,_ in figs)]

STAGE_RE = re.compile(r'\b(pre-?seed|seed|series\s+[a-g]\+?|ipo|public)\b', re.I)
def parse_stage_label(s):
    s = s or ''
    if re.search(r'\bIPO\b|\bpublic\b|\bnasdaq\b|\bnyse\b', s, re.I):
        return 'IPO/public'
    m = STAGE_RE.search(s)
    if not m:
        return 'Unfunded/undisclosed'
    lbl = re.sub(r'\s+', ' ', m.group(1)).title().replace('Pre-Seed','Pre-Seed').replace('Preseed','Pre-Seed')
    if lbl.lower().startswith('pre'): return 'Pre-Seed'
    if lbl.lower() == 'seed': return 'Seed'
    return lbl  # "Series A" etc.
