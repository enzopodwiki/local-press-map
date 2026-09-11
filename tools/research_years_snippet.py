#!/usr/bin/env python3
"""从官方页 HTML 提取创刊线索（临时调研用）。"""
import sys, re, html
s = open(sys.argv[1], encoding='utf-8', errors='ignore').read()
text = html.unescape(re.sub(r'<[^>]+>', ' ', re.sub(r'<script.*?</script>|<style.*?</style>', '', s, flags=re.S)))
text = re.sub(r'\s+', ' ', text)
hits = []
for pat in [r'(創刊|第\s*1\s*期|第一期|创刊)[^。]{0,60}', r'民國\s*\d{2,3}\s*年[^。，]{0,40}',
            r'(19[5-9]\d|20[0-2]\d)\s*年\s*[01]?\d?\s*月[^。，]{0,30}']:
    for mm in re.finditer(pat, text):
        hits.append(mm.group(0)[:70])
seen = set()
for h in hits[:8]:
    if h not in seen:
        seen.add(h)
        print('  线索:', h)
if not seen:
    print('  （无创刊线索，页面大小', len(s), '字节）')
