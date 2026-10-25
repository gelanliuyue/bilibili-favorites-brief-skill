# Focused course tutorial workflow

Use this when the user asks for a tutorial around one topic inside a larger
batch, such as “turn the RAG course into a beginner tutorial”.

## 1. Define the course set

- Match the topic against lesson numbers and titles in `manifest.json`.
- Check the creator's full series when the batch is visibly missing numbered
  lessons.
- Process only missing lessons in a separate batch; copy existing successful
  results instead of paying to regenerate them.
- Keep the course in Bilibili publication order, and keep multi-P lessons in P
  order.

## 2. Read the source material

Read every summary in the selected set. For sections marked as core, also read
the relevant `章节全文.md` so the guide is grounded in the actual lesson rather
than only the one-line conclusion.

## 3. Build the tutorial

The Markdown tutorial must contain:

- a one-paragraph promise and total study time;
- a single pipeline or mental-model diagram;
- a legend for priorities and annotations;
- at least three routes: crash course, practical introduction, and full course;
- one section per lesson with duration, priority, takeaways, pitfalls, key
  timestamp links, knowledge-card link, and chapter-transcript link;
- a common-mistakes section;
- a hands-on checklist;
- a short quiz or acceptance questions;
- a complete course index.

Use explicit labels rather than vague emphasis:

- `★★★ 必看`
- `🧠 核心概念`
- `🛠️ 动手`
- `⚠️ 易错`
- `🔁 复习`

## 4. Render and verify

Generate a standalone learning-map SVG and responsive HTML beside the Markdown.
All relative links must resolve locally. Render the HTML in a browser and verify
the map, badges, tables, and long lesson list visually.
