#!/usr/bin/env python3
"""一次性迁移脚本（P0 重构，2026-08-30）

P0 之前的状况：线上 index.html 是唯一最新的数据（169 种刊物），档案 MD 在仓库外且落后
155 处字段修订，data_v4.js 已停更。本脚本把当时的快照拆成可维护的三件套：

    index.html + 旧档案MD（~/Downloads/在地刊物地图V4.md）
        ├─→ data/在地刊物地图.md   内容源：以 HTML 为准重建条目正文，补「封面：」行
        ├─→ data/regions.json      结构源：书柜分组/顺序/地图归属（从 HTML DATA 提取）
        └─→ template.html          版式源：HTML 去掉数据（DATA/总数留占位符）

最后用 tools/build.py 回渲一遍，与原 index.html 逐字节比对，证明管线可完整复现线上页面。
迁移完成后此脚本仅作存档，日常维护不再使用。
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'tools'))
from build import parse_md, entry_block, render, assemble_data  # noqa: E402

OLD_MD = Path.home() / 'Downloads' / '在地刊物地图V4.md'
HTML = ROOT / 'index.html'
RENAMES = {  # HTML 里已改名、档案仍用旧名
    '《星球雷达：我们与山野的距离》': '《星球雷达》',
}


def main():
    html_text = HTML.read_text(encoding='utf-8')
    data = json.loads(re.search(r'const DATA = (\[.*?\]);\n', html_text, re.S).group(1))
    html_pubs = {p['t']: p for r in data for p in r['pubs']}
    # 字段规范化：原 HTML 有 5 处 y 字段带首尾空格（手工编辑残留），条目按修剪后的值重建
    trims = [(t, k, p[k]) for t, p in html_pubs.items()
             for k in ('p', 'y', 'f') if isinstance(p[k], str) and p[k] != p[k].strip()]
    for p in html_pubs.values():
        for k in ('p', 'y', 'f'):
            if isinstance(p[k], str):
                p[k] = p[k].strip()

    # ---------- 1. 重建档案 MD ----------
    old_lines = OLD_MD.read_text(encoding='utf-8').split('\n')
    out, excluded, i = [], [], 0
    while i < len(old_lines):
        line = old_lines[i]
        if line.startswith('#### '):
            old_t = line[5:].strip()
            new_t = RENAMES.get(old_t, old_t)
            body = []
            i += 1
            while i < len(old_lines) and not old_lines[i].startswith(('#### ', '### ', '## ', '# ', '---')):
                body.append(old_lines[i])
                i += 1
            if new_t in html_pubs:
                out.extend(entry_block(html_pubs[new_t]))
                out.append('')
            else:  # 未上网的条目（如香港社区报）原样保留
                excluded.append(old_t)
                out.append('#### ' + old_t)
                out.extend(body)
                while out and out[-1].strip() == '':
                    out.pop()
                out.append('')
            continue
        out.append(line)
        i += 1

    md_path = ROOT / 'data' / '在地刊物地图.md'
    md_path.parent.mkdir(exist_ok=True)
    md_path.write_text('\n'.join(out), encoding='utf-8')

    # ---------- 2. 提取结构 regions.json ----------
    regions = []
    for r in data:
        rg = {'id': r['id'], 'region': r['region'], 'map': r['map'],
              'pubs': [p['t'] for p in r['pubs']]}
        if r.get('sub'):
            rg['sub'] = r['sub']
        if r.get('roam'):
            rg['roam'] = True
        regions.append(rg)
    spec = {'exclude': excluded, 'regions': regions}
    (ROOT / 'data' / 'regions.json').write_text(
        json.dumps(spec, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')

    # ---------- 3. 提取模板 ----------
    tpl = re.sub(r'const DATA = \[.*?\];\n', 'const DATA = __DATA__;\n', html_text, count=1, flags=re.S)
    tpl = re.sub(r'(<b id="stat-total">)\d+(</b>)', r'\g<1>__TOTAL__\g<2>', tpl, count=1)
    (ROOT / 'template.html').write_text(tpl, encoding='utf-8')

    # ---------- 4. 验证 ----------
    errors = []
    parsed, order = parse_md(md_path)

    for t, p in html_pubs.items():
        q = parsed.get(t)
        if not q:
            errors.append(f'新档案缺条目：{t}')
            continue
        for k in ('p', 'y', 'f', 's', 'i', 'l', 'cover'):
            if p[k] != q[k]:
                errors.append(f'[{t}] 字段 {k} 回读不一致\n  期望: {p[k]!r}\n  实得: {q[k]!r}')
    stale = [t for t in order if t in parsed and not parsed[t]['i'] and t not in excluded]
    if stale:
        errors.append(f'条目介绍为空：{stale}')

    # 回渲比对：允许且仅允许上述空白规范化——把原 HTML 的 DATA 按同一规范修剪后应逐字节一致
    trimmed = json.loads(re.search(r'const DATA = (\[.*?\]);\n', html_text, re.S).group(1))
    for r in trimmed:
        for p in r['pubs']:
            for k in ('p', 'y', 'f'):
                if isinstance(p[k], str):
                    p[k] = p[k].strip()
    expected = re.sub(r'(const DATA = )\[.*?\];\n',
                      lambda m: m.group(1) + json.dumps(trimmed, ensure_ascii=False, indent=1) + ';\n',
                      html_text, count=1, flags=re.S)
    data2, spec2, pubs2, problems = assemble_data()
    if problems:
        errors.extend(problems)
    rendered, total = render(data2)
    if rendered != expected:
        pos = next((k for k, (x, y) in enumerate(zip(rendered, expected)) if x != y),
                   min(len(rendered), len(expected)))
        errors.append(f'回渲与修剪后的原 HTML 不一致（总长 {len(rendered)} vs {len(expected)}），'
                      f'位置 {pos} 附近：{rendered[pos-60:pos+60]!r}')
    if total != 169:
        errors.append(f'总数异常：{total}')

    if errors:
        raise SystemExit('迁移验证失败：\n' + '\n'.join(errors))
    print(f'迁移完成：{total} 种刊物全部回读一致；条目字段规范化了 {len(trims)} 处首尾空格：')
    for t, k, v in trims:
        print(f'  [{t}] {k}: {v!r} -> {v.strip()!r}')
    print(f'  未上网条目（保留在档案、不入地图）：{excluded}')


if __name__ == '__main__':
    main()
