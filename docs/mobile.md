# 移动端适配约定

2026-09 轮次（大陆取景、县级下拉统一、角标化、底部留白）沉淀的原则与方法。
改移动端前先读这页，能避开全部踩过的坑。

## 原则

1. **先读懂既有设计再动手**：移动端已有机制（如大陆地图 700px 横滑）都为解决
   某个问题而存在。新需求与它冲突时，优先「保留其职责 + 改默认行为」
   （例：默认停东部、右滑仍可达西藏），而不是推倒重来。
2. **首屏对准内容密度**：默认取景/停顿位置给图钉最密的区域；稀疏区交给横滑、
   地区下拉、搜索三条路径兜底——可达性比一屏全见重要。
3. **悬浮件不压内容与按钮**：触控目标 ≥44px；位置避开图钉标签、「全国书柜」
   圆片（.roam-row，bottom 70px 起）和翻页器；放不下时才向上叠。
4. **同类控件全局同位**：地区/县级下拉一律在面板标题正下方，五个面板一个心智模型。
5. **尺寸用相对值**：弹窗内媒体 min(300px, 74vw)；绝对宽度只用于刻意超出视口的
   横滑画布。
6. **用户确认过的布局只改点名部分**，不顺手重排。

## 操作要点与坑

- **viewBox 联动**：`svg.map{width:100%;height:auto}` 的高度随 viewBox 比例变化，
  与固定宽度规则（如大陆移动端 700px）互相作用——改完必须桌面/移动各查一遍
  整体布局，不能只看地图本身。
- **SVGElement 没有 offsetLeft/offsetParent**（HTMLElement 专属）：滚动位置
  计算用「wrap padding-left + 锚点坐标 × 单位换算」；单位 = svg 宽 ÷ viewBox 宽。
- **隐藏/未布局时序**：display:none 或布局未稳时设 scrollLeft、读宽度都不可靠
  （NaN 或静默回 0）。用「load 后 200ms×3s 短轮询保持 + pointerdown/wheel/
  touchstart/keydown 一触即停」。
- **下拉共用**：wireJump(selectId, mapId) 统一接线（跳转 + is-current 高亮 +
  hash 深链同步）；自动生成下拉的插入点是 .panel-head 之后，已有专用下拉的
  面板（taiwan/japan）要从自动名单排除。
- **弹窗媒体**：flex-direction:column + min(Npx, 74vw)，任何屏宽都完整。
- **固定定位元素**（便利贴角标 .float-stack、赞助弹窗）注意与 .roam-row 圆片
  的避让关系；角标横排会挤占圆片，竖排放右下贴边最稳。

## 验证流程

1. 每步 `build.py --check` + `validate.py` 全绿再动下一步。
2. 本地 http.server + 浏览器视口 390×844，scrollIntoView 后截**视口截图**
   ——内嵌浏览器的 fullPage/跨视口 clip 会拼接错乱，出过假截图冤枉好实现。
3. 截图之外用 DOM 数值断言兜底：scrollLeft、getBoundingClientRect 求 pin 在
   卡宽的百分比——截图会骗人，数值不会。
4. 桌面/移动各验一遍，确认桌面没被带走。
