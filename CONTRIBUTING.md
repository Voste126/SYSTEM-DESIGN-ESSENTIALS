# Adding a New Chapter — Repeatable Checklist

Follow this 4-step checklist whenever you add a new chapter from either *System Design Interview* (Alex Xu) or *Designing Data-Intensive Applications* (Martin Kleppmann).

---

## 1. Create the Chapter Folder
Determine the correct track and create a zero-padded folder:
- **Alex Xu**: `interviews/NN-kebab-case-topic-name/`
- **DDIA**: `what-you-dont-know/NN-kebab-case-topic-name/`

```bash
# Example for interviews Chapter 02:
mkdir -p interviews/02-back-of-the-envelope-estimation/{snippets}
```

---

## 2. Create `article.html` (Thin Scrollytelling Shell)
Create `article.html` inside the new folder. Link to the shared assets `../../_shared/theme.css` and `../../_shared/scrollytelling.js`.

Use this minimal shell:

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>NN — [Topic Title] | System Design Essentials</title>
  <meta name="color-scheme" content="light">
  <link rel="stylesheet" href="../../_shared/theme.css">
  <script src="../../_shared/scrollytelling.js" defer></script>
</head>
<body>

  <nav class="top-nav">
    <a href="../index.html" class="nav-btn back">&larr; <span class="track-name">TRACK_NAME</span></a>
    <a href="../../index.html" class="nav-btn">index</a>
  </nav>

  <header class="article-header">
    <div class="article-meta">
      <span>Chapter NN</span>
      <span>•</span>
      <span class="source-ref">[Author, Book Title]</span>
    </div>
    <h1 class="article-title">[Topic Title]</h1>
    <p class="article-dek">[1-2 sentence core premise of the chapter]</p>
  </header>

  <main class="scrolly-container">
    <!-- Left: Sticky SVG Diagram -->
    <aside class="diagram-column">
      <div id="stage-nav-container" class="stage-nav"></div>

      <figure class="diagram-frame">
        <div class="diagram-svg-wrap">
          <svg viewBox="0 0 800 600" fill="none" xmlns="http://www.w3.org/2000/svg">
            <!-- Stage 1 elements: data-min="1" -->
            <g data-min="1">
              <!-- SVG shapes here -->
            </g>
            <!-- Stage 2 elements: data-min="2" -->
            <g data-min="2">
              <!-- SVG shapes here -->
            </g>
          </svg>
        </div>

        <div class="stage-caption-card">
          <span id="stage-caption-tag" class="caption-tag">Stage 01</span>
          <div id="stage-caption">Initial description.</div>
        </div>
      </figure>
    </aside>

    <!-- Right: Prose Narrative with click triggers -->
    <article class="prose-column">
      <section class="prose-step" data-stage="1">
        <div class="step-header" onclick="setStage(1, true)">
          <span class="step-num">01</span>
          <h2 class="step-title">[Stage 1 Heading]</h2>
        </div>
        <p>[Explanatory narrative...]</p>
      </section>

      <section class="prose-step" data-stage="2">
        <div class="step-header" onclick="setStage(2, true)">
          <span class="step-num">02</span>
          <h2 class="step-title">[Stage 2 Heading]</h2>
        </div>
        <p>[Explanatory narrative...]</p>
      </section>
    </article>
  </main>

  <footer class="article-footer">
    <span>System Design Essentials</span>
    <span>Source: [Book reference]</span>
  </footer>

  <script>
    const captions = {
      1: { tag: "Stage 01 — [Name]", text: "[Short caption explaining stage 1]" },
      2: { tag: "Stage 02 — [Name]", text: "[Short caption explaining stage 2]" }
    };

    window.addEventListener('DOMContentLoaded', () => {
      window.buildStageNav('#stage-nav-container', Object.keys(captions).length, captions);
    });
  </script>
</body>
</html>
```

---

## 3. Write `notes.md` from the Track Template

### For `interviews/` (Alex Xu format):
```markdown
# NN — [Topic Name]
Source: System Design Interview, Alex Xu, ch. NN

## The pattern
[2-3 sentence summary of the core technique/progression, in my own words]

## What I'd forget in 6 months
- ...

## Interview framing
- What's the "tell" in a prompt that signals this technique?
- What's the one follow-up question an interviewer usually asks next?

## Questions I still don't have a crisp answer to
- ...
```

### For `what-you-dont-know/` (DDIA format):
```markdown
# NN — [Topic Name]
Source: Designing Data-Intensive Applications, Kleppmann, ch. NN

## The tradeoff triangle
[reliability / scalability / maintainability — how they pull against each other]

## Where I've seen this go wrong in something I've actually worked on
- ...

## How this differs from the interview-book treatment of the same idea
- ...

## Questions I still don't have a crisp answer to
- ...
```

---

## 4. Add Row to Track `README.md`
Open the corresponding track's `README.md` (`interviews/README.md` or `what-you-dont-know/README.md`) and append a row to the table:

```markdown
| `NN` | **[Topic Name]** | [notes.md](NN-kebab-case/notes.md) | [article.html](NN-kebab-case/article.html) |
```

---

## Optional: Runnable Code in `snippets/`
Add standalone scripts (e.g. `consistent_hashing.py`, `p99_latency_sim.py`) inside `snippets/` to test or benchmark core distributed mechanisms.
