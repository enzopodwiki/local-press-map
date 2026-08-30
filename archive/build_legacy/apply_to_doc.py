import re
p='/Users/enzo/Downloads/在地刊物档案V4.md'
s=open(p,encoding='utf-8').read()

EDITS=[
 ('📌年刊（已出版 3 期）','📌年刊（已出版 8 期）'),                                   # 新华录
 ('📍台北｜📌快闪刊物','📍台北｜🕐创刊 2015 年 9 月｜📌共出版 3 期（已停刊）'),            # Taipei Post
 ('由东园街上的「家吶子台式居酒屋 Ka-la̍h-á」策划执行','由东园街上的「家吶子台式居酒屋」策划执行'), # 東園誌
 ('📍台湾新竹（北台湾）｜🕐季刊（已改版为《巢兼代》）','📍台湾新竹（北台湾）｜🕐季刊（已停刊，已改版为《巢兼代》）'), # 北辰
 ('📌季刊（共出版4期）','📌季刊（共出版4期，已停刊）'),                                 # 什貨生活
 ('📌不定期（共出版6 期，已停刊）','📌不定期（共出版 6 期，已停刊）'),                     # 藍燈號誌
 ('🕐试刊号 2019年6月','🕐创刊 2019年6月'),                                          # 台毒誌
 ('🕐2015年12 月','🕐2015年 12 月'),                                               # 遇见台湾
 ('📌共94期','📌共94期（已停刊）'),                                                  # 谷根千
 ('📍日本约420个有人离岛｜🕐电子版创刊 2010年10月，2012年1月提出纸质版','📍约420个离岛｜🕐创刊 2010年10月，2012年1月推出纸质版'), # 離島経済新聞
 ('🕐2021年出版','🕐2021 年'),                                                      # 在基隆
 ('📍北京白塔寺胡同｜🕐创刊 2016年｜📌共 30 期','📍北京白塔寺胡同｜🕐创刊 2016年｜📌不定期，共出版 30 期'), # LAWAAI
]
for a,b in EDITS:
    assert s.count(a)==1, a
    s=s.replace(a,b)

NO_LIVE=['《Taipei Post》','《Smaaaaa,han（原來是司馬限啊）～部落誌》','《遇见台湾》（大陆出版）','《北埔》系列','《LAWAAI·事儿多》']
def key(block):
    title, body = block
    meta=next((l for l in body if l.startswith('📍')),'')
    g=1 if '已停刊' in meta else (2 if (re.search(r'单册|一套', meta) or title in NO_LIVE) else 0)
    mm=re.search(r'(19|20)\d{2}', meta)
    return (g, int(mm.group(0)) if mm else 9999)

lines=s.split('\n')
out=[]; i=0
while i < len(lines):
    l=lines[i]
    if l.startswith('### ') and '社区报' not in l:
        out.append(l); i+=1
        pre=[]; blocks=[]; cur=None; curbody=[]
        while i<len(lines) and not lines[i].startswith(('### ','## ')):
            t=lines[i]
            if t.startswith('#### '):
                if cur is not None: blocks.append((cur,curbody))
                cur=t[5:].strip(); curbody=[]
            elif cur is None:
                pre.append(t)
            else:
                curbody.append(t)
            i+=1
        if cur is not None: blocks.append((cur,curbody))
        blocks.sort(key=key)
        out.extend(pre)
        for h,bl in blocks:
            out.append('#### '+h); out.extend(bl)
        continue
    out.append(l); i+=1

open(p,'w',encoding='utf-8').write('\n'.join(out))
print('doc updated; sections reordered')
