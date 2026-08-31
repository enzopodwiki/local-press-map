#!/usr/bin/env python3
"""在地刊物地图 · 数据校验

对仓库里的数据源与构建产物做一致性体检，发现问题按严重度输出：
  [错误] 必须修复（脚本退出码 1）——数据自相矛盾、封面缺失、构建产物过期等
  [提醒] 建议处理——http:// 链接、缺封面、孤儿文件、文档计数待更新等

用法：python3 tools/validate.py（配合 CI：先跑 python3 tools/build.py --check）
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'tools'))
from build import parse_md, assemble_data, MD_PATH  # noqa: E402

errors, notes = [], []


def err(msg):
    errors.append(msg)


def note(msg):
    notes.append(msg)


def main():
    html = (ROOT / 'index.html').read_text(encoding='utf-8')
    data, spec, pubs_by_title, problems = assemble_data()
    errors.extend(problems)
    all_pubs = [p for r in data for p in r['pubs']]
    total = len(all_pubs)

    # 1. 标题唯一
    seen = {}
    for p in all_pubs:
        seen[p['t']] = seen.get(p['t'], 0) + 1
    dup = [t for t, n in seen.items() if n > 1]
    if dup:
        err(f'刊物标题重复：{dup}')

    # 2. 页面总数与 DATA 一致（页面若保留「地图总录」徽章则校验之）
    m = re.search(r'<b id="stat-total">(\d+)</b>', html)
    if m and int(m.group(1)) != total:
        err(f'页面「地图总录」统计（{m.group(1)}）≠ 数据总数（{total}）')

    # 3. 地图 pin 数量与数据一致
    for r in data:
        pat = re.search(r'<g class="pin" data-r="' + re.escape(r['id']) +
                        r'"[^>]*>.*?<text class="pcount" y="3\.5">(\d+)</text>', html, re.S)
        if r.get('roam'):
            if pat:
                err(f'流动书柜 {r["id"]} 不应有 pin')
            continue
        if not pat:
            err(f'区域 {r["id"]} 缺少地图 pin')
        elif int(pat.group(1)) != len(r['pubs']):
            err(f'区域 {r["id"]} pin 数（{pat.group(1)}）≠ 刊物数（{len(r["pubs"])}）')

    # 4. 封面：引用的文件必须存在
    covers_dir = ROOT / 'covers'
    disk = {p.name for p in covers_dir.iterdir() if p.name != '.DS_Store'}
    used = set()
    no_cover = []
    for p in all_pubs:
        if p['cover']:
            used.add(Path(p['cover']).name)
            if not (covers_dir / Path(p['cover']).name).exists():
                err(f'封面文件缺失：{p["t"]} → {p["cover"]}')
        else:
            no_cover.append(p['t'])
    orphans = sorted(disk - used)
    if orphans:
        note(f'covers/ 里未被任何刊物引用的孤儿文件：{orphans}')
    if no_cover:
        note(f'暂无封面的刊物（{len(no_cover)} 种，页面会显示「封面位 · 待置入」）：{no_cover}')

    # 5. 信源链接
    bad = [(p['t'], u) for p in all_pubs for _, u in p['l']
           if not re.match(r'^https?://', u)]
    for t, u in bad:
        err(f'信源链接不是 http(s)：{t} → {u}')
    insecure = [p['t'] for p in all_pubs for _, u in p['l'] if u.startswith('http://')]
    if insecure:
        note(f'使用 http:// 的信源（建议换 https）：{sorted(set(insecure))}')

    # 6. 「更新啦」：书柜 id、地域名、书名都要能对上（点击会深链跳到具体那本书）
    updates = re.search(r'const UPDATES = \[.*?\];', html, re.S).group(0)
    by_id = {r['id']: r for r in data}
    for m in re.finditer(r"\['([a-z0-9-]+)',\s*'([^']*)',\s*'(.*?)'\]", updates):
        rid, label, title = m.group(1), m.group(2), m.group(3)
        g = by_id.get(rid)
        if not g:
            err(f'「更新啦」引用了不存在的书柜 id：{rid}')
            continue
        if label != g['region']:
            note(f'「更新啦」地域名与数据不一致：{rid} 写的是「{label}」，书柜实际叫「{g["region"]}」')
        if not any(p['t'] == title for p in g['pubs']):
            err(f'「更新啦」条目在书柜 {rid}（{g["region"]}）中找不到：{title}')

    # 7. 档案文档自身
    md_text = MD_PATH.read_text(encoding='utf-8')
    parsed, order = parse_md(MD_PATH)
    mapped = {t for rg in spec['regions'] for t in rg['pubs']}
    excluded = set(spec.get('exclude', []))
    for t in mapped:
        if t not in parsed:
            err(f'书柜引用的刊物在档案中无条目：{t}')
        elif not parsed[t]['i']:
            err(f'档案条目介绍为空：{t}')
    unmapped = [t for t in order if t not in mapped and t not in excluded]
    if unmapped:
        note(f'档案中有条目未编入任何书柜（如非刻意，请检查）：{unmapped}')
    m = re.search(r'##### 刊物总数：(\d+) 种', md_text)
    if m and int(m.group(1)) != total:
        note(f'档案头部的「刊物总数」（{m.group(1)}）≠ 数据总数（{total}），请同步更新')
    m = re.search(r'\*\*合计\*\* \| \*\*(\d+)\*\*', md_text)
    if m and int(m.group(1)) != total:
        note(f'档案统计表的「合计」（{m.group(1)}）≠ 数据总数（{total}），请同步更新')

    # 汇总
    for n in notes:
        print('[提醒]', n)
    if errors:
        print()
        for e in errors:
            print('[错误]', e)
        print(f'\n校验未通过：{len(errors)} 个错误，{len(notes)} 条提醒')
        sys.exit(1)
    print(f'\n校验通过：{total} 种刊物、{len(data)} 个书柜，{len(notes)} 条提醒')


if __name__ == '__main__':
    main()
