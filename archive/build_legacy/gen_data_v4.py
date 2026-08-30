import json, re

doc = open('/Users/enzo/Downloads/在地刊物档案V4.md', encoding='utf-8').read().split('\n')
blocks = {}; cur = None
for line in doc:
    if line.startswith('#### '):
        cur = line[5:].strip(); blocks[cur] = []
    elif cur is not None:
        if line.startswith(('### ', '## ', '---')): cur = None
        else: blocks[cur].append(line)

parsed = {}
for title, lines in blocks.items():
    meta=''; intro=[]; links=[]
    for ln in lines:
        s=ln.strip()
        if not s: continue
        if s.startswith('📍'): meta=s
        elif s.startswith('信源'):
            links=[[m[0].strip(),m[1].strip()] for m in re.findall(r'\[([^\]]+)\]\(([^)]+)\)',s)]
        else: intro.append(s)
    p=y=f=''
    for part in meta.split('｜'):
        part=part.strip()
        if part.startswith('📍'): p=part[1:].strip()
        elif part.startswith('🕐'): y=part[1:].strip()
        elif part.startswith('📌'): f=part[1:].strip()
        elif part and not f: f=part
    st='已停刊' if '已停刊' in meta else ''
    f=f.replace('（已停刊）','').strip()
    parsed[title]={'t':title,'p':p,'y':y,'f':f,'s':st,'i':''.join(intro),'l':links,'cover':''}

SELECT = {
'《Timeout 消费导刊》':'beijing','《LAWAAI·事儿多》':'beijing',
'《壹页郑州》':'zhengzhou',
'《新华录》':'shanghai','《古北古北》':'shanghai',
'《不熟》（原 SOLO）':'nanjing',
'《岛与》':'zhejiang','《a mayzine》':'zhejiang','《恰天光》':'zhejiang','《一个，人的村庄……》':'zhejiang','《青山青山村》':'zhejiang',
'《黟县百工》':'yixian',
'《homeland家园》':'fujian','《平话》':'fujian','《海峡旅游》':'fujian','《搜街 SOGUIDE》':'fujian','《城市壹本 City Book》':'fujian',
'《优良 better》':'wuhan','《大武汉》':'wuhan',
'《晨报周刊》':'changsha','《星球雷达：我们与山野的距离》':'changsha',
'《深活集》':'guangdong','《走神》':'guangdong','《阔目 Monsoon Fish》（前身《回南天》）':'guangdong',
'《最重庆》':'chongqing',
'《可以》':'chengdu','《@成都》城市观察书系':'chengdu',
'《Local本地》':'xian',
'《山谷》':'shaxi',
'《西藏人文地理》':'lasa','《PHORPA》':'lasa',
'《碧山》':'roam-cn','《百工》':'roam-cn','《地道风物》':'roam-cn','《风物中国志》':'roam-cn','《柴米多生产生活指南》':'roam-cn',
'《號外》':'hk','《就係香港 Being Hong Kong》':'hk','《种植香港》':'hk','《ISLANDERS島民》':'hk','CACHe 系列刊物':'hk','《香港職人》':'hk','《香港老舖記錄冊》':'hk','《聽說長洲》':'hk',
'《新生代》':'mo','《城與書》':'mo','《咁澳門點？》':'mo',
'《台味誌》':'tw-all','《旅人食通信》':'tw-all','《米通信》':'tw-all','《五花鹽 BaconPress》':'tw-all','《薰風》':'tw-all','《鄉間小路》':'tw-all','《新活水 Fountain》':'tw-all','《誌村鑑》':'tw-all','《台毒誌 to̍k magazine》':'tw-all','《靛花》':'tw-all','《地味手帖》':'tw-all','《秋刀魚》':'tw-all','《本地 The Place》':'tw-all','《遇见台湾》（大陆出版）':'tw-all','《藍鯨》':'tw-all','《我村》OUR VILLAGES':'tw-all','《台灣光華雜誌》（Taiwan Panorama）':'tw-all','《日日好日》':'tw-all',
'《雞籠霧雨》':'tw-north','《海想知道》':'tw-north','《在基隆：城、海、山與未來》':'tw-north','《Taipei Post》':'tw-north','《稻相報 TÀU SIO PO》':'tw-north','《東園誌》':'tw-north','在地Real Local：北投・天母':'tw-north','《台北早餐大王》':'tw-north','《台北畫刊》':'tw-north','《返腳》':'tw-north','《新莊騷》':'tw-north','《新莊報導》':'tw-north','《淡淡》':'tw-north','《甘樂誌》':'tw-north','《Mingalar Par 緬甸街》':'tw-north','《SHOCK 三峽客》':'tw-north','《小小生活》':'tw-north','《夭夭》':'tw-north','《龜山不是島》':'tw-north','《野菱報》':'tw-north','《文化桃園》':'tw-north','《新竹風》':'tw-north','《貢丸湯》':'tw-north','《逐步東行》':'tw-north','《風起Uprisings》':'tw-north','《d設計之旅 台灣·新竹》':'tw-north','《新竹生活》':'tw-north','《北辰》':'tw-north','《巢兼代》':'tw-north','《北埔》系列':'tw-north',
'《尋庄》':'tw-central','《掀海風》':'tw-central','《Smaaaaa,han（原來是司馬限啊）～部落誌》':'tw-central','《山城週刊》':'tw-central','《暖太陽》（Day in the Sun）':'tw-central','《風格線上》（Solmag）':'tw-central','《社群別冊》':'tw-central','《炯話郎》':'tw-central','《員林紀事》':'tw-central','《今秋誌》':'tw-central','《雲林食通信》':'tw-central','《中台灣食通信》':'tw-central','《籃城很有事》':'tw-central',
'《南》':'tw-south','《慢漫刊》':'tw-south','《正興聞》':'tw-south','《透南風》':'tw-south','《路克米 Look At Me》':'tw-south','《美印臺南》':'tw-south','《大雄誌 megao》':'tw-south','《什貨生活》':'tw-south','《鹽埕微醺》':'tw-south','《野上野下》':'tw-south','《型農本色》':'tw-south','《藍燈號誌》':'tw-south','《AMAZING PINGTUNG》':'tw-south','《屏東本事》':'tw-south','《行南》':'tw-south',
'《about 關於地方：南方澳誌》':'tw-east',"《O'rip 生活旅人》":'tw-east','《拾紙》':'tw-east','《太布河里 TRUKU BUNUN RIVER VILLAGE》':'tw-east','《東透可 Taitungtalk》':'tw-east','《THE 17 LAB 地方誌》':'tw-east','《台東土黏黏》':'tw-east','《島嶼綠》':'tw-east','《952 VAZAY TAMO》':'tw-east','《東台灣食通信》':'tw-east',
'《金門文藝》':'tw-islands','《Salty. Dongyin Pictorial Plus+》（東引畫刊）':'tw-islands','《大角誌》（Tāi-kak）':'tw-islands',
'《谷中・根津・千駄木》（谷根千）':'tokyo','《TOmagazine》':'tokyo',
'《自遊人》':'niigata',
'《東北食べる通信》（东北食通信）':'tohoku',
'《本と温泉》（书与温泉）':'hyogo',
'《せとうちスタイル》（濑户内风格）':'setouchi',
'《雲のうえ》（云上）':'kyushu',
'《d design travel》':'roam-jp','《TURNS》':'roam-jp','《離島経済新聞》（ritokei）':'roam-jp','《PAPERSKY》':'roam-jp',
'《Citylife Chiang Mai》（英文）':'chiangmai',
'《a day》（泰文）':'bangkok',
'《城视报 Penang City Eye》':'penang','《Penang Monthly》（英文）':'penang',
"《雪州誌 The Selangor's》":'selangor',
'《麻河时光 Muar River Times》':'muar',
'《Mynah Magazine》（英文）':'singapore',
}
# 直引号变体兼容
if '《雪州誌 The Selangor’s》' not in SELECT: pass
for k in list(blocks):
    pass

REGIONS = [
('beijing','北京','china',None),('zhengzhou','郑州','china',None),('shanghai','上海','china',None),
('nanjing','南京','china',None),('zhejiang','浙江','china',None),('yixian','黟县','china',None),
('fujian','福建','china',None),('wuhan','武汉','china',None),('changsha','长沙','china',None),
('guangdong','广东','china',None),('chongqing','重庆','china',None),('chengdu','成都','china',None),
('xian','西安','china',None),('shaxi','沙溪','china',None),('lasa','西藏','china',None),
('hk','香港','china',None),('mo','澳门','china',None),
('roam-cn','流动书柜 · 全国刊物','china','跨地域出版、难以钉在单一坐标的刊物'),
('tw-all','台湾 · 全台','taiwan','跨分区发行的全台性刊物'),
('tw-north','台湾 · 北部','taiwan',None),('tw-central','台湾 · 中部','taiwan',None),
('tw-south','台湾 · 南部','taiwan',None),('tw-east','台湾 · 东部','taiwan',None),
('tw-islands','台湾 · 离岛','taiwan',None),
('tohoku','东北','japan',None),('niigata','新潟','japan',None),('tokyo','东京','japan',None),
('hyogo','兵库 · 城崎','japan',None),('setouchi','濑户内','japan',None),('kyushu','北九州','japan',None),
('roam-jp','流动书柜 · 全国刊物','japan','一行一册、走遍列岛的刊物'),
('chiangmai','清迈','thailand',None),('bangkok','曼谷','thailand',None),
('penang','槟城','sgmy',None),('selangor','雪兰莪','sgmy',None),('muar','麻河流域','sgmy',None),('singapore','新加坡','sgmy',None),
]

missing=[t for t in SELECT if t not in parsed]
extra=[t for t in parsed if t not in SELECT and t!='香港社区报']
DATA=[]
for rid,label,mp,sub in REGIONS:
    pubs=[parsed[t] for t in SELECT if SELECT[t]==rid]
    obj={'id':rid,'region':label,'map':mp,'pubs':pubs}
    if sub: obj['sub']=sub
    if rid in ('roam-cn','roam-jp','tw-all'): obj['roam']=True
    DATA.append(obj)
tot=sum(len(r['pubs']) for r in DATA)
js='const DATA = '+json.dumps(DATA,ensure_ascii=False,indent=1)+';'
open('/Users/enzo/.qwenworkcn/workspace/msffm7lk4k1le8kk/build/data_v4.js','w',encoding='utf-8').write(js)
print('total:',tot,'missing:',missing,'extra:',extra)
print('per-map:',{m:sum(len(r["pubs"]) for r in DATA if r["map"]==m) for m in ['china','taiwan','japan','thailand','sgmy']})
