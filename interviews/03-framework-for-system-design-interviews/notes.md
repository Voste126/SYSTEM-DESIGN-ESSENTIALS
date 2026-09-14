# 03 — A framework for system design interviews
Source: System Design Interview, Alex Xu, ch. 3

## The core idea

A system design interview isn't really testing whether you can design a real production system in 45 minutes — nobody expects that, and pretending you can is itself a red flag. It's testing collaboration under ambiguity: can you ask good clarifying questions, propose something reasonable, defend it, take feedback without getting defensive, and manage your own time. The final design matters less than the process you used to get there.

**Red flags interviewers watch for**: over-engineering (chasing design purity while ignoring real tradeoffs — and not understanding the compounding cost that causes), jumping to a solution before understanding the problem, narrow-mindedness, and stubbornness when given feedback.

## The 4-step framework

### Step 1 — Understand the problem and establish design scope (3–10 min)

The single biggest mistake is answering fast without understanding the question — confidence is not a substitute for clarity, and an interviewer reads "jumped straight to an answer" as a warning sign, not a strength. Slow down. Ask questions. If the interviewer can't answer a question directly, they'll ask you to state an assumption instead — write it down, you'll need it later.

Questions worth asking as a starting template:
- What specific features are we building?
- How many users does the product have?
- How fast is the company expecting to scale — what's the anticipated load in 3 months, 6 months, a year?
- What's the existing technology stack, and what existing internal services could simplify this design?

**Worked example — designing a news feed system.** The clarifying conversation covers: whether it's mobile, web, or both; which features matter most (the book's answer: posting, and viewing friends' feeds); whether the feed is strict reverse-chronological or weighted/ranked (simplifying assumption used here: reverse-chronological); the maximum friend count per user (5,000); daily active users (10 million); and whether posts can include media (yes — images and video).

### Step 2 — Propose high-level design and get buy-in (10–15 min)

Goal: reach agreement with the interviewer on a blueprint, treating them as a collaborator, not a judge scoring you in silence.
- Sketch box diagrams with the key components — clients, APIs, web servers, data stores, cache, CDN, message queue, etc.
- Run back-of-the-envelope math to check the blueprint actually fits the scale constraints from step 1 — and say out loud that you're about to do this before diving in.
- Walk through a few concrete use cases; this often surfaces edge cases you hadn't considered yet.
- Whether to go down to API endpoints and schema-level detail depends on the problem's scope — too low-level for "design Google search," entirely fair game for "design the backend of a multiplayer poker game." When in doubt, ask.

**Worked example continued.** The news feed design splits into two flows: *feed publishing* (a new post gets written to cache/database, then pushed out into friends' feeds) and *newsfeed building* (aggregating friends' posts, sorted reverse-chronologically, at read time).

### Step 3 — Design deep dive (10–25 min)

By this point you and the interviewer should already agree on scope, have a high-level blueprint, gotten feedback on it, and have a sense — from that feedback — of where to go deeper. Every interview differs here: sometimes the interviewer wants more high-level breadth, sometimes (especially for senior candidates) they want performance characteristics and bottleneck analysis, and most often they want you to dig into one or two specific components.

Examples of good deep-dive targets: for a URL shortener, the hash function that turns a long URL into a short one; for a chat system, reducing latency and supporting online/offline presence.

**Time management matters here more than anywhere else in the interview.** It's easy to get pulled into a fascinating rabbit hole that doesn't actually demonstrate scalable-system-design ability — e.g., spending real time detailing Facebook's actual EdgeRank ranking algorithm during a news feed interview burns the clock without proving the skill being assessed.

### Step 4 — Wrap up (3–5 min)

- Identify bottlenecks in your own design and discuss how you'd improve them. Never claim your design is perfect — that's an immediate credibility loss, not a strength.
- Recap the design, especially if you proposed multiple alternative approaches during the session — the interviewer has been listening for 45 minutes and a summary helps.
- Error cases (server failure, network loss) are worth discussing.
- Operational concerns are worth mentioning: how would you monitor metrics and error logs, how would you roll this system out?
- "The next scale curve" is a favorite follow-up: if your design supports 1M users, what has to change to support 10M?
- If you have time left, propose additional refinements you'd make given more time.

## Rough time allocation for a 45-minute session

| Step | Time |
|---|---|
| 1 — Understand & scope | 3–10 min |
| 2 — High-level design & buy-in | 10–15 min |
| 3 — Design deep dive | 10–25 min |
| 4 — Wrap up | 3–5 min |

This is explicitly a rough guide, not a rule — actual distribution depends on the problem's scope and how the interviewer steers the conversation.

## Dos

- Always ask for clarification. Never assume your assumption is correct without stating it.
- Understand the actual requirements of the problem before proposing anything.
- Accept that there's no single right answer — a startup-scale solution and a millions-of-users solution to the same prompt look completely different, and that's fine as long as it matches the stated requirements.
- Say what you're thinking out loud. Communicate constantly.
- Suggest multiple approaches where it makes sense to.
- Once you and the interviewer agree on the blueprint, go into detail on each component — starting with the most critical one first.
- Bounce ideas off the interviewer; a good one is working with you as a teammate, not against you.
- Never give up, even if a component turns out to be harder than expected.

## Don'ts

- Don't show up unprepared for the typical/common interview questions.
- Don't jump into a solution before clarifying requirements and assumptions.
- Don't go deep into one component too early — high-level first, then drill down.
- Don't hesitate to ask for a hint if you're stuck.
- Don't think in silence — communicate continuously.
- Don't assume you're done once you've given a design — you're done when the interviewer says you're done. Keep asking for feedback.

## What I'd forget in 6 months

- The exact time percentages (worth re-deriving the *ratios* — deep-dive gets the most time, wrap-up the least — rather than the exact minute ranges).
- That over-engineering is treated as a red flag, not a virtue — my instinct as an engineer is often to lean toward "more robust," but in this context that reads as not understanding tradeoffs.

## Questions I still don't have a crisp answer to

- How do you tell, in the moment, whether an interviewer's silence means "keep going, I'm listening" or "you've lost me, backtrack"?
- Is there a good way to practice step 1 (scoping questions) specifically, given that it's the step most different from actual day-to-day engineering work?
