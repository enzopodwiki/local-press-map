#!/usr/bin/env python3
"""「补充刊物」投稿处理：解析 GitHub Issue 表单 → 生成档案条目 + 归柜。

输入：环境变量 ISSUE_BODY（issue 正文，GitHub 表单字段的 Markdown 格式）。
输出：修改 data/在地刊物地图.md 与 data/regions.json；stdout 打印 Markdown 报告。
退出码：0 = 成功生成变更；1 = 数据无效（缺必填/重复/无法归柜），不产生变更。

原则（与主档案一致）：
- 县市名与介绍使用简体中文；刊物名保留投稿者原文（可繁体）；
- 介绍以投稿者提供的内容为素材重新归纳（此脚本原样采用投稿文本，维护者
  在 PR 审核阶段按信源重写——PR 即人工确认环节）。
"""
import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MD_PATH = ROOT / 'data' / '在地刊物地图.md'
REGIONS_PATH = ROOT / 'data' / 'regions.json'

# 县市 dropdown 值 → 书柜 id（与 template.html 下拉框一致）
COUNTY2SHELF = {
 '基隆市': 'tw-keelung', '台北市': 'tw-taipei', '新北市': 'tw-newtaipei', '桃园市': 'tw-taoyuan',
 '新竹市': 'tw-hsinchu-city', '新竹县': 'tw-hsinchu', '苗栗县': 'tw-miaoli', '台中市': 'tw-taichung',
 '彰化县': 'tw-changhua', '南投县': 'tw-nantou', '云林县': 'tw-yunlin', '嘉义市': 'tw-chiayi-city',
 '嘉义县': 'tw-chiayi', '台南市': 'tw-tainan', '高雄市': 'tw-kaohsiung', '屏东县': 'tw-pingtung',
 '宜兰县': 'tw-yilan', '花莲县': 'tw-hualien', '台东县': 'tw-taitung', '澎湖县': 'tw-penghu',
 '金门县': 'tw-kinmen', '连江县': 'tw-lienchiang', '全台（跨县市）': 'tw-all',
 '中国大陆': None, '香港': None, '澳门': None, '日本': None, '新马': None, '泰国': None,
}


def parse_issue_body(body):
    """GitHub issue form 的正文是 '### 字段名\\n\\n值' 的重复结构。"""
    fields = {}
    sections = re.split(r'\n### ', '\n' + body)
    for sec in sections[1:]:
        lines = sec.split('\n')
        label = lines[0].strip().rstrip('*').strip()
        value = '\n'.join(lines[1:]).strip()
        value = re.sub(r'<!--[^>]*-->', '', value).strip()
        fields[label] = value
    return fields


def main():
    body = os.environ.get('ISSUE_BODY', '')
    f = parse_issue_body(body)
    errors, notes = [], []

    title = f.get('刊物名称', '').strip()
    county = f.get('所属县市', '').strip()
    location = f.get('具体地点', '').strip()
    year = f.get('创刊年份', '').strip()
    period = f.get('出版频率', '').strip()
    intro = f.get('刊物介绍', '').strip()
    sources_raw = f.get('信源链接', '').strip()
    status = f.get('出版状态', '')
    notes_raw = f.get('其他说明', '').strip()

    # 必填校验
    if not title:
        errors.append('缺少刊物名称')
    elif not re.match(r'^《.+》$', title):
        title = f'《{title}》'
    if not county:
        errors.append('缺少所属县市')
    if not location:
        errors.append('缺少具体地点')
    if not intro:
        errors.append('缺少刊物介绍')
    if errors:
        print('### 无法处理投稿\n')
        print('\n'.join(f'- {e}' for e in errors))
        return 1

    intro = re.sub(r'\s+', ' ', intro)
    if period in ('不清楚', ''):
        period = ''
    stopped = '该刊物已停刊/休刊' in status

    # 标题唯一
    md = MD_PATH.read_text(encoding='utf-8')
    existing = {b.split('\n')[0].strip() for b in re.split(r'\n#### ', md)[1:]}
    if title in existing:
        print(f'### 无法处理投稿\n\n- 《{title}》已在收录中（标题重复）')
        return 1

    # 归柜
    spec = json.loads(REGIONS_PATH.read_text(encoding='utf-8'))
    regions = {rg['id']: rg for rg in spec['regions']}
    if county not in COUNTY2SHELF:
        errors.append(f'未知县市：{county}')
        print('### 无法处理投稿\n')
        print('\n'.join(f'- {e}' for e in errors))
        return 1
    shelf = COUNTY2SHELF[county]
    if shelf is None:
        # 非台湾投稿：转人工（大陆/海外书柜归并需要维护者判断城市归属）
        print('### 投稿已记录，转人工处理\n')
        print(f'- 非台湾地区投稿（{county}），请维护者手动归入对应书柜。')
        return 1
    if shelf not in regions:
        errors.append(f'书柜不存在：{shelf}')
        print('### 无法处理投稿\n')
        print('\n'.join(f'- {e}' for e in errors))
        return 1

    # 信源行
    src_lines = []
    if sources_raw:
        for u in re.split(r'\s*｜\s*', sources_raw):
            u = u.strip()
            if re.match(r'^https?://', u):
                src_lines.append(f'[信源]({u})')
            else:
                notes.append(f'信源非链接，已放入介绍尾注：{u[:40]}')
                if u:
                    intro = intro + f'（另见：{u}）'
    src_line = '信源：' + ' ｜ '.join(src_lines) if src_lines else ''

    # 组装条目
    meta = f'📍{location}'
    if year:
        meta += f'｜🕐{year}'
    if period:
        meta += f'｜📌{period}'
    if stopped:
        meta += '｜⛔已停刊'

    block = ['', f'#### {title}', meta, intro]
    if src_line:
        block.append(src_line)
    if notes_raw:
        block.append(f'备注：{notes_raw}（投稿者：@{os.environ.get("ISSUE_AUTHOR", "匿名")}）')

    # 写入 MD（该书柜对应的 ### 小节；台湾县市柜按 REGION_SECTION 映射）
    SECTION = {'tw-keelung': '北部', 'tw-taipei': '北部', 'tw-newtaipei': '北部', 'tw-taoyuan': '北部',
               'tw-hsinchu-city': '北部', 'tw-hsinchu': '北部', 'tw-miaoli': '北部',
               'tw-taichung': '中部', 'tw-changhua': '中部', 'tw-nantou': '中部', 'tw-yunlin': '中部',
               'tw-chiayi-city': '中部', 'tw-chiayi': '中部',
               'tw-tainan': '南部', 'tw-kaohsiung': '南部', 'tw-pingtung': '南部',
               'tw-yilan': '东部', 'tw-hualien': '东部', 'tw-taitung': '东部',
               'tw-penghu': '离岛', 'tw-kinmen': '离岛', 'tw-lienchiang': '离岛',
               'tw-all': '全台'}
    sec = SECTION[shelf]
    lines = md.split('\n')
    try:
        start = next(i for i, l in enumerate(lines) if l.strip() == f'### {sec}')
    except StopIteration:
        errors.append(f'档案小节缺失：### {sec}')
        print('### 无法处理投稿\n')
        print('\n'.join(f'- {e}' for e in errors))
        return 1
    end = start + 1
    while end < len(lines) and not lines[end].startswith(('### ', '## ')):
        end += 1
    lines[end:end] = block
    md = '\n'.join(lines)
    MD_PATH.write_text(md, encoding='utf-8')

    # 归柜
    if title not in regions[shelf]['pubs']:
        regions[shelf]['pubs'].append(title)
    REGIONS_PATH.write_text(json.dumps(spec, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')

    # 报告
    print(f'### 投稿解析成功\n')
    print(f'- **{title}** → {regions[shelf]["region"]}（{location}）')
    print(f'- 频率：{period or "未标注"}{"｜已停刊" if stopped else ""}')
    print(f'- 信源：{len(src_lines)} 条')
    if notes:
        print('- 提示：' + '；'.join(notes))
    print('\n**下一步**：维护者审核 PR——按信源重写介绍（禁止照搬投稿文本以外的第三方内容）、')
    print('补封面、确认归柜；合并后由 rebuild 工作流自动更新页面。')
    return 0


if __name__ == '__main__':
    sys.exit(main())
