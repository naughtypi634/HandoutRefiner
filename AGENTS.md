# HandoutRefiner Agent Instructions

## Project Overview

Refines and renders ESL handout Markdown (Business / Spoken / Travel / Beginner) into print-ready PDFs via `scripts/md_to_pdf.py`. Course introductions live in `课程介绍.md`.

## 一 · 文档内容

**文档只呈现教学内容本身，不出现 meta 信息。**

meta 指一切不承载教学内容的文字，不论写给谁——包括写给学生看的引导句。禁止：

- 课程介绍、每节引导句、说明性标签或过渡文字（如“先认识……”“用这些句型开头”“你的版本”“完整示范”）。
- 未经要求的副标题、工作表标签、宣传语或其他元话术；文档只呈现标题和教学内容本身。
- 把选题或措辞要求（如“无关痛痒”“不敏感”“轻松有趣”）原样写进标题、正文或引导句——这类要求只作为生成准则，不得明文标注（如不要写 "Some common, harmless examples:" 这类给作者看的说明文字）。

**文档只保留标题、表格、练习和讨论问题本身。** 本规则适用于所有文档的生成、修订和重排版，任何时候都不得添加这类内容。

## 二 · 受众与场景

所有内容面向 **2026 年的中国成年英语学习者（默认 A1-A2）**。例句、讨论题、练习场景必须贴近当代中国成年人生活（外卖、地铁通勤、加班、面试、租房、微信等），不用过时或陌生场景。

## 三 · 语言真实度

- **例句要有具体画面**：每条例句必须包含具体场景、人物和动作，让读者能立刻在脑中成像并代入（如 "I'm in a good mood — my coffee was free today."），禁止写干巴巴的通用例句（如 "I'm happy today."）。
- **习语必须当代、真实在用**：只选 2020 年代英语口语中真实高频的习语/俚语，避免教科书式、老套、过时的表达（如 over the moon、raining cats and dogs、down in the dumps 之类）。拿不准就先查证再写。

## 四 · 语言标准

**英文一律用美式英语（American English）**，全局生效：拼写、词汇、语法、日期数字格式都用美式，禁止英式。完整替换词表与交付前自检流程见用户级 `ESL-content.instructions.md`。

⚠️ 本项目现有内容中含约 30 处英式拼写（早期 docx 导入遗留，集中在 `Business/`、`Spoken/`、`Travel/` 的话题讲义）。这些是**已知存量**，改动它们会与已打印发出去的材料不一致——先报告，不要擅自修。**新写的内容一律按美式英语。**

## 五 · 版式

- **单课 / 单话题讲义固定 2 页 A4**（大表格可放宽到 4 页）。教师版、分级读物、手册长清单不受此约束，各自另有页数契约。
- **默认黑白打印**，彩色为可选项。

## 视觉设计

- 讲义 PDF 的视觉样式与渲染规则见 [DESIGN.md](DESIGN.md)（awesome-design-md YAML token，默认 `cal` 风格，偏黑白色调）。
