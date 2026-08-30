#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""第二轮微调：
1. 大陆/台湾补「出版观察+书柜速览」侧栏（has-side 类）
2. 侧栏标题转简体；泰蘭出版觀察→暹罗出版观察
3. 删除五张地图左下角的 ※ 图示文字（map-note）
4. 左右切换器下调（bottom:48→12），portrait 地图底部预留 74px 空带避免遮陆地
"""
import os

BASE = '/Users/enzo/.qwenworkcn/workspace/msffm7lk4k1le8kk'
F = os.path.join(BASE, 'outputs', '在地刊物地图书架.html')
s = open(F, encoding='utf-8').read()
orig = s

def rep(old, new, n=1, label=''):
    global s
    c = s.count(old)
    assert c == n, f'[{label}] 期望 {n} 处，实际 {c} 处'
    s = s.replace(old, new)
    print(f'ok: {label}')

# ---------- 1. 五个分区都挂 has-side ----------
rep('<section class="panel" data-map="china" style="--acc:var(--red)">',
    '<section class="panel has-side" data-map="china" style="--acc:var(--red)">', 1, 'china has-side')
rep('<section class="panel" data-map="taiwan" style="--acc:var(--bamboo)">',
    '<section class="panel has-side" data-map="taiwan" style="--acc:var(--bamboo)">', 1, 'taiwan has-side')
rep('<section class="panel portrait" data-map="japan" style="--acc:var(--indigo)">',
    '<section class="panel portrait has-side" data-map="japan" style="--acc:var(--indigo)">', 1, 'japan has-side')
rep('<section class="panel portrait" data-map="thailand" style="--acc:var(--gold)">',
    '<section class="panel portrait has-side" data-map="thailand" style="--acc:var(--gold)">', 1, 'thailand has-side')
rep('<section class="panel portrait" data-map="sgmy" style="--acc:var(--blue)">',
    '<section class="panel portrait has-side" data-map="sgmy" style="--acc:var(--blue)">', 1, 'sgmy has-side')

# ---------- 2. 大陆/台湾侧栏内容 ----------
rep('      <div class="map-band band-hui"></div>',
"""      <div class="map-band band-hui"></div>
      <aside class="side-stack">
        <div class="side-block"><b>神州出版观察</b><p>从北京胡同到雪域高原，刊物生长在街巷、山谷与古城之间。</p></div>
        <div class="side-block"><b>书柜速览</b><p><span data-count="china">—</span> 种刊物 · <span data-shelves="china">—</span> 个书柜<br>全国流动刊物 5 种，见下方「流动书柜」</p></div>
      </aside>""", 1, 'china 侧栏')
rep('      <div class="map-band band-hakka"></div>',
"""      <div class="map-band band-hakka"></div>
      <aside class="side-stack">
        <div class="side-block"><b>岛屿出版观察</b><p>街仔与离岛的书写——按北、中、南、东、离岛五大分区及全台类收录。</p></div>
        <div class="side-block"><b>书柜速览</b><p><span data-count="taiwan">—</span> 种刊物 · <span data-shelves="taiwan">—</span> 个书柜<br>跨分区全台性刊物见下方「全台性刊物书柜」</p></div>
      </aside>""", 1, 'taiwan 侧栏')

# ---------- 3. 侧栏标题简体化 ----------
rep('<b>列島出版觀察</b>', '<b>列岛出版观察</b>', 1, '日本标题简体')
rep('<b>泰蘭出版觀察</b>', '<b>暹罗出版观察</b>', 1, '泰国标题→暹罗出版观察')
rep('<b>南洋出版觀察</b>', '<b>南洋出版观察</b>', 1, '新马标题简体')
rep('<b>書櫃速覽</b>', '<b>书柜速览</b>', 3, '书柜速览简体')

# ---------- 4. 删除 map-note 图示文字 ----------
rep('      <div class="map-note">※ 图钉上的数字 = 该地区刊物数量 · 悬停查看地名 · 《碧山》《地道风物》等跨地域刊物收入下方「流动书柜」</div>\n', '', 1, '删 china map-note')
rep('      <div class="map-note">※ 点击色块分区开书柜 · 离岛各点均通「离岛书柜」 · 跨分区的全台性刊物见下方图章</div>\n', '', 1, '删 taiwan map-note')
rep('      <div class="map-note">※ 《d design travel》《TURNS》等一行一册、走遍全国的刊物收入下方「流动书柜」</div>\n', '', 1, '删 japan map-note')
rep('      <div class="map-note">※ 档案暂存泰国刊物 2 种，均已收录</div>\n', '', 1, '删 thailand map-note')
rep('      <div class="map-note">※ 槟城书柜含中英两种视角的刊物各一种 · 东马（沙巴、砂拉越）地方刊物暂无收录</div>\n', '', 1, '删 sgmy map-note')

# ---------- 5. CSS：side-stack 选择器改 has-side；大陆侧栏置左下 ----------
rep('.panel.portrait .side-stack{display:flex;', '.panel.has-side .side-stack{display:flex;', 1, 'side-stack 选择器')
rep('.panel.portrait .side-stack{display:none}', '.panel.has-side .side-stack{display:none}', 1, 'media 选择器')
rep("""  .panel.portrait svg.map{margin:0 auto}
  .panel.portrait .wm{width:44%}""",
"""  .panel.portrait svg.map{margin:0 auto}
  .panel.portrait .wm{width:44%}
  .panel.portrait .map-wrap{padding-bottom:74px}
  .panel[data-map="china"] .side-stack{top:auto;bottom:20px;transform:none}""", 1, 'portrait 底部空带 + 大陆侧栏左下')

# ---------- 6. 切换器下调 ----------
rep('.map-nav{position:absolute;bottom:48px;', '.map-nav{position:absolute;bottom:12px;', 1, 'map-nav 下调')

# ---------- 7. 移除 .map-note CSS ----------
rep('  .map-note{font-size:11.5px;opacity:.6;padding:8px 18px 14px;letter-spacing:.03em;position:relative;z-index:2}\n', '', 1, '删 map-note CSS')

assert s != orig
open(F, 'w', encoding='utf-8').write(s)
print('写入完成:', len(s), 'chars')
