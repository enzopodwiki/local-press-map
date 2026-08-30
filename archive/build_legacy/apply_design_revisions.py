#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""根据 ~/Downloads/网页设计修改意见.md 对成品 HTML 做外科手术式修改。
所有替换都带 assert，全部通过才写文件。"""
import re, shutil, os

BASE = '/Users/enzo/.qwenworkcn/workspace/msffm7lk4k1le8kk'
F = os.path.join(BASE, 'outputs', '在地刊物地图书架.html')
shutil.copy2(F, os.path.join(BASE, 'build', '在地刊物地图书架.改版前备份.html'))

s = open(F, encoding='utf-8').read()
orig = s

def rep(old, new, n=1, label=''):
    global s
    c = s.count(old)
    assert c == n, f'[{label}] 期望 {n} 处，实际 {c} 处'
    s = s.replace(old, new)
    print(f'ok: {label}')

# ---------- 1. :root 色板：泰金加深 + 新增靛蓝/竹青 ----------
rep("""    --gold:#E39A1D;
    --purple:#6C5EB5;""",
"""    --gold:#C9821A;
    --indigo:#2F5488;
    --bamboo:#46795F;
    --purple:#6C5EB5;""", 1, 'root 色板')

# ---------- 2. body 四角渐变 → 引用 --ambient-acc ----------
rep("""    background:
      radial-gradient(1100px 500px at 8% -5%, rgba(217,74,43,.07), transparent 60%),
      radial-gradient(900px 480px at 96% 12%, rgba(22,104,176,.07), transparent 60%),
      radial-gradient(1000px 560px at 50% 108%, rgba(14,138,95,.08), transparent 62%),
      var(--paper);""",
"""    --ambient-acc:#D94A2B;
    background:
      radial-gradient(1100px 500px at 8% -5%, color-mix(in srgb, var(--ambient-acc) 9%, transparent), transparent 60%),
      radial-gradient(900px 480px at 96% 12%, color-mix(in srgb, var(--ambient-acc) 6%, transparent), transparent 60%),
      radial-gradient(1000px 560px at 50% 108%, color-mix(in srgb, var(--ambient-acc) 10%, transparent), transparent 62%),
      var(--paper);""", 1, 'body 环境渐变')

# ambient 层海浪默认色：蓝 → 红（跟随首屏大陆分区；切页签时 JS 会重写）
rep('stroke="%231668B0" stroke-opacity=".06"',
    'stroke="%23D94A2B" stroke-opacity=".06"', 1, 'ambient 海浪默认色')

# ---------- 3. 页头：装饰行李签降权 ----------
rep("""  .tags-row{display:flex;gap:14px;flex-wrap:wrap;margin-top:26px}
  .ltag{
    display:flex;align-items:center;gap:9px;border:2px solid var(--ink);background:var(--paper);
    padding:7px 14px 7px 8px;box-shadow:3px 3px 0 rgba(38,34,28,.14);font-weight:700;font-size:13px;
    transform:rotate(var(--r,0deg));
  }
  .ltag i{
    width:30px;height:30px;display:flex;align-items:center;justify-content:center;font-style:normal;
    background:var(--c);color:#fff;font-size:15px;font-weight:900;border:2px solid var(--ink);
  }""",
"""  .tags-row{display:flex;gap:12px;flex-wrap:wrap;margin-top:20px}
  .ltag{
    display:inline-flex;align-items:center;gap:6px;font-weight:700;font-size:11.5px;letter-spacing:.02em;opacity:.85;
  }
  .ltag i{
    width:19px;height:19px;display:flex;align-items:center;justify-content:center;font-style:normal;
    background:var(--c);color:#fff;font-size:10.5px;font-weight:900;border-radius:3px;
  }""", 1, '行李签降权')

# ---------- 4. 阅览须知框 margin-left:auto ----------
rep('font-size:12.5px;line-height:1.9;max-width:300px;\n  }\n  .stamp-box b{font-size:15px}',
    'font-size:12.5px;line-height:1.9;max-width:300px;margin-left:auto;\n  }\n  .stamp-box b{font-size:15px}',
    1, '阅览须知贴右')

# ---------- 5. 统计条两端对齐 ----------
rep('  .chip.alt{background:var(--ink);color:var(--paper)}',
    '  .chip.alt{background:var(--ink);color:var(--paper)}\n  .stats-line .chip:last-child{margin-left:auto}',
    1, '统计条两端对齐')

# ---------- 6. 流动书柜按钮居中 ----------
rep('.roam-row{display:flex;gap:12px;flex-wrap:wrap;margin-top:16px}',
    '.roam-row{display:flex;gap:12px;flex-wrap:wrap;margin-top:16px;justify-content:center}',
    1, 'roam 按钮居中')

# ---------- 7. 纵向地图：收窄 + 侧栏资讯 ----------
rep("""  .map-note{font-size:11.5px;opacity:.6;padding:8px 18px 14px;letter-spacing:.03em;position:relative;z-index:2}""",
"""  .map-note{font-size:11.5px;opacity:.6;padding:8px 18px 14px;letter-spacing:.03em;position:relative;z-index:2}
  /* 纵向狭长地形：地图收窄居中，左侧补资讯栏，避免大片留白 */
  .side-stack{display:none}
  .panel.portrait .side-stack{display:flex;flex-direction:column;gap:14px;position:absolute;left:22px;top:50%;transform:translateY(-50%);z-index:4;width:202px}
  .side-block{border:2px solid var(--ink);background:var(--paper);box-shadow:4px 4px 0 rgba(38,34,28,.13);padding:12px 14px;transform:rotate(-.5deg)}
  .side-block b{display:block;font-size:12px;font-weight:900;letter-spacing:.16em;margin-bottom:6px}
  .side-block p{font-size:11.5px;line-height:1.85;opacity:.85}
  .panel.portrait svg.map{margin:0 auto}
  .panel.portrait .wm{width:44%}
  .panel[data-map="japan"] svg.map{max-width:620px}
  .panel[data-map="thailand"] svg.map{max-width:470px}
  .panel[data-map="sgmy"] svg.map{max-width:600px}
  @media (max-width:1080px){
    .panel.portrait .side-stack{display:none}
    .panel.portrait svg.map{max-width:none}
    .panel.portrait .wm{width:62%}
  }""", 1, 'portrait 布局 CSS')

# ---------- 8. 分区主题色与底纹 ----------
rep('<section class="panel" data-map="taiwan" style="--acc:var(--green)">',
    '<section class="panel" data-map="taiwan" style="--acc:var(--bamboo)">', 1, '台湾→竹青')
rep('<section class="panel" data-map="japan" style="--acc:var(--magenta)">',
    '<section class="panel portrait" data-map="japan" style="--acc:var(--indigo)">', 1, '日本→靛蓝+portrait')
rep('<section class="panel" data-map="thailand" style="--acc:var(--gold)">',
    '<section class="panel portrait" data-map="thailand" style="--acc:var(--gold)">', 1, '泰国 portrait')
rep('<section class="panel" data-map="sgmy" style="--acc:var(--blue)">',
    '<section class="panel portrait" data-map="sgmy" style="--acc:var(--blue)">', 1, '新马 portrait')

# 台湾分区色块
rep('fill="#0E8A5F"', 'fill="#46795F"', 4, '台湾 zone 填色')

# 底纹描边色跟随新主题色
rep('stroke="%23D6497F" stroke-opacity=".09"', 'stroke="%232F5488" stroke-opacity=".09"', 1, '日本底纹色')
rep('stroke="%23E39A1D" stroke-opacity=".09"', 'stroke="%23C9821A" stroke-opacity=".09"', 1, '泰国底纹描边')
rep('fill="%23E39A1D" fill-opacity=".08"', 'fill="%23C9821A" fill-opacity=".08"', 1, '泰国底纹填充')
rep('stroke="%230E8A5F" stroke-opacity=".12"', 'stroke="%2346795F" stroke-opacity=".12"', 1, '台湾底纹色')

# 新马底纹：同心圆点阵 → 娘惹瓷砖（中心四瓣花 + 角部连续圆）
rep("""  .panel[data-map="sgmy"] .map-wrap{background:
    url('data:image/svg+xml;utf8,<svg xmlns="http://www.w3.org/2000/svg" width="72" height="72"><g fill="none" stroke="%231668B0" stroke-opacity=".17" stroke-width="2"><circle cx="36" cy="36" r="4"/><circle cx="36" cy="22" r="7"/><circle cx="36" cy="50" r="7"/><circle cx="22" cy="36" r="7"/><circle cx="50" cy="36" r="7"/></g><g fill="%231668B0" fill-opacity=".12"><circle cx="6" cy="6" r="2"/><circle cx="66" cy="66" r="2"/></g></svg>');}""",
"""  .panel[data-map="sgmy"] .map-wrap{background:
    url('data:image/svg+xml;utf8,<svg xmlns="http://www.w3.org/2000/svg" width="96" height="96"><g fill="none" stroke="%231668B0" stroke-opacity=".16" stroke-width="1.8"><path d="M48 26 C55 36 55 60 48 70 C41 60 41 36 48 26 Z"/><path d="M26 48 C36 41 60 41 70 48 C60 55 36 55 26 48 Z"/><circle cx="48" cy="48" r="3.4"/><circle cx="0" cy="0" r="7"/><circle cx="96" cy="0" r="7"/><circle cx="0" cy="96" r="7"/><circle cx="96" cy="96" r="7"/></g><g fill="%231668B0" fill-opacity=".14"><circle cx="48" cy="0" r="1.6"/><circle cx="48" cy="96" r="1.6"/><circle cx="0" cy="48" r="1.6"/><circle cx="96" cy="48" r="1.6"/></g></svg>');}""",
    1, '新马娘惹瓷砖纹')

# ---------- 9. 三个纵向分区的侧栏内容 ----------
rep('      <div class="map-band band-sashiko"></div>',
"""      <div class="map-band band-sashiko"></div>
      <aside class="side-stack">
        <div class="side-block"><b>列島出版觀察</b><p>地方刊物的成熟样本——从东京下町到东北田野，一地一册，与地方共创。</p></div>
        <div class="side-block"><b>書櫃速覽</b><p><span data-count="japan">—</span> 种刊物 · <span data-shelves="japan">—</span> 个书柜<br>全国流动刊物 4 种，见下方「流动书柜」</p></div>
      </aside>""", 1, '日本侧栏')

rep('      <div class="map-band band-thai"></div>',
"""      <div class="map-band band-thai"></div>
      <aside class="side-stack">
        <div class="side-block"><b>泰蘭出版觀察</b><p>清迈的老牌英文城志，与曼谷的创意文化旗舰。</p></div>
        <div class="side-block"><b>書櫃速覽</b><p><span data-count="thailand">—</span> 种刊物 · <span data-shelves="thailand">—</span> 个书柜<br>档案暂存 2 种，均已完整收录</p></div>
      </aside>""", 1, '泰国侧栏')

rep('      <div class="map-band band-songket"></div>',
"""      <div class="map-band band-songket"></div>
      <aside class="side-stack">
        <div class="side-block"><b>南洋出版觀察</b><p>南洋华人社区的在地声音——槟城书柜含中英两种视角。</p></div>
        <div class="side-block"><b>書櫃速覽</b><p><span data-count="sgmy">—</span> 种刊物 · <span data-shelves="sgmy">—</span> 个书柜<br>东马（沙巴、砂拉越）暂无收录</p></div>
      </aside>""", 1, '新马侧栏')

# 新马补竖排题词与纹样图例（其余四区都有）
rep('新加坡</text></g></svg></div>',
    '新加坡</text></g></svg><span class="motto">在南洋寫字</span><span class="legend">纹样 · 娘惹瓷砖</span></div>',
    1, '新马 motto/legend')

# ---------- 10. JS：环境色切换 + 书柜数统计 + 调色板 ----------
rep("const PALETTE = ['#D94A2B','#1668B0','#D6497F','#0E8A5F','#E39A1D','#6C5EB5'];",
    "const PALETTE = ['#D94A2B','#1668B0','#2F5488','#46795F','#C9821A','#6C5EB5'];",
    1, 'PALETTE 更新')

rep("""  {id:'thailand',name:'泰国',                 no:'MAP 05'}
];""",
"""  {id:'thailand',name:'泰国',                 no:'MAP 05'}
];

/* ================= 环境氛围色：跟随当前分区 ================= */
const AMBIENT = {china:'#D94A2B', taiwan:'#46795F', japan:'#2F5488', sgmy:'#1668B0', thailand:'#C9821A'};
function setAmbient(id){
  const hex = AMBIENT[id] || '#D94A2B';
  document.body.style.setProperty('--ambient-acc', hex);
  const e = hex.replace('#','%23');
  document.querySelector('.ambient').style.backgroundImage =
    `url('data:image/svg+xml;utf8,<svg xmlns="http://www.w3.org/2000/svg" width="260" height="90"><g fill="none" stroke="%2326221C" stroke-opacity=".05" stroke-width="2"><path d="M0 70 L30 42 L52 62 L78 30 L104 60 L128 44 L150 66 L178 36 L204 62 L232 46 L260 70"/><path d="M0 84 L40 60 L70 78 L110 52 L150 76 L190 58 L230 78 L260 62"/></g></svg>'),url('data:image/svg+xml;utf8,<svg xmlns="http://www.w3.org/2000/svg" width="120" height="34"><g fill="none" stroke="${e}" stroke-opacity=".07" stroke-width="2"><path d="M0 24 Q15 12 30 24 T60 24 T90 24 T120 24"/><path d="M0 32 Q15 20 30 32 T60 32 T90 32 T120 32"/></g></svg>')`;
}""", 1, 'AMBIENT + setAmbient')

rep("""function switchMap(id,btn){
  document.querySelectorAll('.tab').forEach(t=>t.classList.toggle('active',t===btn));""",
"""function switchMap(id,btn){
  setAmbient(id);
  document.querySelectorAll('.tab').forEach(t=>t.classList.toggle('active',t===btn));""",
  1, 'switchMap 调 setAmbient')

rep("""document.querySelectorAll('[data-count]').forEach(el=>{
  const m = el.dataset.count;
  el.textContent = DATA.filter(d=>d.map===m).reduce((n,d)=>n+d.pubs.length,0);
});""",
"""document.querySelectorAll('[data-count]').forEach(el=>{
  const m = el.dataset.count;
  el.textContent = DATA.filter(d=>d.map===m).reduce((n,d)=>n+d.pubs.length,0);
});
document.querySelectorAll('[data-shelves]').forEach(el=>{
  const m = el.dataset.shelves;
  el.textContent = DATA.filter(d=>d.map===m).length;
});""", 1, 'data-shelves 统计')

assert s != orig
open(F, 'w', encoding='utf-8').write(s)
print('写入完成:', len(s), 'chars')
