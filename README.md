# Systems Knowledge & Architecture Essentials

A personal engineering-knowledge repository maintaining structured notes and interactive visual explainers across two concurrent reading tracks. The repository separates interview-oriented patterns from production-grade distributed systems trade-offs:

- **[`interviews/`](interviews/README.md)** — *System Design Interview* by Alex Xu. Interview-prep framing: crisp, pattern-oriented, "here's the technique, the problem triggers, and when to reach for it."
- **[`what-you-dont-know/`](what-you-dont-know/README.md)** — *Designing Data-Intensive Applications* by Martin Kleppmann. Senior-engineer depth: operational failure modes, distributed race conditions, and real-world production trade-offs.

Every chapter across both tracks pairs markdown notes (`notes.md`) with a lightweight interactive visual explainer (`article.html`) and optional runnable code (`snippets/`).

---

## Shared Visual Explainer System

All interactive explainers leverage a shared "scrollytelling" engine located in **[`_shared/`](_shared/)**:
- **[`_shared/theme.css`](_shared/theme.css)**: Centralized design system built around an editorial paper/ink/amber palette (`--paper:#EEEDE6`, `--ink:#1D2321`, `--accent:#B9762B`), typography (`Source Serif 4` body + `IBM Plex Mono` labels), responsive split-screen layouts, and sticky diagram viewports.
- **[`_shared/scrollytelling.js`](_shared/scrollytelling.js)**: Reusable progression engine that manages diagram stage visibility via `data-min` / `data-max` attributes, automatic scroll-spy driven by `IntersectionObserver`, and declarative stage navigation.

---

## Directory Layout

```
systems-knowledge/
├── README.md                          # Repository guide & track directory
├── CONTRIBUTING.md                    # Repeatable checklist for adding new chapters
├── _shared/                           # Reusable scrollytelling engine & design tokens
│   ├── theme.css
│   └── scrollytelling.js
├── interviews/                        # Track 1: System Design Interview (Alex Xu)
│   ├── README.md
│   └── 01-scale-to-millions/
│       ├── notes.md
│       ├── article.html
│       └── snippets/
└── what-you-dont-know/                # Track 2: Designing Data-Intensive Applications (DDIA)
    ├── README.md
    └── 01-reliable-scalable-maintainable/
        ├── notes.md
        ├── article.html
        └── snippets/
```

---

## Workflow

To add a new chapter or topic, consult the repeatable 4-step checklist in **[CONTRIBUTING.md](CONTRIBUTING.md)**.
