# DESIGN.md — 设计系统参考

本项目的外观 / UI 生成遵循 [awesome-design-md](https://github.com/VoltAgent/awesome-design-md)
的设计语言体系。

## 这是什么

awesome-design-md 是一份从真实网站提取的 DESIGN.md 设计系统合集（74 款），
每款包含色板（Color Palette）、字体（Typography）、组件样式、布局原则、
阴影层级等完整 token。把任意一款 DESIGN.md 放进项目后，告诉 AI agent
"build me a page that looks like this"，即可生成风格一致的 UI。

## 本地合集（直接引用）

- 合集放在与本项目同级的共享目录：`../awesome-design-md/design-md/`
- 每款风格是一个子文件夹，如 `../awesome-design-md/design-md/claude/DESIGN.md`
- 原始仓库：https://github.com/VoltAgent/awesome-design-md

## 使用方法

1. 从 `../awesome-design-md/design-md/` 里挑一款风格（子文件夹名即风格名）。
2. 直接引用该路径（如 `../awesome-design-md/design-md/stripe/DESIGN.md`），
   或把该风格的 DESIGN.md 复制到本项目根目录（与本文件并列即可）。
3. 告诉 agent 使用该设计系统生成页面。
4. 同一项目内保持风格统一，不要混用多款。

## 渲染器对接（scripts/md_to_pdf.py）

讲义 PDF 的视觉样式直接读取合集里所选风格的 YAML token 前端块
（colors / typography / rounded），**不再参考 ESL Assistant 样式**。

    python scripts/md_to_pdf.py --design claude "Spoken/Animals and pets.md"
    python scripts/md_to_pdf.py --design notion --questions-only "Spoken/Discussion on Education.md"

- 风格名 = `design-md/` 下的子文件夹名；默认 `cal`（偏黑白色调）。
  其他黑白风格可直接切换：`wired` / `figma` / `uber` / `mintlify` 等。
- 合集 74 款中 64 款带结构化 YAML token，可自动套用；其余 10 款
  （kraken / lamborghini / lovable / mastercard / runwayml / sanity /
  spotify / starbucks / tesla / theverge）无 token，无法自动渲染。
- token 映射：canvas→页面底色，ink→标题/强调文字，body→正文，
  muted→辅助文字与页码，hairline→边框，primary→强调色（标题下划线、
  提示标签、题号），display 字体→标题，body 字体→正文。
- 中文字体统一为微软雅黑：WeasyPrint 通过 fontconfig 找字体，认不出
  macOS 上随 Office 一起装的那份 msyh.ttc，所以渲染器会自己定位
  msyh.ttc / msyhbd.ttc（macOS 从 `/Applications/Microsoft Word.app/
  Contents/Resources/DFonts` 等处，Windows 找 `C:\Windows\Fonts`），
  再用 @font-face 注册 `Microsoft YaHei`；找不到就回落到系统自带的中文
  字体（macOS 上是冬青黑体 Hiragino Sans GB）。设计系统里的拉丁字体
  （cal 的 Inter）没装时，英文也一起落到同一款中文字体上。
- 字体嵌入按需生效，改字体不用动各份讲义：所有版式都由 `font_stack`
  和各 `*_css()` 函数统一注入，正文、表格、讨论页、四宫格、趋势页
  以及 --trend 的文字宽度测算都读同一份字体文件。
- 表格按解析到的列数渲染，不再截断成两列：第 1 列是标签列（**每张表各按
  自己的内容定宽**，标签尽量排在一行），其余列等分。单元格写成 `**文字**`
  时会渲染为带浅灰底的表头格，该行同时成为 `<thead>`，**跨页时在每页重复**。
- 中文词组不会被拆行（`露营` 不会变成 `露` / `营`）：表格、`--notes`、纯讨论
  题三种版式都适用；只有 ≤6 字的中文串设为不断行，更长的中文仍可换行，
  避免撑破单元格。
- 无问题的表格型词汇表会自动渲染为表格版式 PDF；表格 + 讨论题的混合讲义
  （如 `Spoken/English for WeChat.md`）则第 1 页词汇表、第 2 页讨论。列数
  超过 3 的宽表格也走表格版式（跨页排版，末尾的讨论小节一并渲染），
  如 `Travel/Different Types of TRAVEL.md`。表格版式也会渲染非表格的段落 /
  讨论行，所以「表格 + 句型 + 练习」的讲义（如 `Travel/Discomfort in travel.md`）
  能一次输出完整。
- 表格版式下分节之间禁止分页（`.sec + .sec { break-before: avoid }`），
  避免某一节被整页孤立；页数预算：表格行数多时放宽到 4 页，且若减小字号能
  少一页就选小字号，免得末页只剩一两行。
- 纯讨论题讲义（`--questions-only`）若自动分页会把某组的最后 1 题单独甩到
  第 2 页，渲染器改为在组与组之间换页（取两页题量最接近的分界）；行距两页
  统一，不再逐页拉伸。不需要这个处理时加 `--no-balance`。
- 纯讨论题讲义会把题目文本里的 `**加粗**` 标记去掉再排版，不会字面显示。
  想让每条题目**一行排完、不折行**，写的时候控制在约 80 字符以内；各节题量
  尽量均匀（如 8/7/8/7），两页才会都排得满。
- `--notes` 默认把最后一节当讨论页处理：单独起页，行距撑到页底。末节其实是
  句型 / 词汇练习而不是讨论题时（如 `Travel/At the Restaurant.md`），加
  `--no-disc-page`，让最后一节和其他各节行距一致、也不另起页。
- `--cols2` 把每节的条目排成两列（条目多的清单更省版面、字号更大）：测验类
  讲义（如 `Travel/What kind of Traveler are you.md`，题干一行 + 选项 2×2）
  很合适。只有 1 条的节仍占整幅宽度，不会缩成半栏；两列下每条约需 ≤38 字符
  才不折行。
- 字号偏大时用 `--font-pt` 固定正文字号：默认取「铺满页数预算的最大字号」，
  所以内容少的讲义字号会很大。标题与节标题按正文字号等比缩放（标题 1.7×，
  节标题 1.3×，见 `render_notes_html`），整体一起变小，不会小正文配巨标题。
- 想让**每一节（1、2、3…）之后都留一小段书写空白**、同时仍然铺满 2 页：用
  `--font-pt` 定住字号，再给 `--category-gap-mm` 一个上限。渲染器先取「还排得
  下的最大节间距」，多余的空间才给行距，所以空白落在节与节之间而不是行与行
  之间。例：`--notes --cols2 --no-disc-page --font-pt 10 --category-gap-mm 8`
  → 实测行距 1.0mm、节间距 7.7mm（请求值会被自动收到真正排得下的上限）。
- 排版不留孤行：一条列表内容不会被拆到两页（`li` 设 `break-inside: avoid`）；
  一页放得下的短节整体保持在同一页（`.sec.keep`），避免标题只带一行就断页；
  长节照常跨页，标题靠 `h2 { break-after: avoid }` 始终跟着正文。
  节标题不要用一级 `# `——渲染器只把第一个 `# ` 当文档标题，分节请用 `## `。
- 一张页面塞满时，节标题会紧贴上一节最后一行（节间距被压到约 1.5mm），
  标题下的横线看起来像在给上一节收尾、两块内容糊在一起。这种满页讲义改用
  `--boxes` 给每一节加细边框（同时去掉标题横线），再配 `--font-pt` +
  `--category-gap-mm` 撑开盒间距。例：`--notes --boxes --font-pt 10
  --category-gap-mm 4`（见 `Spoken/Annoying things.md`）。
- 换风格只需改 `--design` 参数；同一项目内保持风格统一，不要混用。

### 图表句型页（`--trend`）

用于「图表常用句型」这类讲义：`Business/BEC-图表常用句型.md`。

- MD 契约：`## 运动` → `**波段**` → `- 英文 — 中文 — 例句`。**每个
  `**波段**` 就是图上的一条色带**，顺序即从左到右：每段占时间轴的
  等分、并分走总量的一部分，所以图上最深的色带，正是下面写「sharply」
  的那一段。波段行可写 `<!-- shape=… -->` 决定这段怎么走
  （`rise`/`fall` 按 1、2、3… 递增坡比，`top_out`/`bottom_out` 抬头后走平，
  `level` 不动，`plateau` 先涨后平）——`平稳` 一节就是这样先平、再抬头。
- 运动名决定整张图的走向（`上升→rise`、`下降→fall`、`波动→wave`、
  `平稳→level`）。`wave` 不按坡比分段，而是画一条**振幅逐渐变大**的
  振荡曲线，因为「波动」没有陡不陡，只有大不大。
- 每条运动**独占一页**（`.cat { break-before: page }`，首页那条用
  `.masthead + .cat` 放行——第一个子元素是页眉不是章节，用 `:first-child`
  会连首页也被推到第 2 页）。页首是一张铺满整幅宽度的折线图
  （12 个月刻度、5 条淡横线、色带由浅到深、线下浅色填充、波段名排在轴下），
  下面是两列条目，**不再有逐条小走势图**——16mm 的小图看不出差别。
- 图高 64mm 固定（viewBox 760×256 缩放到正文宽）。曲线采样 49 点
  （`TREND_CURVE_SAMPLES`）而不是 12 点，否则振荡会被画成十二段折线；
  只有 12 个月位才点圆点。
- 条目区用 `column-fill: balance`——`auto` 会让多栏容器吃掉整页剩余高度，
  空着右半栏。字数少的那几条运动（`波动`、`平稳`）靠**每页各自的行距**
  撑满：`fit_trend_row_pads` 单独渲染这一条运动、量出实际高度，把富余
  的高度摊到行与行之间（`--row-pad` 变量，上限 4mm），所以短名单不会
  在页底留半页空白。装了 pdfplumber 才量得准，没有就退回默认行距。
- 字号由两个条件同时决定：每一行必须一行排完（`text_width_mm` 量，
  超宽就缩字号），且不超页数预算。默认页数 = 运动条数。
- 例句控制在约 58 个字符以内（约 91mm），否则该条会顶出栏宽。
  宽度测算用的字体：Windows 上取 Segoe UI / 雅黑，其他平台回落到
  渲染器实际会用的那款中文字体，所以 macOS 上这道校验也是真的在跑。

## 风格清单（分类摘要）

- AI / LLM：Claude、Cohere、ElevenLabs、Minimax、Mistral、Ollama、OpenCode、Replicate、Runway、Together AI、VoltAgent、xAI
- 开发者工具：Cursor、Expo、Lovable、Raycast、Superhuman、Vercel、Warp
- 后端 / 数据库：ClickHouse、Composio、HashiCorp、MongoDB、PostHog、Sanity、Sentry、Supabase
- 效率 / SaaS：Cal、Intercom、Linear、Mintlify、Notion、Resend、Zapier
- 设计创意：Airtable、Clay、Figma、Framer、Miro、Webflow
- 金融：Binance、Coinbase、Kraken、Mastercard、Revolut、Stripe、Wise
- 电商零售：Airbnb、Meta、Nike、Shopify、Starbucks
- 媒体消费：Apple、HP、IBM、NVIDIA、Pinterest、PlayStation、SpaceX、Spotify、The Verge、Uber、Vodafone、WIRED
- 汽车：BMW、BMW M、Bugatti、Ferrari、Lamborghini、Renault、Tesla
- 复古网页：Dell (1996)、Nintendo (2001)
