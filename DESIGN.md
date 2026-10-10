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
- 表格按解析到的列数渲染，不再截断成两列：第 1 列是标签列（宽度按内容
  测算，标签尽量排在一行），其余列等分。单元格写成 `**文字**` 时会渲染为
  带浅灰底的表头格，该行同时成为 `<thead>`，**跨页时在每页重复**。
- 中文词组不会被拆行（`露营` 不会变成 `露` / `营`）；只有 ≤6 字的中文串
  设为不断行，更长的中文仍可换行，避免撑破单元格。
- 无问题的表格型词汇表会自动渲染为表格版式 PDF；表格 + 讨论题的混合讲义
  （如 `Spoken/English for WeChat.md`）则第 1 页词汇表、第 2 页讨论。列数
  超过 3 的宽表格也走表格版式（跨页排版，末尾的讨论小节一并渲染），
  如 `Travel/Different Types of TRAVEL.md`。
- 纯讨论题讲义（`--questions-only`）若自动分页会把某组的最后 1 题单独甩到
  第 2 页，渲染器改为在组与组之间换页（取两页题量最接近的分界）；行距两页
  统一，不再逐页拉伸。不需要这个处理时加 `--no-balance`。
- `--notes` 默认把最后一节当讨论页处理：单独起页，行距撑到页底。末节其实是
  句型 / 词汇练习而不是讨论题时（如 `Travel/At the Restaurant.md`），加
  `--no-disc-page`，让最后一节和其他各节行距一致、也不另起页。
- 排版不留孤行：一条列表内容不会被拆到两页（`li` 设 `break-inside: avoid`）；
  一页放得下的短节整体保持在同一页（`.sec.keep`），避免标题只带一行就断页；
  长节照常跨页，标题靠 `h2 { break-after: avoid }` 始终跟着正文。
  节标题不要用一级 `# `——渲染器只把第一个 `# ` 当文档标题，分节请用 `## `。
- 换风格只需改 `--design` 参数；同一项目内保持风格统一，不要混用。

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
