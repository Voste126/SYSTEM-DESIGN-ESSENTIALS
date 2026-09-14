# 01 — What is software engineering?
Source: Software Engineering at Google, Winters & Manshreck, ch. 1

## Read this version first (the simple one)

Google's core claim: **"software engineering is programming integrated over time."** Programming is writing code that works right now. Software engineering is everything required to keep that code working, and keep it changeable, for however long it actually needs to survive — which could be an hour or could be decades, and the practices that make sense at one end are actively wrong at the other.

Three things separate the two:
- **Time** — will this code need to survive a language upgrade, an OS upgrade, a hardware change? A one-off script doesn't care. Google Search has to.
- **Scale** — is this one person's work, or does it need policies that still work when the team is 10x or 100x bigger?
- **Trade-offs** — software engineering means constantly weighing costs (money, compute, people's time, opportunity cost, even societal impact) against each other, usually with incomplete information.

## The deeper version

### The lifespan spectrum is the whole chapter's foundation

Reasonable answers to "how long will this code live" vary by roughly a **factor of 100,000** — from an hour to multiple decades. Code on the short end is basically unaffected by time: a one-time script doesn't care if a new OS version drops while you're writing it. Code on the long end (Google Search, the Linux kernel) has to assume everything underneath it — libraries, the OS, the language itself — will eventually change, because over a long enough span, it will.

**Sustainability**, precisely defined: your project is sustainable if, for as long as it's expected to live, you're *capable* of reacting to any valuable change — technical or business. Capable, not obligated — you can choose not to upgrade. But if you're *incapable* of reacting (because nothing was ever built to allow it), you're making a silent bet that nothing important will ever need to change. That bet is often fine for a short-lived project and reckless for a long one.

### Hyrum's Law — the single idea worth memorizing cold

> With a sufficient number of users of an API, it does not matter what you promise in the contract: all observable behaviors of your system will be depended on by somebody.

The hash-set-ordering example makes this concrete: nothing in a hash set's contract promises any particular iteration order, but if you run the same program long enough with enough users, *someone* will write code that quietly depends on whatever order it happens to produce today — maybe using it as an ad hoc random number source. You didn't promise that order would stay stable. It doesn't matter. It's being depended on anyway.

The practical takeaway isn't "therefore never let anything be observable" (impossible) — it's that every change to a long-lived, widely-used system needs to weigh not just "does this violate the documented contract" but "what real, undocumented behavior might people be relying on, and what does it cost to find and fix those breaks."

### Policies that scale, and policies that quietly don't

The test for whether a policy scales: imagine your organization 10x or 100x bigger. Does the *work required per engineer* grow along with it? If yes, you have a scaling problem, policy or not.

**A scaling failure, concretely — old-style deprecation.** "We're deleting the old Widget on August 15th, migrate before then" pushes the migration cost onto every downstream team, and that cost grows with the size of the dependency graph, not with the size of the team doing the deprecating.

**The fix Google settled on — the Churn Rule.** Whoever owns the infrastructure change does the migration work themselves (or makes the change backward-compatible in place). This scales because a small number of experts doing a well-understood migration is cheaper, in aggregate, than forcing every downstream team to re-learn the problem from scratch just to fix their one usage.

**A second scaling win — the Beyoncé Rule**: "if it broke and there wasn't a CI test for it, that's not the fault of the infrastructure change that broke it" ("if you liked it, you should have put a test on it"). Without this, an infrastructure team would need to manually track down every team with any bespoke, untested dependency before making any change — a cost that grows without bound as the org grows. With it, the CI system is the single source of truth for "does this break anything," which scales flat regardless of headcount.

**A structural failure mode — long-lived dev branches.** Feature branches that stay open a long time and merge in big batches work fine at 5-10 branches; the resync/retest cost every time a branch merges grows with the *number* of branches, which grows with team size. This is why trunk-based development (small, frequent merges) tends to win as organizations scale — the alternative's cost curve is superlinear.

### Shifting left

The developer workflow is a timeline: design → implementation → review → testing → commit → canary → production. A bug found earlier on that timeline is cheaper to fix than the same bug found later — a security flaw caught before commit costs the original author a quick fix; the same flaw discovered in production requires someone else to investigate, triage, and remediate a live incident. "Shifting left" just means pushing detection as early on that timeline as it can go — static analysis and code review before commit are cheap; production incidents are expensive, for the same bug.

### Trade-offs and the six kinds of cost

Google explicitly tracks more than money when weighing a decision: **financial cost, resource cost (CPU/compute), personnel cost (engineer time), transaction cost (cost of acting), opportunity cost (cost of *not* acting), and societal cost** (impact on users, especially at billion-user scale, where small usability/fairness/abuse gaps get magnified). Two worked examples make the "small decision, real trade-off" point vivid:

- **Whiteboard markers.** Locking up a $1 marker to prevent hoarding trades away friction-free brainstorming to save almost nothing — a deliberately lopsided trade-off Google chose to *not* make, on purpose, once actually priced out.
- **Distributed builds.** Moving from local builds to a shared distributed build system clearly paid off in engineer-time saved — but once the *individual* cost of a bloated build stopped being felt directly by each engineer, nobody was incentivized to keep dependencies lean anymore, and build bloat crept back in as an unintended side effect (an instance of Jevons Paradox: efficiency gains can increase total consumption, not just efficiency).

### When time and scale actually conflict: fork or depend?

Forking a dependency to fit your exact needs gives you control and insulation from someone else's changes — genuinely valuable for a short-lived or narrowly-scoped project. But at scale, every fork is a copy that needs its own security patches, its own bug fixes, its own migration when something upstream changes — the exact scaling failure mode the rest of the chapter warns about. Short project life span or a provably narrow-scope fork: less risky. A fork of something structural (data formats, network protocols, serialization) that could spread across many projects and years: high risk.

## The one line worth keeping on a sticky note

**"It's programming if 'clever' is a compliment, but it's software engineering if 'clever' is an accusation."** Clever, brittle, implementation-dependent code is fine for something that lives an hour. The same cleverness in a system that needs to survive a decade of compiler upgrades is a future incident report.

## How this differs from the other two tracks

Alex Xu's book teaches you to *design* a system in an interview. DDIA teaches you the *technical* tradeoffs inside a system once it exists. This book is about neither — it's about what keeps a system (and the organization behind it) alive and changeable for years, which is a completely different skill from either designing or implementing one. None of the other two tracks mention Hyrum's Law, the Beyoncé Rule, or the idea that "sustainable" is a precise, definable property rather than a vibe.

## Questions I still don't have a crisp answer to

- How do you actually estimate "expected code lifespan" honestly at the moment you're writing something, rather than after the fact when it's obvious in hindsight?
- The Churn Rule assumes infrastructure teams have the bandwidth to migrate everyone themselves — what's the actual threshold where that stops being affordable and some cost has to shift back to downstream teams?
