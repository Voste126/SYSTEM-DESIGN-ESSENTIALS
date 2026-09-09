# 01 — Reliable, scalable, maintainable applications
Source: Designing Data-Intensive Applications, Kleppmann, ch. 1

## The tradeoff triangle

Reliability, scalability, and maintainability aren't independent knobs — they're three lenses on the same system, and optimizing hard for one usually costs you effort on the others.

- **Reliability**: the system keeps doing the right thing even when parts of it go wrong. The key distinction is *fault* (one component deviating from spec) versus *failure* (the whole system failing the user). Good design is about stopping faults from becoming failures, not pretending faults won't happen.
- **Scalability**: not a label a system either has or doesn't — it's a question of "if load grows this way, what breaks first, and what do we do about it?" You can't answer that without first describing load with real parameters (requests/sec, read:write ratio, fan-out, whatever's actually the bottleneck for *your* system).
- **Maintainability**: the majority of a system's lifetime cost is maintenance, not initial build. It splits into operability (can ops keep it running smoothly), simplicity (can a new engineer understand it — specifically, how much of its complexity is *accidental* rather than inherent to the problem), and evolvability (can it be changed as requirements shift).

## The idea that reframed things for me

Twitter's home-timeline problem is the clearest example in the chapter of why "scalability" isn't one-dimensional. Posting a tweet is cheap in isolation — the expensive part is fan-out: each tweet has to reach every follower. Fan-out-on-read (query all followees' tweets at read time) is simple but the read path gets crushed, since reads (300k/sec) vastly outnumber writes (4.6k/sec average). Fan-out-on-write (push each tweet into every follower's precomputed timeline cache at post time) makes reads cheap but turns one write into potentially millions — Twitter's own numbers show a single celebrity tweet fanning out to 30M+ writes. Their actual answer is a hybrid: fan-out-on-write for most users, fan-out-on-read for celebrities, merged at read time. There's no universally "correct" architecture — the right one depends entirely on your load parameters.

## Where I've seen this go wrong in something I've actually worked on

*(fill this in — pick a system you've touched where reliability, scalability, or maintainability was quietly traded away, and what the actual consequence was)*

## How this differs from the interview-book treatment of the same idea

Alex Xu's chapter 1 hands you a sequence of *techniques* — load balancer, replica, cache, CDN — as if scalability is a checklist you apply in order. Kleppmann's chapter 1 deliberately refuses to give you a checklist: the whole point of the Twitter example is that the "obviously correct" architecture (fan-out-on-read, the simple relational join) was wrong for their actual load shape, and the fix required understanding *their* specific ratio of reads to writes, not applying a generic pattern. The interview book optimizes for "name the right technique fast." This book optimizes for "can you tell me why that technique is right *here*."

## Terms worth being able to define cold

- **Fault vs. failure** — component deviation vs. user-visible system failure.
- **Load parameters** — the numbers that describe current load (Twitter: tweet rate, but really fan-out distribution).
- **Tail latency / p99, p999** — why the mean is close to useless for user experience, and why Amazon optimizes p999 but not p9999 (diminishing returns past a point).
- **Accidental vs. inherent complexity** — accidental complexity comes from implementation, not from the problem itself; abstraction is the main tool for removing it.

## Questions I still don't have a crisp answer to

- How do you actually decide *which* percentile to optimize for before you have production traffic to measure?
- At what point does "distributed by default" stop being overkill for a system that doesn't yet have Twitter-scale load?
