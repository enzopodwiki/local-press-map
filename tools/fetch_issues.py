#!/usr/bin/env python3
"""「新刊速递」抓取器

按 data/sources.json 的监控清单逐刊抓取信源，提取新刊发布的消息（期数 + 当期主题），
与 data/new_issues.json 里的历史记录去重后合并，把新发现打印成 Markdown 摘要。

- 只抓 method 为 rss / official / platform 的刊物；wechat（公众号桥接）与 social
  （登录墙）暂不自动抓，等桥接配置后再接入。
- 通道级容错：单条通道失败只记警告，不影响整体退出码（CI 里警告会出现在 PR 描述里）。
- 新发现的判定：同一刊物的 (期数|URL) 未出现在历史中。信源公告不会过期，
  漏抓的会在下次运行自然补上。

用法：
    python3 tools/fetch_issues.py                 # 全量抓取，输出 Markdown 摘要
    python3 tools/fetch_issues.py --pubs 碧山,走神  # 只抓指定刊物（标题含匹配即可）
"""
import concurrent.futures
import html
import json
import re
import ssl
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urljoin, urlparse

ROOT = Path(__file__).resolve().parent.parent
SOURCES_PATH = ROOT / 'data' / 'sources.json'
HISTORY_PATH = ROOT / 'data' / 'new_issues.json'

UA = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 '
                    '(KHTML, like Gecko) Chrome/124.0 Safari/537.36',
      'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
      'Accept-Language': 'zh-CN,zh;q=0.9,ja;q=0.8,en;q=0.7'}
FETCH_TIMEOUT = 15
FETCH_WORKERS = 6
MAX_ITEMS_PER_CHANNEL = 5

TZ_CN = timezone(timedelta(hours=8))
CTX = ssl.create_default_context()
CTX.check_hostname = False
CTX.verify_mode = ssl.CERT_NONE

# 期数模式：按优先级排列，先命中先得（Vol 不设词边界：中文后跟 vol40 同样可解析）
ISSUE_PATTERNS = [
    (re.compile(r'第\s*([0-9０-９]{1,4})\s*[期輯辑号]'), 'issue'),
    (re.compile(r'[Vv]ol\.?\s*([0-9]{1,4})'), 'vol'),
    (re.compile(r'\b[Ii]ssue\s*([0-9]{1,4})\b'), 'issue'),
    (re.compile(r'\b[Nn]o\.?\s*([0-9]{1,4})\b'), 'no'),
    (re.compile(r'([0-9]{4})\s*年\s*([0-9]{1,2})\s*月号'), 'ym'),
]
# 明确的「新刊/出刊」公告词：RSS/HTML 候选里，没有期数时必须命中其中之一才保留
ANNOUNCE_RE = re.compile(r'新刊|出刊|創刊|创刊|復刊|复刊|発売|發售|发售|上市|發行|发行|好評発売中')
# 主题词：含这些词的链接才进入候选扫描（HTML 扫描的第一道粗筛）
KEYWORDS = ('出刊', '新刊', '上市', '発売', '發售', '发售', '出版', '发行', '發行',
            'vol.', 'issue', '第', '号外', '特集', '專題', '专题', '月刊', '季刊')


def fullwidth_to_ascii(s):
    return s.translate(str.maketrans('０１２３４５６７８９', '0123456789'))


def parse_issue(text):
    """从标题里提取 (期数标识, 去掉期数后的主题)。找不到期数返回 (None, 原文)。"""
    t = fullwidth_to_ascii(text)
    for pat, kind in ISSUE_PATTERNS:
        m = pat.search(t)
        if not m:
            continue
        if kind == 'ym':
            issue = f"{m.group(1)}年{m.group(2)}月号"
        else:
            issue = m.group(1)
        theme = (t[:m.start()] + t[m.end():]).strip(' 　-–—｜|:：（）()《》「」·，,。.~')
        return issue, theme or text.strip()
    return None, text.strip()


def fetch(url):
    """GET 一个 URL，返回 (最终URL, 状态码, bytes)。失败返回 (url, None, b'')。"""
    req = urllib.request.Request(url, headers=UA)
    try:
        with urllib.request.urlopen(req, timeout=FETCH_TIMEOUT, context=CTX) as r:
            return r.geturl(), r.status, r.read(2_000_000)
    except urllib.error.HTTPError as e:
        return url, e.code, b''
    except Exception:
        return url, None, b''


def decode(data):
    """按响应内容猜测编码（多数站点 utf-8，部分繁体站 big5）。"""
    for enc in ('utf-8', 'big5', 'gb18030'):
        try:
            return data.decode(enc)
        except UnicodeDecodeError:
            continue
    return data.decode('utf-8', errors='replace')


def parse_feed(xml_text):
    """极简 RSS/Atom 解析：返回 [(标题, 链接)]。"""
    import xml.etree.ElementTree as ET
    items = []
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return items
    for el in root.iter():
        tag = el.tag.rsplit('}', 1)[-1]
        if tag not in ('item', 'entry'):
            continue
        title, link = None, None
        for child in el:
            ctag = child.tag.rsplit('}', 1)[-1]
            if ctag == 'title' and child.text:
                title = child.text.strip()
            elif ctag == 'link':
                link = (child.get('href') or child.text or '').strip() or link
        if title:
            items.append((title, link or ''))
    return items


ANCHOR_RE = re.compile(r'<a[^>]+href="([^"#]+)"[^>]*>(.*?)</a>', re.S | re.I)
TAG_RE = re.compile(r'<[^>]+>')
# 商店/CMS 常把商品路径直接写进 HTML（含 JS 数据），期数与主题就编码在路径里
SLUG_RE = re.compile(r'(?:products|articles|posts|magazine)/[^\s"\'<>\\]{4,90}')
TITLE_RE = re.compile(r'<title[^>]*>(.*?)</title>', re.S | re.I)
OGTITLE_RE = re.compile(r'property="og:title" content="([^"]*)"', re.I)


def page_headline(page_url, data):
    """取页面 <title> / og:title 作为候选标题。"""
    text = decode(data)
    m = OGTITLE_RE.search(text) or TITLE_RE.search(text)
    if not m:
        return None
    title = html.unescape(re.sub(r'\s+', ' ', TAG_RE.sub(' ', m.group(1)))).strip()
    return title or None


def scan_html(page_url, data, pub_title=None):
    """从官网页面提取新刊候选：
    1) 锚文本含期数/公告词的链接；
    2) 内嵌商品路径（URL 解码后常为 貢丸湯vol40〈經典客家味〉-1 这类）；
    3) 若以上仍无「可解析期数」的候选，跟进站内候选页标题深挖一层。"""
    text = decode(data)
    host = urlparse(page_url).netloc.lower()
    out, seen_urls = [], set()

    def push(cand):
        if cand['url'] in seen_urls:
            return
        seen_urls.add(cand['url'])
        out.append(cand)

    for href, inner in ANCHOR_RE.findall(text)[:3000]:
        anchor = html.unescape(re.sub(r'\s+', ' ', TAG_RE.sub(' ', inner))).strip()
        if not anchor or len(anchor) > 120:
            continue
        hay = anchor.lower()
        if not any(k in hay for k in KEYWORDS):
            continue
        issue, theme = parse_issue(anchor)
        if issue is None and not ANNOUNCE_RE.search(anchor):
            continue
        target = urljoin(page_url, href)
        t_host = urlparse(target).netloc.lower()
        if t_host != host and 'weixin.qq.com' not in t_host and 'mp.weixin' not in t_host:
            continue
        push({'title': anchor, 'issue': issue, 'theme': theme, 'url': target})

    # 内嵌路径扫描：不依赖锚文本，直接从 HTML 原文里解码商品/文章路径
    for m in SLUG_RE.finditer(text):
        raw = m.group(0)
        slug = urllib.parse.unquote(raw.split('?')[0])
        issue, theme = parse_issue(slug)
        if issue is None:
            continue
        url = urljoin(page_url, raw.split('?')[0])
        push({'title': slug, 'issue': issue, 'theme': theme, 'url': url})

    # 深挖：落地页没有可解析期数的候选时，跟进站内候选链接，用目标页标题再提取
    if pub_title and not any(c['issue'] for c in out):
        follow = [c['url'] for c in out
                  if urlparse(c['url']).netloc == host][:3]
        if not follow:  # 锚点扫描颗粒太粗时，退而抓取页面里任意同域详情链接
            follow = [urljoin(page_url, h) for h in re.findall(r'href="(/[^"#?]+)"', text)[:6]
                      if re.search(r'\d|magazine|product|post|article', h)][:3]
        for u in follow:
            _, st, d2 = fetch(u)
            if not st or st >= 400:
                continue
            headline = page_headline(u, d2)
            if not headline:
                continue
            issue, theme = parse_issue(headline)
            if issue is not None or ANNOUNCE_RE.search(headline):
                push({'title': headline, 'issue': issue, 'theme': theme, 'url': u})
    return out


def extract_from_channel(channel, pub):
    """抓取一条通道，返回 (candidates, warnings)。candidates: [{issue, theme, title, url}]"""
    warnings = []
    adapter = channel.get('adapter')
    url = channel.get('feed') if adapter in ('rss', 'official') and channel.get('feed') else channel['url']
    if url.startswith('http://'):
        url = 'https://' + url[7:]  # CI 环境一律升级 https
    final, status, data = fetch(url)
    if not status:
        return [], [f'{pub["t"]}：通道不可达 {url}']
    if status >= 400:
        return [], [f'{pub["t"]}：通道返回 {status} {url}']
    if adapter == 'rss' or (channel.get('feed') and data.lstrip()[:5] in ('<?xml', '<rss ')):
        candidates = []
        for title, link in parse_feed(decode(data))[:60]:
            title = html.unescape(re.sub(r'<[^>]+>', ' ', title)).strip()
            title = re.sub(r'\s+', ' ', title)
            issue, theme = parse_issue(title)
            # feed 里全是站点博文：没有期数又不像发布公告的条目直接丢弃
            if issue is None and not ANNOUNCE_RE.search(title):
                continue
            candidates.append({'issue': issue, 'theme': theme, 'title': title, 'url': link or final})
        return candidates[:MAX_ITEMS_PER_CHANNEL], []
    return scan_html(final, data, pub_title=pub['t']), []


def clean_theme(theme, title):
    """标题形如《貢丸湯》第30期《貢丸湯》〈…〉时，主题会残留重复刊名，清掉。"""
    nm = re.sub(r'（[^）]*）', '', title.replace('《', '').replace('》', ''))
    t = (theme or '').strip()
    if nm and t.startswith(nm):
        t = t[len(nm):].lstrip('》〉」』 　·：:－-')
    return t.strip()


# 价格（NT$200 / ¥1,500 / 1,200円…）不属于「主题」，一律剔除
PRICE_RE = re.compile(
    r'(?:NT\s?\$|HK\$|US\$|S\$|RM|¥|￥|€)\s?[\d,]+(?:\.\d+)?|\d{1,3}(?:,\d{3})+円|\d+\s?円',
    re.I)
# 主题里不允许出现的表述（创刊/上市/发售等事件词、购买引导）：整个条目视为无效
THEME_FORBIDDEN_RE = re.compile(
    r'^(?:創刊|创刊|復刊|复刊|新刊上市|上市|発売|发售|好評発売中|封面公開|封面公开|最新刊のご購入|ご購入はこちら)[!！。.\s]*$')


# 标题边缘的促销话术（新刊發售／熱賣中／装饰符号…）：反复剥离
PROMO_EDGE = ('新刊發售', '新刊上市', '新刊発売', '好評発売中', '熱賣中', '热卖中', '発売中',
              '封面公開', '封面公开', '最新刊', '新刊', '発売', '發售', '发售', '上市', '創刊', '创刊', '復刊', '复刊',
              '✨', '🔥', '🎉', '📢', '＼', '／', '/', '|')


def strip_promo_edges(t):
    pad = ' 　＼／/|'
    for _ in range(6):
        before = t
        t = t.strip(pad)
        for tok in PROMO_EDGE:
            if t.startswith(tok):
                t = t[len(tok):].strip(pad)
            if t.endswith(tok):
                t = t[:len(t) - len(tok)].strip(pad)
        if t == before:
            break
    return t


def clean_display_theme(theme, title):
    """页面展示用的主题：去重复刊名、去联名企划标注、去价格与促销话术；无效返回空串。"""
    nm = re.sub(r'（[^）]*）', '', title.replace('《', '').replace('》', ''))
    nmc = re.sub(r'\s+', '', nm).lower()
    t = clean_theme(theme, title)
    t = re.sub(r'【[^】]*】', ' ', t)          # 【X 和 X 特别企划】类联名标注不属于主题
    t = PRICE_RE.sub(' ', t)

    # 剥离引用刊名自身的书名号段（如 雑誌『DEEPTOKYOmagazine 』創刊！）
    def drop_self(m):
        inner = re.sub(r'\s+', '', m.group(1) or m.group(2) or '')
        return ' ' if nmc and nmc in inner.lower() else m.group(0)
    t = re.sub(r'[『「《]([^』」》]{0,40})[』」》]', drop_self, t)
    t = re.sub(r'^(?:雑誌|杂志)\s*', '', t.strip())
    t = re.sub(r'\s+', ' ', t).strip(' 　·：:－-~〜')
    t = strip_promo_edges(t)
    t = re.sub(r'\s+', ' ', t).strip(' 　·：:－-~〜')
    if nmc and t.startswith(nm):               # 促销词剥掉后才露出的重复刊名
        t = t[len(nm):].lstrip('》〉」』 　·：:－-')
        t = strip_promo_edges(t)
    t = re.sub(r'[-－_]\d{1,3}$', '', t)       # 商品路径尾部编号（…〈經典客家味〉-1）
    t = re.sub(r'\s+', ' ', t).strip(' 　·：:－-~～!！')
    if not t or THEME_FORBIDDEN_RE.fullmatch(t):
        return ''
    return t


def issue_rank(issue):
    """期数排序权重：纯数字比大小，N年N月号折算为序，无期数为 -1。"""
    if not issue:
        return -1
    m = re.fullmatch(r'(\d{4})年(\d{1,2})月号', issue)
    if m:
        return int(m.group(1)) * 12 + int(m.group(2))
    return int(issue) if re.fullmatch(r'\d{1,4}', issue) else -1


def item_key(item):
    base = item['url'].split('#')[0].rstrip('/')
    return (item['issue'] or '?') + '|' + base


def main():
    args = sys.argv[1:]
    filter_words = None
    if '--pubs' in args:
        filter_words = args[args.index('--pubs') + 1].split(',')

    sources = json.loads(SOURCES_PATH.read_text(encoding='utf-8'))
    history = json.loads(HISTORY_PATH.read_text(encoding='utf-8')) if HISTORY_PATH.exists() \
        else {'version': 1, 'history': {}, 'batches': []}
    hist = history.setdefault('history', {})
    batches = history.setdefault('batches', [])  # [{'d': 'YYYY-MM-DD', 'items': [...]}]，最新在前

    jobs = []            # 可自动抓取的 (pub, channel)：仅官方通道
    pending_confirm = []  # 二手信源：不自动采信，报告里列出让人类确认
    for p in sources['pubs']:
        if p['method'] not in ('rss', 'official', 'platform'):
            continue
        if filter_words and not any(w in p['t'] for w in filter_words):
            continue
        for c in p['channels']:
            if c.get('usable') == 'dead' or c.get('adapter') not in ('rss', 'official', 'platform'):
                continue
            if c.get('grade') == 'secondhand':
                pending_confirm.append((p, c))   # 抓取原则：二手信源必须经人工确认
                continue
            jobs.append((p, c))

    warnings, fresh_all = [], []  # fresh_all: (pub, channel, candidate)，去重后的新候选
    with concurrent.futures.ThreadPoolExecutor(max_workers=FETCH_WORKERS) as ex:
        futs = {ex.submit(extract_from_channel, c, p): (p, c) for p, c in jobs}
        for f in concurrent.futures.as_completed(futs):
            p, c = futs[f]
            try:
                candidates, chans_warn = f.result()
                warnings.extend(chans_warn)
            except Exception as e:  # 抓取器自身缺陷不应中断整轮
                warnings.append(f'{p["t"]}：抓取异常 {type(e).__name__}: {e}')
                continue
            seen = {(r.get('issue') or '?', r['url'].split('#')[0].rstrip('/'))
                    for r in hist.get(p['t'], [])}
            fresh_all.extend((p, c, cand) for cand in candidates
                             if ((cand['issue'] or '?'), cand['url'].split('#')[0].rstrip('/')) not in seen)

    # 抓取原则：每刊只取最新一期。期数与主题至少要有一个——都解析不出（或主题
    # 属于价格/创刊/上市/购买引导等无效表述）的条目整条舍弃；有期数无主题则只展示期数。
    # 出版公告信号（/news/ 路径、封面公開/新刊/發售 等标题词）优先于内容特集页：
    # 官网常同时存在「特集页」（vol.NN 主题页）与「出版公告页」（第N期封面公開/发售），
    # 刊物期数以公告页为准。
    PUB_EVENT_RE = re.compile(r'新刊|出刊|創刊|创刊|復刊|复刊')
    ANNOUNCE_URL_RE = re.compile(r'/news/|/notice|/announcement|/press')
    ANNOUNCE_TITLE_RE = re.compile(r'封面公開|封面公开|公開|公开|新刊|發售|发售|発売|上市|出刊')

    def announce_signal(cand):
        return bool(ANNOUNCE_URL_RE.search(urlparse(cand['url']).path)
                    or ANNOUNCE_TITLE_RE.search(cand['title']))

    grouped = {}
    for p, c, cand in fresh_all:
        has_issue = issue_rank(cand['issue']) >= 0
        has_event = bool(PUB_EVENT_RE.search(cand['title']))
        if not (has_issue or has_event):
            continue
        # 已记录过更高期数的刊物，不再接受更旧的「最新一期」
        max_seen = max((issue_rank(r['issue']) for r in hist.get(p['t'], [])
                        if issue_rank(r['issue']) >= 0), default=-1)
        if has_issue and issue_rank(cand['issue']) <= max_seen:
            continue
        grouped.setdefault(p['t'], (p, []))[1].append((c, cand, has_issue))
    new_items = []
    for t, (p, cands) in grouped.items():
        signalled = [x for x in cands if announce_signal(x[1])]
        pool = signalled or cands
        # 同期数并列时优先有实质主题的一条（如〈與自己散步〉优先于「封面公開」）
        def pick_key(x):
            rank = issue_rank(x[1]['issue'])
            has_theme = 1 if clean_display_theme(x[1].get('theme', ''), t) else 0
            return (rank, has_theme)
        best_c, best, best_has_issue = max(pool, key=pick_key)
        theme = clean_display_theme(best.get('theme', ''), t)
        if not theme and not best_has_issue:
            continue
        item = {'issue': best['issue'], 'title': best['title'], 'url': best['url'],
                'theme': theme,
                'foundAt': datetime.now(TZ_CN).strftime('%F'),
                'channel': best_c['url']}
        new_items.append((p, item))

    if new_items:
        for p, item in new_items:
            hist.setdefault(p['t'], []).append(item)
        # 同一天的多条发现归入同一批次；批次列表最新在前，供页面「新刊速递」模块使用
        d = datetime.now(TZ_CN).strftime('%F')
        batch = next((b for b in batches if b['d'] == d), None)
        if batch is None:
            batch = {'d': d, 'items': []}
            batches.insert(0, batch)
        for p, item in new_items:
            # 同刊同期替换：批次里该刊物只保留最新一条（只取最新一期原则）
            batch['items'] = [x for x in batch['items'] if x['t'] != p['t']]
            batch['items'].append({'t': p['t'], 'shelf': p['shelf'], 'issue': item['issue'],
                                   'theme': item['theme'], 'title': item['title'], 'url': item['url']})
        history['lastRun'] = datetime.now(TZ_CN).strftime('%F %R %z')
        HISTORY_PATH.write_text(json.dumps(history, ensure_ascii=False, indent=1) + '\n',
                                encoding='utf-8')

    # —— Markdown 摘要（stdout → PR 描述）——
    now = datetime.now(TZ_CN).strftime('%F %R')
    lines = [f'## 新刊速递 · 抓取报告（{now}）', '']
    if new_items:
        lines.append(f'发现 **{len(new_items)}** 条新公告：')
        lines.append('')
        for p, item in new_items:
            issue = f'第 {item["issue"]} 期 · ' if item['issue'] else ''
            theme = f'《{item["theme"]}》' if item['theme'] else item['title']
            lines.append(f'- **{p["t"]}**（{p["shelf"]}）— {issue}{theme}')
            lines.append(f'  [{item["url"]}]({item["url"]})')
    else:
        lines.append('本轮没有发现新的刊物公告。')
    if pending_confirm:
        lines += ['', '### 二手信源 · 待人工确认', '',
                  '以下通道为二手信源（媒体报道/书店页等），按原则不自动采信，确认后请手动登记：', '']
        lines += [f'- {p["t"]}（{p["shelf"]}）· {c["name"]}：{c["url"]}'
                  for p, c in pending_confirm]
    if warnings:
        lines += ['', '### 警告', '']
        lines += [f'- {w}' for w in warnings[:30]]
    print('\n'.join(lines))
    print(f'\n[统计] 监控 {len({p["t"] for p, _ in jobs})} 种 / 通道 {len(jobs)} 条，'
          f'新公告 {len(new_items)} 条，警告 {len(warnings)} 条', file=sys.stderr)
    return 0


if __name__ == '__main__':
    sys.exit(main())
