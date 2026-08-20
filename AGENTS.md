# HandoutRefiner Agent Instructions

## Project Overview

Refines and renders ESL handout Markdown (Business / Spoken / Travel / Beginner) into print-ready PDFs via `scripts/md_to_pdf.py`. Course introductions live in `课程介绍.md`.

讲义 PDF 的视觉样式由 `scripts/md_to_pdf.py` 按本地 awesome-design-md 合集的 YAML 设计 token 渲染（默认 `cal` 风格，偏黑白色调），不再参考 ESL Assistant 样式。

## 内容原则

- **受众与时代定位**：所有内容面向 **2026 年的中国成年英语学习者（A1-A2）**。例句、讨论题、练习场景必须贴近当代中国成年人生活（外卖、地铁通勤、加班、面试、租房、微信等），不用过时或陌生场景。
- **习语必须当代、真实在用**：只选 2020 年代英语口语中真实高频的习语/俚语，避免教科书式、老套、过时的表达（如 over the moon、raining cats and dogs、down in the dumps 之类）。拿不准就先查证再写。
- **例句要有具体画面**：每条例句必须包含具体场景、人物和动作，让读者能立刻在脑中成像并代入（如 "I'm in a good mood — my coffee was free today."），禁止写干巴巴的通用例句（如 "I'm happy today."）。
