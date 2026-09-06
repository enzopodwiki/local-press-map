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

# 期数模式：按优先级排列，先命中先得
ISSUE_PATTERNS = [
    (re.compile(r'第\s*([0-9０-９]{1,4})\s*[期輯辑号]'), 'issue'),
    (re.compile(r'\b[Vv]ol\.?\s*([0-9]{1,4})\b'), 'vol'),
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


def scan_html(page_url, data):
    """从 HTML 里提取疑似新刊公告的链接：锚文本含期数或关键词。
    只保留本站链接与微信文章（过滤掉页脚电商、友站等噪音）。"""
    text = decode(data)
    host = urlparse(page_url).netloc.lower()
    out = []
    for href, inner in ANCHOR_RE.findall(text)[:3000]:
        anchor = TAG_RE.sub(' ', inner)
        anchor = html.unescape(re.sub(r'\s+', ' ', anchor)).strip()
        if not anchor or len(anchor) > 120:
            continue
        hay = anchor.lower()
        if not any(k in hay for k in KEYWORDS):
            continue
        issue, theme = parse_issue(anchor)
        if issue is None and not ANNOUNCE_RE.search(anchor):
            continue  # 无期数也非明确发布公告的链接不要
        target = urljoin(page_url, href)
        t_host = urlparse(target).netloc.lower()
        if t_host != host and 'weixin.qq.com' not in t_host and 'mp.weixin' not in t_host:
            continue
        out.append({'title': anchor, 'issue': issue, 'theme': theme, 'url': target})
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
    return scan_html(final, data)[:MAX_ITEMS_PER_CHANNEL], []


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

    jobs = []  # (pub, channel)
    for p in sources['pubs']:
        if p['method'] not in ('rss', 'official', 'platform'):
            continue
        if filter_words and not any(w in p['t'] for w in filter_words):
            continue
        for c in p['channels']:
            if c.get('usable') == 'dead' or c.get('adapter') not in ('rss', 'official', 'platform'):
                continue
            jobs.append((p, c))

    warnings, new_items = [], []
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
            fresh = [cand for cand in candidates
                     if ((cand['issue'] or '?'), cand['url'].split('#')[0].rstrip('/')) not in seen]
            for cand in fresh:
                item = {'issue': cand['issue'], 'title': cand['title'], 'url': cand['url'],
                        'theme': cand.get('theme', ''), 'foundAt': datetime.now(TZ_CN).strftime('%F'),
                        'channel': c['url']}
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
            batch['items'].append({'t': p['t'], 'issue': item['issue'], 'theme': item['theme'],
                                   'title': item['title'], 'url': item['url']})
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
    if warnings:
        lines += ['', '### 警告', '']
        lines += [f'- {w}' for w in warnings[:30]]
    print('\n'.join(lines))
    print(f'\n[统计] 监控 {len({p["t"] for p, _ in jobs})} 种 / 通道 {len(jobs)} 条，'
          f'新公告 {len(new_items)} 条，警告 {len(warnings)} 条', file=sys.stderr)
    return 0


if __name__ == '__main__':
    sys.exit(main())
