#!/usr/bin/env python3
"""微信公众号文章抓取与「新刊速递」人工登记

仅限本机运行：微信的「环境异常」验证墙拦机房/云端 IP（CI 必撞），
本机住宅 IP + 浏览器 UA 通常直过（方法源自 wechat-mp-fetch 技能，2026-08 实测）。

用法：
    python3 tools/fetch_wechat.py <文章URL> [--pub 《刊名》]   # 登记为新刊公告
    python3 tools/fetch_wechat.py --peek <文章URL>             # 只提取字段，不写数据
    python3 tools/fetch_wechat.py --sogou <公众号名或刊名>      # 搜狗微信搜索试点

登记流程：抓取文章 → 提取标题/账号/期数/主题 → 匹配刊物（--pub 可指定）→
查历史去重 → 写入 new_issues.json 当日批次（channel 注明人工登记），
并把发现的公众号账号名/.biz 回写 sources.json 对应通道。
登记后需手动跑 python3 tools/build.py 才会出现在页面上。

微信桥接试点结论（2026-09-06，岛与 biz=Mzg5OTkwODk0Mw== / 松赞Songtsam 实测）：
- 原生直连枚举公众号历史：死路。profile_ext?action=home 返回「验证」空壳页，
  getmsg 接口返回 {"ret":-3,"errmsg":"no session"}——枚举必须有微信会话凭据，
  住宅 IP 也绕不过（与单篇 /s/ 文章页可直过形成对比）；
- 托管桥接：wechat2rss 托管版（bestblogs.dev）为 SPA 需注册；RSSHub 公共实例的
  wechat/mp 路由 503/404；二十次幂（ershicimi.com）不可达——公共免费桥接不可用；
- 唯一可行路线：自建 wewe-rss（微信读书凭据型）——需要本机装 Docker 或源码构建
  （本机有 Node 22 无 Docker）、用户提供微信读书凭据（约月度过期需续期）、
  且轮询只能本机跑（CI 够不到微信也够不到本机服务）；
- 结论：桥接成本（装环境+凭据维护）对应收益（16 种公众号刊物的自动发现），
  由用户权衡；未启用桥接前，微信覆盖依赖人工巡查提醒 + 本工具的单篇登记。

搜狗微信搜索试点结论（2026-09-06，岛与 / 松赞Songtsam 两账号实测）：
- 技术可行：本机 IP 初始可搜、结果块结构可解析（uigs="article_title_N" 带下划线，
  账号在 class="all-time-y2"，日期在 timeConvert('ts')）；
- 限流极凶：短时 4+ 次请求即触发 TLS 级断连（握手超时），冷却时长未知——
  每次运行只允许 1 次搜索，且只能当双周频度的低置信度补充手段；
- 关键词搜索噪音大：两字刊名（岛与）会命中大量含关键词的无关旧文，
  只有账号名足够独特（松赞Songtsam）+ 账号过滤 + 日期过滤才有实用价值。
"""
import argparse
import html
import json
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'tools'))
from fetch_issues import (HISTORY_PATH, SOURCES_PATH, clean_display_theme,  # noqa: E402
                          issue_rank, parse_issue)

UA = ('Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
      'AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15')
FETCH_TIMEOUT = 30
TZ_CN = timezone(timedelta(hours=8))
URL_RE = re.compile(r'^https://mp\.weixin\.qq\.com/s/[A-Za-z0-9_-]{22}$')


def fetch(url):
    """本机抓取一个 URL，返回 (状态码, 文本)。撞验证墙返回 (None, 原因)。"""
    req = urllib.request.Request(url, headers={'User-Agent': UA})
    try:
        with urllib.request.urlopen(req, timeout=FETCH_TIMEOUT) as r:
            data = r.read()
    except urllib.error.HTTPError as e:
        return e.code, ''
    except Exception as e:
        return None, f'请求失败：{type(e).__name__}: {e}'
    text = data.decode('utf-8', errors='ignore')
    if '环境异常' in text:
        return None, '命中微信「环境异常」验证墙（本机 IP 也被限流），放慢后重试'
    return 200, text


class BodyParser(HTMLParser):
    """从 #js_content 提取正文，跟踪 script/style 跳过深度（技能教训：不跟踪会混入数 MB 脚本）。"""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.cap = False
        self.skip = 0
        self.out = []

    def handle_starttag(self, tag, attrs):
        if dict(attrs).get('id') == 'js_content':
            self.cap = True
        if tag in ('script', 'style'):
            self.skip += 1
        if self.cap and self.skip == 0 and tag in ('p', 'br', 'li', 'h1', 'h2', 'h3', 'h4', 'section'):
            self.out.append('\n')

    def handle_endtag(self, tag):
        if tag in ('script', 'style') and self.skip:
            self.skip -= 1

    def handle_data(self, data):
        if self.cap and self.skip == 0:
            t = data.strip()
            if t:
                self.out.append(t)


def extract_article(url):
    """抓取并提取微信文章字段，返回 dict（或抛 RuntimeError）。"""
    status, text = fetch(url)
    if status != 200:
        raise RuntimeError(f'抓取失败（{status}）：{text or url}')
    if len(text) < 5000:
        raise RuntimeError(f'页面过短（{len(text)} 字节），疑似未拿到正文：{url}')

    m = re.search(r"var\s+msg_title\s*=\s*'([^']*)'", text)
    title = m.group(1).strip() if m else ''
    if not title:
        m = re.search(r'property="og:title"\s+content="([^"]*)"', text)
        title = html.unescape(m.group(1)).strip() if m else ''
    if not title:
        raise RuntimeError('标题为空（msg_title 与 og:title 都没取到）')

    nickname = ''
    m = re.search(r'var\s+nickname\s*=\s*htmlDecode\("([^"]*)"\)', text)
    if m:
        nickname = html.unescape(m.group(1)).strip()
    if not nickname:
        m = re.search(r'id="js_name"[^>]*>\s*([^<]+?)\s*<', text)
        nickname = html.unescape(m.group(1)).strip() if m else ''

    biz = ''
    m = re.search(r'var\s+biz\s*=\s*"([^"]+)"', text)
    if m:
        biz = m.group(1)
    else:
        m = re.search(r'__biz=([A-Za-z0-9+/=]{10,}?)&', text)
        biz = m.group(1) if m else ''

    p = BodyParser()
    p.feed(text)
    body = re.sub(r'\n{2,}', '\n', '\n'.join(l for l in ''.join(p.out).split('\n') if l.strip()))

    return {'url': url, 'title': title, 'account': nickname, 'biz': biz, 'body': body}


def parse_fields(article, pub_title=None):
    """从标题（回退正文前 800 字）解析期数与主题，套用展示清洗。"""
    issue, theme = parse_issue(article['title'])
    nm = re.sub(r'（[^）]*）', '', (pub_title or article['title']).replace('《', '').replace('》', ''))
    theme = clean_display_theme(theme, f'《{nm}》')
    if not issue:
        head = article['body'][:800]
        i2, t2 = parse_issue(head)
        if i2:
            issue = i2
            theme = theme or clean_display_theme(t2, f'《{nm}》')
    return issue, theme


def load():
    sources = json.loads(SOURCES_PATH.read_text(encoding='utf-8'))
    history = json.loads(HISTORY_PATH.read_text(encoding='utf-8')) if HISTORY_PATH.exists() \
        else {'version': 1, 'history': {}, 'batches': []}
    return sources, history


def save(history):
    HISTORY_PATH.write_text(json.dumps(history, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')


def resolve_pub(sources, article, pub_flag):
    """确定刊物：--pub 指定优先；否则用账号名/标题匹配 wechat 刊物。返回 (pub, 提示)。"""
    pubs = sources['pubs']
    if pub_flag:
        for p in pubs:
            if p['t'] == pub_flag or p['t'] == f'《{pub_flag}》':
                return p, None
        raise RuntimeError(f'--pub 指定的刊物不在监控清单里：{pub_flag}')
    nm = article['account']
    short = article['title'].replace('《', '').replace('》', '')
    cands = []
    for p in pubs:
        base = re.sub(r'（[^）]*）', '', p['t'].replace('《', '').replace('》', ''))
        if nm and (nm == base or nm in p['t']):
            cands.append(p)
        elif base and base in short:
            cands.append(p)
    if len(cands) == 1:
        return cands[0], None
    if not cands:
        raise RuntimeError(f'无法确定刊物（账号「{nm}」，标题「{article["title"][:40]}」）——请用 --pub 《刊名》指定')
    names = '、'.join(p['t'] for p in cands)
    raise RuntimeError(f'匹配到多个刊物：{names} —— 请用 --pub 《刊名》指定')


def register(article, pub, sources, history):
    """登记进 new_issues.json（批次同刊替换 + 历史去重）。"""
    issue, theme = parse_fields(article, pub['t'])
    if not issue and not theme:
        raise RuntimeError(f'期数与主题都解析不出（标题「{article["title"][:40]}」）——按展示格式整条放弃')
    hist = history.setdefault('history', {})
    seen_issues = {r['issue'] for r in hist.get(pub['t'], []) if r['issue']}
    seen_urls = {r['url'] for r in hist.get(pub['t'], [])}
    if (issue and issue in seen_issues) or article['url'] in seen_urls:
        return None  # 重复
    max_seen = max((issue_rank(x) for x in seen_issues if issue_rank(x) >= 0), default=-1)
    if issue and issue_rank(issue) <= max_seen:
        raise RuntimeError(f'期数 {issue} 不新于已记录的最高期数（{max_seen}），不予登记')
    today = datetime.now(TZ_CN).strftime('%F')
    batch = next((b for b in history['batches'] if b['d'] == today), None)
    if batch is None:
        batch = {'d': today, 'items': []}
        history['batches'].insert(0, batch)
    batch['items'] = [x for x in batch['items'] if x['t'] != pub['t']]
    batch['items'].append({'t': pub['t'], 'shelf': pub['shelf'], 'issue': issue,
                           'theme': theme, 'title': article['title'], 'url': article['url']})
    hist.setdefault(pub['t'], []).append({'issue': issue, 'title': article['title'],
                                          'url': article['url'], 'theme': theme,
                                          'foundAt': today,
                                          'channel': f'人工登记·微信公众号{("「" + article["account"] + "」") if article["account"] else ""}'})
    # 账号档案回写 sources.json
    for c in pub['channels']:
        if c['url'] == article['url']:
            c['account'] = article['account']
            if article['biz']:
                c['biz'] = article['biz']
    if article['account'] and not pub.get('account'):
        pub['account'] = article['account']
    SOURCES_PATH.write_text(json.dumps(sources, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    save(history)
    return {'issue': issue, 'theme': theme}


def sogou_search(query, account=None, days=60):
    """搜狗微信文章搜索（type=2）。返回 (结果列表, 诊断信息)。

    结果条目：{title, account, date, link}。link 是搜狗跳转链（/link?url=…），
    需再解一次跳转才是 mp.weixin 正式 URL——确认登记时建议直接用公众号原文链接。
    注意：搜狗限流极凶，一次运行只发这一个请求。
    """
    q = urllib.parse.quote(query)
    url = f'https://weixin.sogou.com/weixin?type=2&query={q}'
    status, text = fetch(url)
    diag = f'状态 {status}，页面 {len(text)} 字节'
    if status != 200:
        return [], diag + ('；' + text if text and len(text) < 200 else '；疑似触发限流（TLS 断连），冷却后再试')
    if 'antispider' in text.lower() or '请输入验证码' in text:
        return [], diag + '；触发搜狗反爬验证码'
    results = []
    for m in re.finditer(r'<li id="sogou_vr_[^"]*"[^>]*>(.*?)</li>', text, re.S):
        b = m.group(1)
        t = re.search(r'uigs="article_title[^"]*"[^>]*>(.*?)</a>', b, re.S)
        a = re.search(r'class="all-time-y2">([^<]+)<', b)
        d = re.search(r"timeConvert\('(\d+)'\)", b)
        u = re.search(r'href="(/link\?url=[^"]+)"', b)
        if not t:
            continue
        import datetime as dt
        ts = int(d.group(1)) if d else 0
        results.append({'title': html.unescape(re.sub(r'<[^>]+>', '', t.group(1))).strip(),
                        'account': a.group(1).strip() if a else '?',
                        'date': dt.datetime.fromtimestamp(ts).strftime('%F') if ts else '?',
                        'ts': ts,
                        'link': 'https://weixin.sogou.com' + u.group(1).replace('&amp;', '&') if u else '?'})
    if account:
        results = [r for r in results if r['account'] == account]
    cutoff = (datetime.now(TZ_CN) - timedelta(days=days)).timestamp()
    results = [r for r in results if r['ts'] >= cutoff]
    return results, diag


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('urls', nargs='*')
    ap.add_argument('--pub')
    ap.add_argument('--peek', action='store_true')
    ap.add_argument('--sogou', metavar='QUERY')
    ap.add_argument('--account', metavar='账号名', help='搜狗结果的公众号过滤')
    ap.add_argument('--days', type=int, default=60, help='只保留近 N 天结果（默认 60）')
    args = ap.parse_args()

    if args.sogou:
        results, diag = sogou_search(args.sogou, account=args.account, days=args.days)
        print(f'搜狗微信搜索「{args.sogou}」（账号过滤={args.account or "无"}，近 {args.days} 天）— {diag}')
        if not results:
            print('（过滤后无结果——关键词命中均为其他账号的旧文，或已被限流）')
            return 0
        for r in results[:10]:
            print(f"  [{r['date']}] {r['account']}：{r['title'][:48]}")
            print(f"      {r['link'][:100]}")
        print('\n确认后请用登记模式录入公众号原文正式链接（搜狗链接为跳转链）。')
        return 0

    if not args.urls:
        ap.error('需要文章 URL，或 --sogou <查询词>')

    sources, history = load()
    for url in args.urls:
        if not URL_RE.match(url):
            print(f'[跳过] 不是标准的 /s/ 短链（22 位 token）：{url}')
            continue
        try:
            article = extract_article(url)
        except RuntimeError as e:
            print(f'[失败] {e}')
            continue
        if args.peek:
            print(f'[peek] 标题: {article["title"]}')
            print(f'       账号: {article["account"] or "?"}   biz: {article["biz"] or "?"}')
            print(f'       正文: {len(article["body"])} 字')
            issue, theme = parse_fields(article)
            print(f'       解析: 第{issue or "?"}期 · {theme or "(无主题)"}')
            continue
        try:
            pub, hint = resolve_pub(sources, article, args.pub)
            if hint:
                print(hint)
            result = register(article, pub, sources, history)
            if result is None:
                print(f'[重复] {article["title"][:50]}（已在历史中）')
            else:
                issue = f'第{result["issue"]}期' if result['issue'] else ''
                theme = result['theme'] or '(无主题)'
                print(f'[登记] {pub["t"]} {issue} {theme}')
                print(f'       记得跑 python3 tools/build.py 更新页面')
        except RuntimeError as e:
            print(f'[失败] {e}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
