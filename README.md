# 在地刊物地图

把华语与东亚地区的在地刊物（城市杂志、社区报、地方志出版物）标在五张手绘示意地图上：
中国大陆·港澳、台湾、日本、新马、泰国。每根图钉是一个城市的「书柜」，点开可翻阅书架与刊物详情。

- 线上页面：https://enzopodwiki.github.io/local-press-map/
- 纯静态单文件站点，无框架、无依赖、无后端。

## 功能速览

- **全站搜索**：页首搜索框，按刊名 / 城市 / 简介关键词检索全部刊物，
  标题匹配排在前面；`/` 或 `Ctrl/Cmd + K` 聚焦，↑↓ 选择，Enter 打开，Esc 关闭。
- **刊物级深链**：URL 形如 `#书柜id/第几本`（如 `#beijing/2`），翻书时自动同步——
  任何时候复制地址栏都能回到正在看的那本书；只写 `#书柜id` 则打开整个书柜。
- **移动端**：封面区域左右滑动翻书；地图横滑大图 + 地区胶囊索引。

## 仓库结构

```
data/在地刊物地图.md    内容唯一数据源：刊物条目（标题/地点/年份/频率/停刊/介绍/信源/封面）
data/regions.json      结构数据：52 个书柜的分组、顺序、地图归属（新增地区时才改）
template.html          版式模板：页面的一切，除了数据（DATA 与总数是占位符）
tools/build.py         构建脚本：数据源 + 模板 → index.html
tools/validate.py      校验脚本：数据一致性体检（CI 也会跑）
tools/migrate_p0.py    一次性迁移脚本存档（2026-08 从旧仓库结构迁出，勿再用）
index.html             构建产物，GitHub Pages 直接发布本文件
covers/                封面图（c001…c141，条目用「封面：covers/cXXX.jpg」引用）
archive/build_legacy/  P0 之前的一次性补丁脚本与备份，仅作历史存档
```

## 数据流与命令

```
data/在地刊物地图.md ─┐
data/regions.json  ──┼─→ tools/build.py ─→ index.html ─→ git push 即发布
template.html      ─┘         ↑
                    tools/validate.py 体检
```

```bash
python3 tools/build.py             # 构建并覆盖 index.html
python3 tools/build.py --check     # 只校验 index.html 是否与数据源一致（不写文件）
python3 tools/validate.py          # 数据体检：0 错误才允许提交
```

CI（.github/workflows/validate.yml）会在每次 push 时自动跑 `--check` 和校验。

## 如何新增一本刊物

1. 在 `data/在地刊物地图.md` 找到对应城市小节（`###`），按格式加条目：

   ```
   #### 《刊物名》
   📍地点｜🕐创刊 2024 年｜📌季刊｜⛔已停刊     （空的字段省略；停刊可不写 ⛔）
   一段话介绍，单行。
   信源：[来源名](链接) ｜ [来源名](链接)       （可无）
   封面：covers/c142.jpg                       （可无，文件先放进 covers/）
   ```

2. 在 `data/regions.json` 里找到该书柜，把 `《刊物名》` 加进 `pubs` 数组
   （数组顺序 = 书架上的排列顺序）。标题必须与 MD 条目完全一致。
3. 跑 `python3 tools/build.py && python3 tools/validate.py`——地图 pin 上的数量、
   页面总数会自动更新；校验会拦下标题对不上、封面缺失等问题。
4. 提交并推送，Pages 一两分钟后更新。

其他场景：

- **补封面**：图片放进 `covers/`（建议宽 540px 左右的 jpg，200KB 内），
  在该条目里加一行 `封面：covers/cXXX.jpg`，重新构建。
- **发「更新啦」横幅**：编辑 `template.html` 里的 `UPDATES` 数组（往数组头部加批次）。
  每条是 `[书柜id, 地域名, 《刊名》]`，点击会深链跳到那本书——刊名必须与档案标题
  完全一致（含括号后缀），`validate.py` 会校验。
- **新增书柜（地区）**：`data/regions.json` 加分组，并在 `template.html` 对应地图的
  SVG 里手放一个 pin（`<g class="pin" data-r="新id"…`，坐标参考邻近城市）。
  除非确有必要，优先并入现有书柜。

## 数据源约定

- 档案 MD 是唯一内容源；`index.html` 是生成物，**不要直接手改**（改了 `--check` 会报）。
- 条目标题（`#### 《…》`）是 MD 与 regions.json 之间的主键，改名要两处同步。
- 档案头部的「刊物总数」「合计」是手写统计，构建不会改它；数量变了 validate 会提醒。
- 「香港社区报」在档案里保留但未编入地图（见 `regions.json` 的 `exclude`）。
