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
