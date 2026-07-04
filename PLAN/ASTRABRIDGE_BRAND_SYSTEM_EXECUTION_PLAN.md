# AstraBridge 星桥品牌系统执行计划

Last updated: 2026-07-04

## 总目标

把 AstraBridge 星桥的桌面端界面从“功能可用”推进到“具有稳定品牌识别度的产品界面”。

目标不是给现有界面套一层装饰皮肤，而是建立一套可持续执行的品牌系统，使以下元素在多个 surface 上统一工作：

- 浅蓝为主、克制而专业的品牌色系
- 半透明、低干扰的星座/星图背景语言
- 不同于通用 SaaS 边框的“星桥边界”渲染方式
- 重做后的高频图标系统
- 自定义鼠标强调层与低密度星点拖尾
- 与真实运行状态绑定的“点亮星座”等待动画
- 对左侧栏、中间任务区、右侧 inspector、设置页、浏览器页、文件页等 surface 的一致品牌落地

本计划必须保持以下产品边界：

- 风格要有识别度，但不能破坏高密度工作流和信息效率。
- 品牌感优先通过 token、边界、图标、轻动效和背景层次建立，而不是靠“卡片大战”、厚圆角、重渐变和大面积装饰。
- 每轮对话只完成一个编号步骤；完成后必须更新本文件的“当前进度”和“完成记录”。
- 后续 agent 从下一未完成步骤开始，除非用户明确要求跳转。

## 注意事项

- 星桥品牌风格必须保持“克制的专业观测台”方向，不做游戏 UI，不做大面积科幻海报，不做廉价发光效果。
- 中间主任务窗口是高频工作区，品牌装饰强度必须低于左侧栏、设置页和空态页。
- 禁止重新引入大块圆角卡片、厚阴影、紫蓝渐变主导、装饰性大英雄区等 AI 风格默认审美。
- 所有 UI 改动都要频繁截图复核，优先使用 in-app browser 和已有 screenshot QA 规则检查：
  - 桌面常规宽度
  - 右侧栏展开宽度
  - 窄宽度 / 竖向浏览器场景
  - hover / focus / loading / empty / error 状态
- 动效必须有 `reduced motion` 退化方案；鼠标增强和拖尾必须可关。
- 品牌效果不得影响输入框、文本编辑区、浏览器嵌入区、拖拽区和文件预览区的可读性与可操作性。
- 品牌实现优先使用现有 CSS token、React 组件、lucide icon 替换、SVG/canvas 和受控 bitmap 资产；避免引入沉重运行时依赖。
- 默认保留 `PRIVATE/**` 下的评审截图、风格探索图、生成过程和验证报告，但不得提交含 secret 的内容。
- 如果引入外部公开素材，必须在真正落地该素材的同一轮里更新 `docs/ASSET_SOURCES.md`，写清 source URL、license/usage note、应用位置和 owning step。

## 公开素材与版权边界

允许使用生图工具和公开素材，但必须遵守以下来源优先级与边界。

### 1. 首选来源

- OpenAI / AstraBridge 管理下生成的自有品牌资产
  - 用于壁纸底图、星点纹理、指针装饰、加载动画精灵、非官方图标草图。
  - 优先级最高，因为版权和品牌唯一性最好控制。
- 自绘 SVG / canvas / CSS 程序化图形
  - 用于星轨、星座连线、边框高光、等待态节点、鼠标拖尾。

### 2. 允许的公开素材来源

- NASA 官方媒体
  - 参考：<https://www.nasa.gov/nasa-brand-center/images-and-media/>
  - 允许点：NASA 内容通常可用于教育/信息用途。
  - 限制点：不得使用 NASA 标识、徽记或形成官方背书暗示；如页面特别注明例外，以页面例外为准。
- Wikimedia Commons
  - 参考：<https://commons.wikimedia.org/wiki/Commons:Reusing_content_outside_Wikimedia>
  - 允许点：可复用公开领域或自由许可内容。
  - 限制点：必须按“文件级”核对具体 license，不能因为站点整体可复用就默认所有文件可直接商用或免署名。
- Unsplash
  - 参考：<https://unsplash.com/license>
  - 允许点：官方许可允许免费使用与修改。
  - 限制点：不作为星桥核心品牌资产默认来源，仅作为 moodboard 或壁纸备选来源；不允许用作“官方品牌独特性”的主要承载。

### 3. 许可执行规则

- 真正下载/提交任何单个外部素材前，必须在该轮再次核对一次源页面 license，而不是只依赖本计划中的概括。
- 默认只接受以下三类外部素材进入仓库：
  - public domain / CC0
  - CC-BY / CC-BY-SA 且能明确记录 attribution
  - NASA 媒体使用指南允许的素材，且不涉及标识/背书风险
- 外部素材仅用于壁纸、纹理、参考图或经过显著二次加工的底层视觉材料；星桥核心图标、主标识、任务/导航高频图标默认应为自绘或自生成。
- 如果某素材 license 有模糊区、署名要求不清、衍生作品限制不清、商用边界不清，则本计划默认视为不可用。

## 细节

### 1. 品牌气质

- 关键词：浅蓝、冷静、观测、连线、轨道、桥接、星图、低噪声
- 避免词：霓虹、厚重玻璃、夜店紫、魔法粒子、满屏星空、过度浪漫化

### 2. 视觉层级

- 左侧栏：品牌识别最强
- 顶栏 / 输入区：中等品牌识别
- 主任务区：最克制，只保留轻边界和状态动效
- 右侧 inspector：专业观测面板式品牌感
- 设置页 / 空态页：允许更强背景和图形语言

### 3. 色彩系统

建议先建立品牌 token，再逐步替换现有散色：

- 主蓝：用于高优先级高亮、激活状态、品牌焦点
- 冰蓝：用于边界、hover、弱强调
- 雾白蓝：用于玻璃底色和浅背景
- 深蓝灰：用于正文和高对比文本
- 紫灰：仅用于层级阴影与次要分隔，不作为主视觉中心

### 4. 背景系统

背景拆为三层：

- 底层：极淡冷光
- 中层：稀疏星点
- 上层：低对比星座连线

正文区必须永远比背景更强，不允许出现“背景比内容更有存在感”的情况。

### 5. 边界系统

核心不是做卡片，而是做“星桥边界”：

- 薄描边
- 局部高光
- 激活态轻流光
- 选中态星轨切角或小节点
- 低阴影或无阴影

### 6. 图标系统

- 基于统一线宽和圆角策略
- 保留工程感，不走可爱化路线
- 在少数关键图标中引入“轨道节点 / 星点连接 / 桥接路径”母题
- 从一级导航、权限模式、工作流模式、等待状态、浏览器控制、文件/审查操作开始替换

### 7. 鼠标系统

只做 app 内部 cursor enhancement，不替换系统级原生鼠标：

- 默认箭头保留清晰命中感
- 加轻量星桥外轮廓或尾迹 accent
- 拖尾限制为低密度星点，不做连续粒子喷射
- 文本区必须尊重 I-beam 语义
- 低性能或 reduced-motion 模式下自动禁用

### 8. 等待态系统

等待态统一为“点亮星座”，并且必须与真实状态绑定：

- 短等待：输入区小星座
- 中等待：消息或活动行附近的节点推进
- 长等待：独立但克制的阶段星图

状态绑定至少考虑：

- 思考中
- 工具调用中
- 联网中
- 文件编辑中
- 自动化运行中
- 成功完成 / 中断 / 失败

### 9. 技术边界

- 优先复用现有 `styles.css`、组件层、状态层和截图 QA 流程
- 非必要不引入大型动画库
- 若使用 canvas，必须证明：
  - 不遮挡交互
  - 不产生高 CPU 常驻负担
  - 在窄面板中仍保持清晰

### 10. 交付边界

本计划的最终交付不只是“看起来更像星桥”，而应包括：

- 品牌 token
- 组件样式落地
- 图标替换
- 动效系统
- 鼠标系统
- 素材来源记录
- 性能/无障碍/截图 QA 证据

## 实现步骤

- [x] 1. 固化品牌系统执行计划与素材许可边界
  - 目标：
    - 把星桥专属风格从口头方向变成可逐轮执行的品牌计划。
    - 明确生图工具与公开素材的许可边界、优先级和记录规则。
  - 交付物：
    - `PLAN/ASTRABRIDGE_BRAND_SYSTEM_EXECUTION_PLAN.md`
  - 完成标准：
    - 后续 agent 能直接从本文件读取品牌目标、注意事项、风格细节、顺序步骤和当前进度。
    - 本文件清楚说明可用公开素材来源与 file-level license 校验要求。
  - 验证方式：
    - 本文件存在且包含总目标、注意事项、公开素材与版权边界、细节、实现步骤、当前进度、完成记录几个部分。

- [x] 2. 盘点当前 UI surface 并建立品牌改造基线
  - 目标：
    - 梳理当前左侧栏、顶栏、主任务区、composer、右侧 inspector、设置页、浏览器页、文件页的视觉现状。
    - 记录“卡片大战”“边框冗余”“颜色不统一”“图标风格混杂”“等待态普通”“鼠标无品牌感”等基线问题。
  - 交付物：
    - 一份品牌基线截图集
    - 一份基线问题报告
  - 完成标准：
    - 每个高频 surface 至少有一张基线截图与一组问题说明。
  - 验证方式：
    - in-app browser 截图与问题清单已保存，且可直接作为后续改造前后对比证据。

- [x] 3. 建立星桥品牌 token 系统
  - 目标：
    - 在前端代码中定义颜色、透明度、描边、高光、阴影、圆角、模糊等品牌 token。
    - 替换明显散乱或不一致的现有基础值。
  - 交付物：
    - 品牌 token 代码
    - token 使用规则说明
  - 完成标准：
    - 后续 surface 改造可基于 token，而不是继续写零散值。
  - 验证方式：
    - 代码中品牌核心值集中管理，构建通过。

- [x] 4. 建立半透明星座壁纸系统
  - 目标：
    - 做一套低干扰背景系统，支持主背景、侧栏背景、空态背景和设置页背景。
    - 确认背景强度不会压过正文。
  - 交付物：
    - 自生成或程序化背景资产
    - 背景层级与使用规则
  - 完成标准：
    - 背景在高频工作面中存在感低，在空态/设置中存在感略高。
  - 验证方式：
    - 多个 viewport 截图复核文字可读性与背景克制程度。

- [x] 5. 建立“星桥边界”基础样式原语
  - 目标：
    - 把边框、激活态、hover、高光、切角、薄玻璃面做成可复用样式原语。
    - 逐步替换厚卡片和普通边框。
  - 交付物：
    - 边界样式类或样式 token
  - 完成标准：
    - 常见 panel、按钮、行项、tab 和输入区有统一边界语言。
  - 验证方式：
    - 代表性 surface 前后对比截图可见边界风格统一。

- [x] 6. 改造左侧栏与顶部 chrome
  - 目标：
    - 把左侧栏做成品牌识别最强的区域。
    - 统一顶部导航、返回、菜单、切换入口的视觉语言。
  - 交付物：
    - 左侧栏与顶部样式改造
  - 完成标准：
    - 左侧栏更像星桥，而不是默认 web app 列表。
  - 验证方式：
    - 展开/收起状态截图通过，信息密度未下降。

- [x] 7. 改造主任务区与 composer 的品牌基底
  - 目标：
    - 在不干扰高频工作的前提下，为主任务区、输入框、模式切换和发送区加入克制品牌感。
    - 确保主任务区仍是全局最安静的区域。
  - 交付物：
    - 主任务区与 composer 样式改造
  - 完成标准：
    - 输入和阅读效率不受影响，但品牌识别明显提升。
  - 验证方式：
    - 对话长列表、空态、输入中、发送中截图复核。

- [x] 8. 改造右侧 inspector 的品牌化观测面板样式
  - 目标：
    - 让状态、审查、浏览器、文件四个 inspector tab 统一为“观测面板”风格。
    - 保留 canvas 优先和信息压缩的成果，不倒退成卡片堆叠。
  - 交付物：
    - inspector 样式改造
  - 完成标准：
    - 右栏既专业又有星桥识别度，不牺牲空间利用率。
  - 验证方式：
    - 展开右栏截图与窄栏截图通过。

- [x] 9. 固化图标系统规范与替换矩阵
  - 目标：
    - 定义星桥图标风格规则、优先替换清单和禁用风格。
    - 盘点当前所有高频图标替换优先级。
  - 交付物：
    - 图标规范
    - 一级替换矩阵
  - 完成标准：
    - 后续图标重做不再是零散修改。
  - 验证方式：
    - 图标清单明确覆盖一级导航、高频控制、状态入口和模式切换。

- [x] 10. 替换一级导航与高频控制图标
  - 目标：
    - 先替换最常见、最影响品牌识别的图标。
  - 交付物：
    - 一级导航与高频控制图标落地
  - 完成标准：
    - 用户第一眼可见区域不再混用旧符号和默认图标。
  - 验证方式：
    - 左侧栏、顶部、composer、inspector 截图通过。

- [x] 11. 建立“点亮星座”等待态基础组件
  - 目标：
    - 把等待动画抽象成可复用基础组件，而不是到处写临时 spinner。
  - 交付物：
    - 星座等待态基础组件
  - 完成标准：
    - 短等待和中等待场景都有可复用版本。
  - 验证方式：
    - 本地状态切换演示与截图通过。

- [x] 12. 将等待态与真实运行阶段绑定
  - 目标：
    - 把星座等待态绑定到思考、工具、联网、文件编辑、自动化等真实事件，而不是装饰性循环动画。
  - 交付物：
    - 运行状态绑定逻辑
  - 完成标准：
    - 用户能从等待态看懂当前系统正在做什么。
  - 验证方式：
    - 运行中截图和事件回放截图通过。

- [x] 13. 建立自定义鼠标强调层与拖尾原型
  - 目标：
    - 做 app 内部 cursor enhancement 原型，验证视觉质量、命中语义和性能。
  - 交付物：
    - cursor overlay 原型
  - 完成标准：
    - 默认态、hover 态、拖拽态有差异，但不干扰文本编辑和点击。
  - 验证方式：
    - 视频或连续截图复核，性能无明显恶化。

- [x] 14. 为鼠标系统补齐开关、降级和 reduced-motion 方案
  - 目标：
    - 让鼠标增强和拖尾可以关闭，并在低性能/无障碍条件下降级。
  - 交付物：
    - 设置开关
    - reduced-motion 退化逻辑
  - 完成标准：
    - 鼠标系统不成为强制品牌效果。
  - 验证方式：
    - 开关前后与 reduced-motion 模式截图/测试通过。

- [x] 15. 改造浏览器 surface 的星桥品牌外观
  - 目标：
    - 在保留瘦高浏览器产品化方向的前提下，加入星桥的边界、背景和图标语言。
    - 保证不回退到厚 tab、重卡片或无效说明文案。
  - 交付物：
    - 浏览器 surface 品牌样式改造
  - 完成标准：
    - 浏览器页既像浏览器，也明显属于星桥。
  - 验证方式：
    - 真实网页与移动端渲染截图通过。

- [x] 16. 改造文件、审查、设置与认证 surface
  - 目标：
    - 把文件、审查、设置、provider/API key/模型管理等次高频界面统一纳入品牌系统。
  - 交付物：
    - 相关 surface 品牌样式改造
  - 完成标准：
    - 不再出现一部分页面是星桥，一部分页面像默认后台的割裂感。
  - 验证方式：
    - 多页面截图对比通过。

- [x] 17. 固化素材来源记录与生成资产流程
  - 目标：
    - 真正建立品牌资产 provenance 记录习惯。
    - 明确哪些资产是自生成、哪些是外部来源、哪些只是本地评审产物。
  - 交付物：
    - `docs/ASSET_SOURCES.md` 更新
    - 相关生成记录或说明
  - 完成标准：
    - 每个进入仓库的外部视觉素材都能追溯来源和许可。
  - 验证方式：
    - `docs/ASSET_SOURCES.md` 可覆盖新增素材。

- [x] 18. 做性能、可访问性与低运动模式审计
  - 目标：
    - 确认品牌效果没有把产品变慢、变花或变得不可访问。
  - 交付物：
    - 性能/可访问性审计结果
  - 完成标准：
    - 动效、背景、鼠标系统和图标替换都有合理退化策略。
  - 验证方式：
    - 构建通过，关键交互无明显掉帧，键盘/对比度/可读性检查通过。

- [x] 19. 做跨 surface 截图 QA 与最终 polish sweep
  - 目标：
    - 统一复查所有高频页面，修复溢出、重叠、过度装饰、文案冗余和风格不一致问题。
  - 交付物：
    - 最终品牌截图集
    - UI polish 报告
  - 完成标准：
    - 星桥品牌系统在多个 surface 上稳定一致。
  - 验证方式：
    - 多 viewport 截图索引和 polish 报告可追踪。

- [x] 20. 汇总品牌系统第一轮结论并制定下一轮入口
  - 目标：
    - 汇总完成步骤、品牌规则、素材来源、截图证据、剩余风险和下一轮建议。
  - 交付物：
    - 第一轮品牌系统总结文档
  - 完成标准：
    - 后续 agent 能直接从总结文档和当前进度接着做，而不是重新理解风格方向。
  - 验证方式：
    - 本计划当前进度标为 `20/20`，总结文档可解析，公开素材记录清晰，下一轮入口明确。

## 当前进度

- 当前阶段：`step_20_completed`
- 已完成步骤：`20 / 20`
- 下一步入口：`本轮已完成；如继续品牌系统工作，请先读 docs/BRAND_SYSTEM_ROUND1_SUMMARY.md 的“Next Round Entry”。`
- 当前结论：
  - 星桥品牌方向应是“克制的专业观测台”，不是大面积科幻装饰。
  - 品牌识别应优先来自 token、边界、图标、轻量背景和状态动效，而不是卡片堆叠。
  - 生图工具可以作为品牌资产首选来源；公开素材仅在 license 明确且 file-level 校验通过时允许进入仓库。
  - 真正进入仓库的外部品牌素材必须同步写入 `docs/ASSET_SOURCES.md`。
  - 当前高频 surface 的品牌弱点已经完成基线记录：左侧栏偏通用、顶栏匿名、主任务区无品牌边界、右侧浏览器/文件面板缺少星桥语言、设置页高度碎片化、窄宽度下 metadata pills 噪声偏高。
  - 品牌 token 已在 `apps/astrabridge-desktop/src/styles.css` 建立第一版稳定层，并补充 `docs/BRAND_TOKENS.md` 作为后续步骤的消费规则。
  - shell 默认底色已从暖白调整到浅蓝观测台基线，侧栏、顶栏菜单、inspector tab 和基础交互态开始共享统一 token 语言。
  - 半透明星图壁纸系统已经以纯 CSS 程序化方式落地，包含冷光、稀疏星点和低对比连线三层，并区分 root / sidebar / settings / empty-state 的强度。
  - launch isolation 阻断页已修正为位于壁纸前景层之上，空态/守卫态不会再被全局背景覆盖成不可读页面。
  - Step 5 已建立并回修第一版“星桥边界”原语：银蓝色 surface frame、控制边缘、行项/分段切换边缘，以及右下角语义星座组件；当前版本已经去掉椭圆底色，改为基于真实猎户座轮廓的“基底连线 + 沿线流动光晕 + 发光星点 + 星屑拖尾”表达。设置页与守卫页使用统一的低对比边界语言，而不再依赖单独的蓝色折线贴图；右栏星座已因空间密度原因回退。
  - Step 6 已把左侧栏和顶部 chrome 提升为更明确的星桥品牌入口：侧栏新增品牌头、观测台副标题、统一的银蓝边界导轨与更工程化的导航图标；顶部菜单和动作区收口为更轻的品牌线条与控件层次。展开态与收起态截图均通过，信息密度未下降。
  - Step 8 已把状态、审查、浏览器、文件四个 inspector tab 收口为统一的“观测面板”风格：右栏整体退回到一块克制的观察表面，列表行、详情区、diff 画布、文件画布和浏览器工作台共享更轻的边界语义，不再退回卡片堆叠。
  - Step 9 已把图标系统从零散替换推进到可执行规范：`docs/BRAND_ICON_SYSTEM.md` 固化了星桥图标的语义家族、禁用风格、几何和状态规则，`docs/BRAND_ICON_REPLACEMENT_MATRIX.md` 列出了一级导航、高频控制、状态入口和模式切换的 Tier 1 替换矩阵，并明确把 `●`、`□`、`✎`、`×`、`↑` 等 raw Unicode UI 符号列为 P0 清理对象。
  - Step 10 已把第一眼可见区的图标替换成第一批星桥图标家族：左侧栏、项目/任务树、顶栏高频动作、permission / workflow 模式触发器、附件入口、语音按钮、发送按钮，以及 inspector 四个入口 tab 已接入统一的 silver-blue outline 语义；`●`、`□`、`✎`、`×`、`↑` 这批高可见 raw Unicode UI 符号已从主路径中移除。
  - Step 12 已把“点亮星座”等待态绑定到真实运行阶段：主任务区 runtime guard 现在会跟随思考、工具/多模态、联网、文件编辑、自动化与审批状态切换文案与轨迹；同时补入 `brand_waiting_replay` smoke 入口，允许在主界面按真实 runtime state shape 回放 thinking / tools / web / files / automation / approval 六种阶段用于截图验收。
  - Step 19 已用当前 headless capture 重新复核主任务区、审查、浏览器、文件和窄宽度布局，并结合 Step 18 的设置页与键盘焦点证据，确认当前品牌系统在高频 surface 上没有明显的重叠、溢出、过度装饰或风格回退；对应截图与报告索引位于 `PRIVATE/brand-system/reports/step19-polish-20260704.md`。
  - Step 13 已建立第一版 app 内部 cursor enhancement：新增固定定位的 `StarbridgeCursorOverlay`，默认态使用轻量银蓝光晕与星点拖尾，hover 态增强边环与辉光，drag 态转为沿拖拽方向拉伸的星轨；文本编辑态则收敛为不遮挡 I-beam 的窄向高光，并通过 `requestAnimationFrame` 平滑坐标更新、`pointer-events: none` 和 `(pointer: fine)` / `prefers-reduced-motion` 约束保持性能与可操作性。
  - Step 14 已把鼠标系统收口为可配置、可降级的品牌增强层：新增 `cursor_enhancement` 项目偏好并贯通 sidecar 默认值/规范化、桌面端 store 持久化与设置页入口；`StarbridgeCursorOverlay` 现在会根据 `prefers-reduced-motion`、fine pointer、`saveData`、`hardwareConcurrency` 和 `deviceMemory` 在 `full / economy / minimal / hidden` 四档之间退化，且用户可在普通设置页直接切换 `自动 / 关闭`，不再把星桥鼠标效果做成强制品牌负担。
  - Step 15 已把浏览器 surface 收口为真正属于星桥的瘦高浏览器工作台：右栏浏览器页现在使用更薄的 workbench tabs、紧凑地址栏、成组导航按钮和带 `StarbridgeBrowserIcon` 的 surface 标题栏；同时修正了 inspector 内容壳与 `browser-webview-stage` 不参与纵向伸展的问题，使浏览器预览真正吃满右栏高度，在高纵横比下会自动切到 `手机入口` / mobile entry，并能在同一品牌框架下展示真实网页。
  - Step 16 已把文件、审查、设置与认证 surface 收口回同一套星桥语言：`InspectorPanels.tsx` 为 review/files 面板补齐当前对象信息与更清晰的工作区头；`App.tsx` 把 users / providers / models 管理页统一回 `manager-hero + list/detail` 结构，`styles.css` 则继续削薄 settings 侧栏偏好区、provider/model 列表、metadata 区块和 manager 行项，去掉默认后台式的厚卡片感。当前 settings / login / users / providers / keys / models / review / files 多页面截图已形成前后对照证据。
  - Step 17 已把品牌资产 provenance 从隐含事实固化成显式记录：`docs/ASSET_SOURCES.md` 现已区分 repository visual asset inventory、programmatic brand assets、local-only artifacts 与 future provenance workflow，并明确 `brand/icon-source.svg`、favicon、`brand-constellation.svg` 和 legacy bootstrap raster 的来源边界；同时新增 `PRIVATE/brand-system/reports/step17-asset-provenance-20260704.md` 作为本轮资产盘点记录，确认当前 Starbridge 品牌系统没有引入第三方外部视觉素材。
  - Step 18 已完成第一轮品牌性能 / 可访问性 / 低运动模式审计：`StarbridgeCursorOverlay.tsx` 现已把 cursor overlay 的常驻 `requestAnimationFrame` 循环改成按需启动与收敛后停止，`styles.css` 则把 reduced-motion 覆盖面扩展到 composer beacon halo、录音 pulse、activity shimmer 与 diff number-pop 等次级动效；同时在 `PRIVATE/brand-system/reports/step18-performance-accessibility-audit-20260704.md` 中汇总主界面、设置页、键盘 Tab 链与构建 / 测试证据，确认当前品牌层没有因为装饰而破坏可读性或基本键盘可达性。
  - 后续执行按“一轮一步”推进，并持续截图复核 UI 美观与信息密度。
  - Step 20 已把第一轮结论、规则、素材来源、截图证据、剩余风险和下一轮入口汇总到 `docs/BRAND_SYSTEM_ROUND1_SUMMARY.md`。后续 agent 不应再从 Step 1 重新理解品牌方向，而应从该总结文档和完成状态 `20 / 20` 继续。
- 动态调整状态：
  - 允许后续 agent 根据实施情况微调步骤顺序、拆分局部原型或调整具体样式优先级，
  - 但不得放弃以下核心目标：
    - 星桥专属品牌识别
    - 低干扰高效率工作流
    - 可追溯素材许可边界
    - 高频截图 QA
    - 每轮只完成一步的执行纪律

## 完成记录

- 2026-07-04：完成步骤 `20`。新增 `docs/BRAND_SYSTEM_ROUND1_SUMMARY.md`，将本轮品牌系统工作正式收口为一个可交接入口：汇总了 Round 1 的完成状态、已建立的品牌规则、规范文档入口、截图 / 报告证据索引、当前资产 provenance 状态、剩余风险，以及下一轮建议入口。同步把本计划更新为 `20 / 20`，并将未来入口显式指向该总结文档的 “Next Round Entry” 部分，避免后续 agent 从旧步骤重新理解方向。当前结论是：Starbridge 第一轮品牌系统已经从“风格探索”进入“可追溯、可复查、可继续执行”的稳定基线。
- 2026-07-04：完成步骤 `19`。使用 `node scripts/capture_astrabridge_page.mjs` 针对当前应用生成新的跨 surface 证据集，覆盖 `PRIVATE/brand-system/screenshots/step19-polish-20260704/review.png`、`browser.png`、`files.png`、`main-narrow.png`，并产出对应 capture 报告 `PRIVATE/brand-system/reports/step19-review.json`、`step19-browser.json`、`step19-files.json`、`step19-main-narrow.json`。本轮逐张复核主任务区 + review inspector、browser inspector、files inspector 与窄宽度布局，同时复用 Step `18` 的 `settings-overview.png` 与 `keyboard-focus.png` 作为未改动 surface 的支持证据；四份 Step `19` capture 报告均返回 `ok: true`、`http_status: 200`、`console_issues: []`、`request_failures: []`。最终在 `PRIVATE/brand-system/reports/step19-polish-20260704.md` 落盘截图索引与 polish 结论：当前高频 surface 未发现必须继续回修的 overflow / overlap / card-heavy fallback / over-decoration 问题，因此本步以 QA 收口，不额外引入新的 CSS churn。下一步入口为步骤 `20`。
- 2026-07-04：完成步骤 `18`。在 `apps/astrabridge-desktop/src/features/brand/StarbridgeCursorOverlay.tsx` 中把品牌鼠标层的常驻 `requestAnimationFrame` 改为按需队列：只有发生 pointer 活动时才启动帧循环，blur / hide 时会取消，光标头 / 拖尾收敛后不再继续空转；并在 `apps/astrabridge-desktop/src/features/brand/StarbridgeCursorOverlay.test.tsx` 中新增回归测试，确认 overlay 不会在静止时无条件启动帧循环。在 `apps/astrabridge-desktop/src/styles.css` 中扩展 `prefers-reduced-motion: reduce` 的覆盖面，额外关闭 composer beacon halo 呼吸、录音 pulse、activity shimmer 与 diff number-pop 这些次级动效，避免 reduced-motion 只覆盖“主星座”而漏掉周边动画。验证通过 `npm.cmd test -- src/features/brand/cursorEnhancement.test.ts src/features/brand/StarbridgeCursorOverlay.test.tsx src/features/brand/ComposerStarTrack.test.tsx src/features/brand/StarbridgeCornerConstellation.test.tsx src/features/brand/StarbridgeWaitingConstellation.test.tsx` 与 `npm.cmd run build`。审计报告位于 `PRIVATE/brand-system/reports/step18-performance-accessibility-audit-20260704.md`；主界面、设置页和键盘焦点截图分别位于 `PRIVATE/brand-system/screenshots/step18-audit-20260704/main-default.png`、`settings-overview.png`、`keyboard-focus.png`，对应 capture / focus 报告位于 `PRIVATE/brand-system/reports/step18-main-default.json`、`step18-settings-overview.json`、`step18-keyboard-focus.json`。当前结论是：品牌层已具备更完整的 reduced-motion 与 idle-cost 退化策略，下一步入口为步骤 `19`。
- 2026-07-04：完成步骤 `17`。更新 `docs/ASSET_SOURCES.md`，把当前品牌资产来源从“未来如有新增再记录”改为可执行库存：明确 `brand/icon-source.svg` 是 app icon 家族的 canonical source，列出 `icons/**` 与 `src-tauri/icons/**` 的导出关系，补入 `apps/astrabridge-desktop/public/favicon.svg`、`apps/astrabridge-desktop/src/assets/brand-constellation.svg` 与 `apps/astrabridge-desktop/src-tauri/icons/local-codex-router-icon.png` 的 provenance / usage 边界；同时新增 programmatic brand assets 与 provenance workflow，明确哪些是代码生成、哪些是本地评审产物、哪些未来必须同步记录 source URL 与 file-level license。另新增本地记录 `PRIVATE/brand-system/reports/step17-asset-provenance-20260704.md`，汇总本轮 brand asset 盘点结论，并保存当前主界面回归截图 `PRIVATE/brand-system/screenshots/step17-asset-provenance-20260704/main-sanity.png` 作为无 UI 回退的 sanity evidence。当前结论是：活跃 Starbridge 品牌系统仍未引入第三方外部视觉素材，后续若新增外部资产，必须在同一轮更新 `docs/ASSET_SOURCES.md`。下一步入口为步骤 `18`。
- 2026-07-04：完成步骤 `16`。在 `apps/astrabridge-desktop/src/features/runtime/InspectorPanels.tsx` 中为审查与文件面板补齐更明确的当前文件信息：review 当前文件区现在同时显示文件状态缩写，files 面板补入工作区/当前对象头信息，避免右栏只有一块无语义空白画布；在 `apps/astrabridge-desktop/src/App.tsx` 中将 users / providers / models 管理页统一回 `manager-hero + list/detail` 的品牌壳层，并为 keys 空态补入明确提示；在 `apps/astrabridge-desktop/src/styles.css` 中继续削薄 settings 侧栏偏好区、provider/model 列表、metadata 区块和 manager 行项，移除默认后台式的厚卡片语义，使设置与认证入口和主壳层、右栏观测面板回到同一套星桥边界语言。验证通过 `npm.cmd test -- src/features/runtime/InspectorPanels.test.tsx src/features/navigation/SetupLandingPanel.test.tsx src/features/navigation/ViewWorkspacePanel.test.tsx` 与 `npm.cmd run build`。截图证据位于 `PRIVATE/brand-system/screenshots/step16-surface-after-20260704/`，覆盖 `review-after.png`、`files-after.png`、`settings-overview-after.png`、`login-after.png`、`users-after.png`、`providers-after.png`、`keys-after.png`、`models-after.png`，并与 `PRIVATE/brand-system/screenshots/step16-surface-baseline-20260704/` 形成前后对照；对应采集报告位于 `PRIVATE/brand-system/reports/step16-*.json`。下一步入口为步骤 `17`。
- 2026-07-04：完成步骤 `15`。在 `apps/astrabridge-desktop/src/features/runtime/InspectorPanels.tsx` 延续浏览器 surface 的品牌化收口：workbench tab 标题、浏览器标题栏、compact toolbar、导航按钮分组、surface mode/detail chips 和空态图标都统一接入星桥图标与银蓝边界语言；同时在 `apps/astrabridge-desktop/src/styles.css` 修正 `inspector-scroll-shell` 与 `browser-webview-stage` 的纵向伸展关系，让浏览器预览不再塌成顶部小块，而是吃满右栏高度并更稳定触发 tall/narrow 场景下的 mobile entry。验证通过 `npm.cmd test -- src/features/runtime/InspectorPanels.test.tsx` 与 `npm.cmd run build`。截图证据包括桌面态 `PRIVATE/brand-system/screenshots/step15-browser-surface-20260704/browser-realpage.png` 与最终竖向 mobile entry 实页 `PRIVATE/brand-system/screenshots/step15-browser-surface-20260704/browser-realpage-wiki-v3.png`，对应采集报告位于 `PRIVATE/brand-system/reports/step15-browser-realpage.json` 与 `PRIVATE/brand-system/reports/step15-browser-realpage-wiki-v3.json`。下一步入口为步骤 `16`。
- 2026-07-04：完成步骤 `14`。新增 `apps/astrabridge-desktop/src/features/brand/cursorEnhancement.ts` 与 `cursorEnhancement.test.ts`，把鼠标增强偏好统一为 `auto / off`，并在 `apps/astrabridge-sidecar/astrabridge_sidecar/project_service.py`、`apps/astrabridge-sidecar/tests/test_sidecar_services.py`、`apps/astrabridge-desktop/src/store.ts`、`apps/astrabridge-desktop/src/types.ts`、`apps/astrabridge-desktop/src/api.ts` 中补齐项目默认值、规范化、持久化和前端接口；`apps/astrabridge-desktop/src/features/brand/StarbridgeCursorOverlay.tsx` 与 `apps/astrabridge-desktop/src/styles.css` 现已支持 `full / economy / minimal / hidden` 四档渲染质量，并根据 reduced motion、save-data 和低硬件提示自动退化。`apps/astrabridge-desktop/src/App.tsx` 同步把鼠标光效开关放进 launcher、设置侧栏偏好和普通“设置”落地页，保证用户不进入细页也能直接关闭。验证通过 `npm.cmd test -- src/features/brand/cursorEnhancement.test.ts src/features/brand/StarbridgeCursorOverlay.test.tsx src/features/brand/ComposerStarTrack.test.tsx src/features/brand/StarbridgeCornerConstellation.test.tsx src/features/brand/StarbridgeWaitingConstellation.test.tsx`、`python -m unittest discover -s apps/astrabridge-sidecar/tests -p test_sidecar_services.py -k runtime_preferences`、`python -m unittest discover -s apps/astrabridge-sidecar/tests -p test_sidecar_services.py -k legacy_runtime_defaults` 与 `npm.cmd run build`。in-app 浏览器验收确认顶栏“设置”页已显示 `鼠标光效` 开关，关闭态会移除 overlay DOM，证据位于 `PRIVATE/brand-system/screenshots/step14-cursor-controls-20260704/settings-cursor-off.png` 与 `settings-cursor-auto.png`。下一步入口为步骤 `15`。
- 2026-07-04：完成步骤 `13`。新增 `apps/astrabridge-desktop/src/features/brand/StarbridgeCursorOverlay.tsx` 与 `StarbridgeCursorOverlay.test.tsx`，建立星桥第一版自定义鼠标强调层：默认态、hover 态、drag 态与 text 态共用一套银蓝星点语义，交互坐标通过 `requestAnimationFrame` 驱动而不直接用 React 重渲染鼠标移动；在 `apps/astrabridge-desktop/src/App.tsx` 中把 overlay 接到 launcher、主应用、等待态预览和 launch-isolation guard 入口，在 `apps/astrabridge-desktop/src/styles.css` 中补入低干扰星屑、光晕、拖拽星轨与 reduced-motion 退化规则。验证通过 `npm.cmd test -- src/features/brand/StarbridgeCursorOverlay.test.tsx src/features/brand/ComposerStarTrack.test.tsx src/features/brand/StarbridgeCornerConstellation.test.tsx src/features/brand/StarbridgeWaitingConstellation.test.tsx` 与 `npm.cmd run build`。连续截图证据位于 `PRIVATE/brand-system/screenshots/step13-cursor-overlay-20260704/cursor-default.png`、`cursor-hover-send.png`、`cursor-text-input.png`、`cursor-drag-grip.png`。下一步入口为步骤 `14`。
- 2026-07-04：完成步骤 `12`。新增 `apps/astrabridge-desktop/src/features/brand/runtimeWaitingState.ts` 与 `runtimeWaitingState.test.ts`，把 live activity / diff / approval / pending 状态统一映射为星桥等待态语义；在 `apps/astrabridge-desktop/src/App.tsx` 中把 runtime guard 从静态文案升级为真实绑定的 `StarbridgeWaitingConstellation`，并补入 `brand_waiting_replay` smoke 回放入口；在 `apps/astrabridge-desktop/src/styles.css` 中补齐 guard 内联布局。验证通过 `npm.cmd test -- src/features/brand/runtimeWaitingState.test.ts src/features/brand/StarbridgeWaitingConstellation.test.tsx` 与 `npm.cmd run build`。运行中与事件回放截图证据分别位于 `PRIVATE/brand-system/screenshots/step12-runtime-binding-20260704/runtime-thinking.png`、`PRIVATE/brand-system/screenshots/step12-runtime-binding-20260704/runtime-files.png`，对应报告为 `PRIVATE/brand-system/reports/step12-runtime-thinking.json` 与 `PRIVATE/brand-system/reports/step12-runtime-files.json`。下一步入口为步骤 `13`。
- 2026-07-03：完成步骤 `11`。新增 `apps/astrabridge-desktop/src/features/brand/StarbridgeWaitingConstellation.tsx`、`StarbridgeWaitingConstellation.test.tsx` 与 `StarbridgeWaitingPreview.tsx`，把等待动效正式抽象成可复用的星桥基础组件：提供 `inline` 与 `panel` 两个等待形态，并预留 `thinking / tools / web / files / automation / approval` 六种阶段语义；同时在 `apps/astrabridge-desktop/src/App.tsx` 中加入受控 query 入口 `brand_waiting_preview=1`，用于本地切换等待阶段而不提前侵入真实运行绑定。实现过程中还修复了品牌根背景伪元素覆盖预览内容的问题，通过为预览壳层建立独立 stacking context 保证 smoke 页可读。验证证据包括 `PRIVATE/brand-system/screenshots/step11-waiting-state-20260703/preview-thinking.png`、`PRIVATE/brand-system/screenshots/step11-waiting-state-20260703/preview-files.png`、`PRIVATE/brand-system/reports/step11-waiting-preview-thinking.json`、`PRIVATE/brand-system/reports/step11-waiting-preview-files.json`，以及 `npm.cmd test -- src/features/brand/StarbridgeWaitingConstellation.test.tsx src/features/brand/ComposerStarTrack.test.tsx src/features/brand/StarbridgeCornerConstellation.test.tsx`、`npm.cmd run build`。下一步入口为步骤 `12`。
- 2026-07-03：完成步骤 `10`。新增 `apps/astrabridge-desktop/src/features/brand/StarbridgeIcons.tsx` 与 `StarbridgeIcons.test.tsx`，建立第一批星桥图标家族，并将其接入左侧栏一级导航、项目/任务树、顶部 `压缩上下文` / `创建分支任务` 动作、permission / workflow 模式切换、附件入口、语音转写、发送按钮，以及 inspector 的 `状态 / 审查 / 浏览器 / 文件` 四个入口。主路径中此前最刺眼的 raw Unicode UI 符号 `●`、`□`、`✎`、`×`、`↑` 已被移除，`workflow goal` 也不再复用普通 send-arrow 语义。验证证据包括 `PRIVATE/brand-system/screenshots/step10-tier1-icons-20260703/main-headless.png`、`PRIVATE/brand-system/reports/step10-tier1-icons-main.json`、`npm.cmd test -- src/features/brand/StarbridgeIcons.test.tsx`，以及 `npm.cmd run build`。下一步入口为步骤 `11`。
- 2026-07-03：完成步骤 `9`。新增 `docs/BRAND_ICON_SYSTEM.md` 与 `docs/BRAND_ICON_REPLACEMENT_MATRIX.md`，正式固化星桥图标系统规范：明确了图标几何、色彩、语义家族、禁用风格、替换规则，以及覆盖一级导航、高频控制、状态入口和模式切换的 Tier 1 替换矩阵。该矩阵已把当前最需要清理的 raw Unicode UI 符号 `●`、`□`、`✎`、`×`、`↑` 标为 P0，并将 workflow `goal` 与 composer `send` 的语义冲突列入优先修复项。视觉盘点证据补充为 `PRIVATE/brand-system/screenshots/step9-icon-system-20260703/main-live.png`。下一步入口为步骤 `10`。
- 2026-07-03：完成步骤 `8`。在 `apps/astrabridge-desktop/src/features/runtime/InspectorPanels.tsx` 与 `apps/astrabridge-desktop/src/styles.css` 中把右侧 inspector 收口为统一的“观测面板”样式：状态、审查、浏览器、文件四个 tab 共享更轻的壳层、导轨、分隔线和行项语义，保留 canvas / stage 优先与信息压缩，不再回退为厚卡片堆叠；同时让文件空态不再重复渲染无意义的 workspace 顶栏。验证证据包括 `PRIVATE/brand-system/screenshots/step8-inspector-20260703/after-status.png`、`PRIVATE/brand-system/screenshots/step8-inspector-20260703/after-review.png`、`PRIVATE/brand-system/screenshots/step8-inspector-20260703/after-browser.png`、`PRIVATE/brand-system/screenshots/step8-inspector-20260703/after-files.png`、`PRIVATE/brand-system/screenshots/step8-inspector-20260703/after-narrow-files.png`，以及 `npm.cmd run build`。下一步入口为步骤 `9`。
- 2026-07-03：完成步骤 `7`。在 `apps/astrabridge-desktop/src/App.tsx` 与 `apps/astrabridge-desktop/src/styles.css` 中为主任务区与 composer 建立更克制的品牌基底：主任务区加入轻量壳层、细高光与更安静的消息流边界，空态被收口为低噪声居中面板，消息元信息与分隔线改为更轻的观测台语义；composer 统一为薄边界、浅银蓝底、柔和聚焦态与更明确的品牌发送按钮，同时保持模式切换和模型控件的高频可读性。验证证据包括 `PRIVATE/brand-system/screenshots/step7-main-composer-20260703/baseline-main.png`、`PRIVATE/brand-system/screenshots/step7-main-composer-20260703/main-after.png`、`PRIVATE/brand-system/screenshots/step7-main-composer-20260703/draft-state.png`、`PRIVATE/brand-system/screenshots/step7-main-composer-20260703/sending-state.png`、`PRIVATE/brand-system/screenshots/step7-main-composer-20260703/empty-state.png`，以及 `npm.cmd run build`。下一步入口为步骤 `8`。
- 2026-07-03：完成步骤 `6`。在 `apps/astrabridge-desktop/src/App.tsx` 与 `apps/astrabridge-desktop/src/styles.css` 中完成左侧栏与顶部 chrome 的品牌化收口：左栏新增 AstraBridge 品牌头与“观测台”副标题，项目/任务列表补齐统一的银蓝导轨语义，并用一致的导航图标替换通用文本符号；顶部菜单加入更轻的下划线激活语义，动作区按钮统一到更克制的品牌控件层。验证包括 `PRIVATE/brand-system/screenshots/step6-sidebar-topbar-20260703/main-expanded.png`、`PRIVATE/brand-system/screenshots/step6-sidebar-topbar-20260703/main-collapsed.png`、定向测试 `ProjectTaskTree.test.tsx` / `ComposerStarTrack.test.tsx` / `StarbridgeCornerConstellation.test.tsx`，以及 `npm.cmd run build`。下一步入口为步骤 `7`。

- 2026-07-03: Step `5` refinement. Added a dedicated composer star-track primitive so the main input shell itself acts as a restrained live route surface: new `ComposerStarTrack` component, composer rail state wiring in `App.tsx`, lower-edge rail motion in `styles.css`, reduced-motion coverage, and a matching update in `docs/BRAND_EDGE_PRIMITIVES.md`. Verified with targeted brand tests, `npm.cmd run build`, and a live in-app browser reload. Next entry remains Step `6`.

- 2026-07-03：步骤 `5` 六次回修。按最新反馈删除主界面右侧 inspector 的星座装饰，右栏保留紧凑信息优先。同步修复主对话框出界问题：`chat-canvas` 采用四行 grid，但此前未给 notice / guard / stream / composer 显式分配 grid-row，导致在 guard 缺席时 `composer` 被错误挤进弹性行并塌缩到十几像素；现已固定各区块行位。此轮仍不推进步骤 `6`，下一步入口保持为步骤 `6`。
- 2026-07-03：步骤 `5` 五次回修。将猎户座星座引入主界面右侧 inspector，并把右栏结构收口为“固定 tabbar + 可滚动内容壳”，使星座可以稳定贴在右栏底层。新增 inspector 专用自适应版本，基于右栏宽度自动调整尺寸、位置和可见度，避免压住状态信息。此轮仍不推进步骤 `6`，下一步入口保持为步骤 `6`。
- 2026-07-03：步骤 `5` 四次回修。根据最新反馈，将 settings 页右下角猎户座整体缩小并下移，避免上沿压到 UI；同时在不遮挡主界面的前提下略微提高整体可见度。此轮仍不推进步骤 `6`，下一步入口保持为步骤 `6`。
- 2026-07-03：步骤 `5` 三次回修。根据最新 live 验收反馈，继续加强猎户座的静态基底连线，并单独提升下沿基座线与腰带线的线宽、亮度和可见度；星形结构保持不变。此轮仍不推进步骤 `6`，下一步入口保持为步骤 `6`。
- 2026-07-03：步骤 `5` 二次回修。根据进一步验收反馈，将右下角语义星座从自定义结构替换为可识别的真实著名星座轮廓，当前采用猎户座（双肩、三星腰带、双足、下垂剑）的简化结构；同时继续强化结节点星形的可见度。此轮仍不推进步骤 `6`，下一步入口保持为步骤 `6`。
- 2026-07-03：步骤 `5` 回修。基于 live 页面验收反馈，去掉右下角星座装饰下方的椭圆底色，强化了“可见基底连线 + 沿线流动光晕 + 发光星点 + 星屑拖尾”的组合表达，并把节点星形改为更明确的银色多尖星。此轮不推进步骤 `6`，下一步入口仍为步骤 `6`。
- 2026-07-03：完成步骤 `5`。建立第一版“星桥边界”基础样式原语：在 `apps/astrabridge-desktop/src/styles.css` 增加银蓝色 surface frame、control edge、row/tab edge 规则，提升按钮、输入框、设置导航项和主要面板的统一边界语言；新增 `apps/astrabridge-desktop/src/features/brand/StarbridgeCornerConstellation.tsx` 与测试，做出具有“relay bridge / handoff”语义的右下角星座组件，使用银色节点、低对比连线、方向性流转和星屑拖尾，并在 `prefers-reduced-motion` 下退化为静态星图。`App.tsx` 已将该组件挂载到 settings 和 launch-isolation surface；`docs/BRAND_EDGE_PRIMITIVES.md` 记录了这套原语。验证包括组件测试、`npm.cmd run build`、受控 in-app 浏览器实时检查，以及两帧 live browser 截图的二进制差异确认动效真实存在。下一步从步骤 `6` 开始改造左侧栏与顶部 chrome。
- 2026-07-03：步骤 `4` 可见性复核。由于用户指出“稀疏星点”和“低对比连线”在截图中不够可感知，本轮没有前进到步骤 `5`，而是回到步骤 `4` 继续加强 settings / launch-isolation surface 的显式 constellation overlay，新增 `apps/astrabridge-desktop/src/assets/brand-constellation.svg`，并复核 `PRIVATE/brand-system/screenshots/wallpaper-visibility-tune-20260703/settings-overview-v5.png` 与 `PRIVATE/brand-system/screenshots/wallpaper-visibility-tune-20260703/launch-isolation-v5.png`。当前结论更新为：主任务区继续保持克制，设置页与守卫页已经能直接看到浅蓝星点和连线，Step `4` 证据通过，下一步仍从步骤 `5` 开始。
- 2026-07-03：完成步骤 `1`。新增 `PLAN/ASTRABRIDGE_BRAND_SYSTEM_EXECUTION_PLAN.md`，把星桥专属风格执行路线固化为 20 步计划，明确了总目标、注意事项、公开素材与版权边界、风格细节、顺序步骤、当前进度，以及“每轮从下一未完成步骤开始且每轮只完成一步”的执行约束；同时基于公开官方资料确认了 NASA 媒体指南、Wikimedia Commons 复用指引和 Unsplash License 可作为后续素材边界参考，但真正落地任何单个外部素材时仍需在当轮做 file-level 许可复核。
- 2026-07-03：完成步骤 `2`。使用 `node scripts/capture_astrabridge_page.mjs` 对当前 AstraBridge UI 做品牌基线截图，覆盖主任务壳、设置概览、右侧浏览器 inspector、右侧文件 inspector 和 390px 窄宽度堆叠布局；截图位于 `PRIVATE/brand-system/screenshots/step2-brand-baseline-20260703/`，原始采集位于 `PRIVATE/brand-system/raw/step2-*.json`，报告位于 `PRIVATE/brand-system/reports/step2-brand-baseline.json` 与 `.md`，验证位于 `PRIVATE/brand-system/validations/step2-brand-baseline-validation.json`。本步确认九类高优先级品牌问题：缺少专属色盘、缺少星图背景层、边界语言通用、图标不一致、metadata pill 过多、设置页碎片化、浏览器面板割裂、文件面板过于冷白、以及缺少签名式等待/鼠标动效。下一步从步骤 `3` 开始建立星桥品牌 token 系统。
- 2026-07-03：完成步骤 `3`。在 `apps/astrabridge-desktop/src/styles.css` 建立第一版星桥品牌 token 系统，分为 brand palette、material、semantic app 和 shell interaction 四层；将默认 shell 基线从暖白切换为浅蓝观测台方向，并把侧栏、导航行、菜单弹层、计数胶囊、inspector tab 等高频 chrome 映射到统一 token。新增 `docs/BRAND_TOKENS.md` 记录 token 分层和消费规则；用 `npm.cmd run build` 完成构建验证，并通过 `node scripts/capture_astrabridge_page.mjs` 复核主壳、设置页和浏览器 inspector 截图，确认本步实现了冷静统一的基础品牌语言，但尚未进入壁纸、图标、鼠标和等待态阶段。下一步从步骤 `4` 开始建立半透明星座壁纸系统。
- 2026-07-03：完成步骤 `4`。在 `apps/astrabridge-desktop/src/styles.css` 建立第一版半透明星图壁纸系统，使用纯 CSS 生成三层背景：冷光 base、稀疏星点 star field、低对比 constellation lines，并通过 `#root::before` / `#root::after` 落到全局背景层；同时为 sidebar、settings workspace、launcher / launch-isolation、empty-state 等 surface 添加更强但仍克制的局部壁纸强度。新增 `docs/BRAND_WALLPAPER_SYSTEM.md` 记录三层模型、surface 强度规则和约束；构建验证通过 `npm.cmd run build`，截图复核覆盖主任务壳、设置页、390px 窄宽度、launch isolation 阻断页和文件侧面板。执行中顺手修复了一个真实回归：launch isolation 页此前未被提升到壁纸前景层，会被全局背景压成不可读；现已恢复为可见守卫态。下一步从步骤 `5` 开始建立“星桥边界”基础样式原语。
