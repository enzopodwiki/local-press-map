#!/usr/bin/env python3
"""在地刊物地图 · 构建脚本

数据流：data/在地刊物地图.md + data/regions.json → template.html → index.html

- MD 档案是刊物内容（标题/地点/年份/频率/停刊/介绍/信源/封面）的唯一数据源；
- regions.json 描述结构（书柜分组、顺序、地图归属），新增地区时才需要改它；
- 地图 pin 的坐标画在 template.html 的 SVG 里，pin 上的数量由本脚本按数据回填。

用法：
    python3 tools/build.py             # 构建并覆盖 index.html
    python3 tools/build.py --check     # 构建到内存，与现有 index.html 比对（CI 用）
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MD_PATH = ROOT / 'data' / '在地刊物地图.md'
REGIONS_PATH = ROOT / 'data' / 'regions.json'
FRESH_PATH = ROOT / 'data' / 'new_issues.json'
TEMPLATE_PATH = ROOT / 'template.html'
OUTPUT_PATH = ROOT / 'index.html'
FRESH_BATCHES = 6  # 页面「新刊速递」模块展示的最近批次数


def parse_md(path):
    """解析档案 MD，返回 {标题: pub 字典}。

    条目格式：
        #### 《标题》
        📍地点｜🕐年份｜📌频率｜⛔已停刊        （空字段省略；「已停刊」写在任何位置都能识别）
        介绍正文（单行）
        信源：[名称](链接) ｜ [名称](链接)      （可无）
        封面：covers/c001.jpeg                 （可无）
    """
    text = Path(path).read_text(encoding='utf-8')
    blocks, order, cur = {}, [], None
    for line in text.split('\n'):
        if line.startswith('#### '):
            cur = line[5:].strip()
            blocks[cur] = []
            order.append(cur)
        elif cur is not None:
            if line.startswith(('### ', '## ', '# ', '---')):
                cur = None
            else:
                blocks[cur].append(line)

    pubs = {}
    for title, lines in blocks.items():
        meta, intro, links, cover = '', [], [], ''
        for ln in lines:
            s = ln.strip()
            if not s:
                continue
            if s.startswith('📍'):
                meta = s
            elif s.startswith('信源'):
                links = [[a.strip(), b.strip()]
                         for a, b in re.findall(r'\[([^\]]+)\]\(([^)]+)\)', s)]
            elif s.startswith('封面'):
                cover = s.split('：', 1)[1].strip() if '：' in s else ''
            else:
                intro.append(s)
        p = y = f = ''
        for part in meta.split('｜'):
            part = part.strip()
            if part.startswith('📍'):
                p = part[1:].strip()
            elif part.startswith('🕐'):
                y = part[1:].strip()
            elif part.startswith('📌'):
                f = part[1:].strip()
            elif part.startswith('⛔'):
                pass
            elif part and not f:
                f = part
        s = '已停刊' if '已停刊' in meta else ''
        # 兼容「📌…（已停刊）」「📌…，已停刊）」两种旧写法：状态进 s，频率里去掉
        f = f.replace('，已停刊）', '）').replace('（已停刊）', '').strip()
        pubs[title] = {'t': title, 'p': p, 'y': y, 'f': f, 's': s,
                       'i': ''.join(intro), 'l': links, 'cover': cover}
    return pubs, order


def meta_line(pub):
    """由字段重建 📍 元信息行（regen_md_from_html.py 与 build 校验共用）。"""
    parts = []
    if pub['p']:
        parts.append('📍' + pub['p'])
    if pub['y']:
        parts.append('🕐' + pub['y'])
    if pub['f']:
        parts.append('📌' + pub['f'])
    if pub['s']:
        parts.append('⛔已停刊')
    return '｜'.join(parts)


def entry_block(pub):
    """由字段重建完整 MD 条目（不含条目间的空行）。"""
    lines = ['#### ' + pub['t'], meta_line(pub)]
    if pub['i']:
        lines.append(pub['i'])
    if pub['l']:
        lines.append('信源：' + ' ｜ '.join(f'[{n}]({u})' for n, u in pub['l']))
    if pub['cover']:
        lines.append('封面：' + pub['cover'])
    return lines


def assemble_data():
    """读数据源，拼出 DATA 数组（键序与历史版本保持一致）。"""
    pubs, _ = parse_md(MD_PATH)
    spec = json.loads(REGIONS_PATH.read_text(encoding='utf-8'))
    data, problems = [], []
    for rg in spec['regions']:
        group = []
        for t in rg['pubs']:
            if t not in pubs:
                problems.append(f'书柜 {rg["id"]} 的刊物在档案中找不到：{t}')
                continue
            group.append(pubs[t])
        obj = {'id': rg['id'], 'region': rg['region'], 'map': rg['map'], 'pubs': group}
        if rg.get('sub'):
            obj['sub'] = rg['sub']
        if rg.get('roam'):
            obj['roam'] = True
        data.append(obj)
    return data, spec, pubs, problems


def render(data):
    """注入模板：DATA、总数、各 pin 的数量、新刊速递批次。"""
    html = TEMPLATE_PATH.read_text(encoding='utf-8')
    total = sum(len(r['pubs']) for r in data)
    html = html.replace('const DATA = __DATA__;',
                        'const DATA = ' + json.dumps(data, ensure_ascii=False, indent=1) + ';')
    if '__TOTAL__' in html:  # 页面保留「地图总录」徽章时回填总数
        html = html.replace('<b id="stat-total">__TOTAL__</b>', f'<b id="stat-total">{total}</b>')
    if '__FRESH__' in html:  # 新刊速递：最近几个抓取批次（new_issues.json 的 batches）
        batches = []
        if FRESH_PATH.exists():
            batches = json.loads(FRESH_PATH.read_text(encoding='utf-8')).get('batches', [])
        html = html.replace('const FRESH_ISSUES = __FRESH__;',
                            'const FRESH_ISSUES = ' + json.dumps(batches[:FRESH_BATCHES], ensure_ascii=False, indent=1) + ';')
    for rg in data:
        pat = re.compile(r'(<g class="pin" data-r="' + re.escape(rg['id']) +
                         r'"[^>]*>.*?<text class="pcount" y="3\.5">)\d+(</text>)', re.S)
        html, n = pat.subn(r'\g<1>' + str(len(rg['pubs'])) + r'\g<2>', html, count=1)
        if n == 0 and not rg.get('roam'):
            raise SystemExit(f'构建失败：非流动书柜区域缺少地图 pin：{rg["id"]}')
    return html, total


def main():
    data, spec, pubs, problems = assemble_data()
    if problems:
        raise SystemExit('构建失败：\n  ' + '\n  '.join(problems))
    html, total = render(data)

    if '--check' in sys.argv:
        old = OUTPUT_PATH.read_text(encoding='utf-8')
        if html == old:
            print(f'--check 通过：index.html 与数据源完全一致（{total} 种刊物，{len(data)} 个书柜）')
            return
        raise SystemExit('--check 失败：index.html 与数据源不一致，请运行 python3 tools/build.py 重新构建')

    OUTPUT_PATH.write_text(html, encoding='utf-8')
    per_map = {}
    for r in data:
        per_map[r['map']] = per_map.get(r['map'], 0) + len(r['pubs'])
    print(f'构建完成：index.html（{total} 种刊物，{len(data)} 个书柜）')
    print('  分地图：', '，'.join(f'{k} {v}' for k, v in per_map.items()))


if __name__ == '__main__':
    main()
