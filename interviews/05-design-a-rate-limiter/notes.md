# 05 — Design a rate limiter
Source: System Design Interview, Alex Xu, ch. 4

## The pattern

A rate limiter caps how many requests a client or service can send in a given window — "no more than 2 posts per second," "10 new accounts per day per IP," "5 reward claims per week per device." It exists for three concrete reasons: stopping resource exhaustion from a denial-of-service attack (intentional or not — Twitter and Google Docs both publish hard per-user caps for exactly this reason); controlling cost when you're paying per call to a third-party API (credit checks, payments, health records); and simply keeping your own servers from being overwhelmed by bots or misbehaving clients.

## Requirements, stated plainly

- Accurately enforce the limit.
- Add minimal latency to every request that *isn't* rate limited.
- Use memory efficiently.
- Work across multiple servers/processes (distributed, not single-instance).
- Give the client a clear signal when it's been throttled.
- Fail gracefully — if the rate limiter's own infrastructure (e.g., its cache) goes down, the rest of the system should keep working.

## Where to put it: client, server, or middleware

- **Client-side** — generally the wrong place. A client's requests are trivially forgeable by anyone malicious, and you often don't even control the client's code (think third-party apps calling your API).
- **Server-side** (inside each API server) — works, but couples rate-limiting logic to your application code.
- **Middleware in front of the API servers** — a dedicated layer that inspects and throttles requests before they ever reach your actual servers, returning HTTP 429 ("too many requests") to anything over the limit. This is commonly implemented as part of an **API gateway** — a managed component that often also handles SSL termination, auth, and IP allow-listing alongside rate limiting.

**Deciding between "build it into the gateway" vs. "build a standalone service"** comes down to practical factors: how efficient your current stack is for this; which algorithm your business actually needs (building it yourself gives full algorithm control, a third-party gateway may constrain your choices); whether you already run a gateway for other cross-cutting concerns (if so, adding rate limiting there is often the path of least resistance); and whether you have the engineering time to build and maintain a custom service at all (a commercial gateway is the pragmatic choice when you don't).

## The five algorithms, one by one

**Token bucket** — a bucket with a fixed capacity; tokens refill at a steady rate up to that capacity, and any request consumes one token (dropped if none are available). Two parameters: bucket size, refill rate. Used by Amazon and Stripe. **Pros**: simple, memory-efficient, and — notably — tolerates short bursts gracefully, since a request can go through as long as tokens are sitting in the bucket even if they arrived faster than the steady refill rate. **Cons**: tuning the two parameters correctly for a given workload isn't always obvious. How many buckets you need scales with how granular your rules are — separate buckets per endpoint (one for posting, one for friend requests, one for likes), per IP address if you're throttling by IP, or one shared global bucket if you just need an overall system-wide cap.

**Leaking bucket** — conceptually similar, but implemented as a FIFO queue processed at a strictly fixed output rate rather than a token pool. An incoming request either joins the queue (if there's room) or gets dropped (if the queue's full); requests are pulled off and processed at a constant interval regardless of how bursty the input was. Parameters: queue size, outflow rate. Shopify uses this approach. **Pros**: memory-efficient, and ideal when you specifically need a stable, predictable output rate. **Cons**: a burst can fill the queue with a backlog of *old* requests, meaning genuinely recent requests get rejected while stale ones are still processing — the opposite of what you'd usually want; still has the same two-parameter tuning difficulty as token bucket.

**Fixed window counter** — divide time into fixed-size windows (e.g., one-second or one-minute buckets), keep one counter per window, increment on each request, and reject anything once the counter hits the threshold for that window — resetting fresh at the next window boundary. **Pros**: memory-efficient, simple to reason about, and the "quota resets on a clean boundary" behavior fits some use cases naturally. **Cons — the big one**: traffic clustered right at the edge of two adjacent windows can let through nearly double the intended limit. If the limit is 5 requests/minute and a client sends 5 requests in the last moment of one window and 5 more in the first moment of the next, any *rolling* one-minute span straddling that boundary sees 10 requests — twice the allowed rate — even though neither individual fixed window technically exceeded its own quota.

**Sliding window log** — the direct fix for that edge-burst problem. Keep an actual log of request timestamps (commonly in a Redis sorted set); on each new request, purge timestamps older than the start of the current rolling window, add the new timestamp, and accept the request only if the resulting log size is within the allowed count (otherwise reject it, though the timestamp may still occupy space in the log even for a rejected request). **Pros**: genuinely accurate — no rolling window, at any position, will ever see more than the allowed count. **Cons**: memory cost, since every timestamp for every request (accepted or not) potentially lingers until it ages out of the window.

**Sliding window counter** — a hybrid that captures most of the sliding-log accuracy at close to the fixed-window's memory cost. Instead of a full timestamp log, it estimates the current rolling count using: *(requests in the current fixed window) + (requests in the previous fixed window × the overlap fraction between the rolling window and that previous window)*. For example, with 3 requests already in the current window, 5 in the previous window, and the current moment sitting 30% of the way into the current window (meaning the rolling window still overlaps 70% of the previous window), the estimate comes out to 3 + 5×0.7 ≈ 6.5, typically rounded down to 6. **Pros**: smooths out traffic spikes since it's implicitly averaging against the recent past, and stays memory-efficient (no per-request log). **Cons**: it's an *approximation* — it assumes requests were evenly spread across the previous window, which isn't always true — though in practice this turns out to matter far less than it sounds: Cloudflare's own measurements found only a tiny fraction of a percent of requests were ever mis-classified by this approximation across hundreds of millions of real requests.

## The high-level architecture

At its core, every one of these algorithms boils down to: maintain a counter per client/key, compare it against a threshold, reject if exceeded. The counter needs to live somewhere fast — a database is too slow for something on the hot path of every request — so an **in-memory cache with built-in expiration** is the standard choice. Redis specifically is popular because it natively supports exactly the two operations this needs: `INCR` (atomically bump a counter) and `EXPIRE` (auto-delete the counter once its time window has passed).

**The request flow**: client → rate-limiting middleware → middleware fetches the relevant counter from Redis and checks it against the limit → if over the limit, reject immediately (429) without ever touching the real API servers; if under the limit, forward to the API servers *and* increment the counter in Redis.

## Rules, rejection handling, and client-facing signals

**Rules** are typically expressed declaratively and stored in configuration files on disk — something like "allow a maximum of 5 marketing messages per day per user" or "no more than 5 login attempts per minute." Lyft's open-sourced rate-limiting component is a real-world example of this pattern.

**When a request gets rejected**, the standard response is HTTP 429. Depending on the use case, a rejected request might just be dropped, or — for something like an order that shouldn't simply vanish — queued for later processing instead of discarded outright.

**How a client knows where it stands**: three response headers are the convention — one indicating remaining allowed requests in the current window, one indicating the total limit per window, and one telling the client how long to wait before it's safe to retry. These headers turn "getting rate limited" from a mysterious failure into something a well-behaved client can react to gracefully (back off, retry later).

**The fuller pipeline**: rules live on disk; background workers periodically pull them into a cache so the hot path never touches disk directly. An incoming request hits the middleware, which reads the cached rules plus the relevant counter and last-request-timestamp from Redis, and decides to forward or reject (429, possibly with the request queued rather than dropped) accordingly.

## The two hard problems in a distributed rate limiter

**Race conditions.** The naive "read counter, check threshold, write counter+1" sequence is not atomic. If two requests read the same counter value concurrently before either writes back, both compute "current value + 1" from the same stale read and both write back the same (wrong, too-low) result — silently under-counting real traffic. Plain locks would fix this but at a real cost to throughput, so the practical fixes lean on Redis-specific tools instead: Lua scripts (letting the whole read-check-increment sequence run as one atomic unit inside Redis itself) or Redis's sorted-set data structure, which supports the sliding-window-log approach's operations atomically.

**Synchronization across multiple rate-limiter instances.** Once there's more than one rate-limiter server (necessary at real scale), and clients can land on different instances between requests (normal for a stateless web tier), each instance needs a consistent view of every client's usage — otherwise a client could effectively double or triple their real limit just by having requests happen to land on different rate-limiter instances that don't know about each other. Sticky sessions (always routing a given client to the same rate-limiter instance) technically works but isn't scalable or flexible. The better fix: a shared, centralized data store (Redis again) that every rate-limiter instance reads and writes against, so there's exactly one source of truth for each client's counters regardless of which instance handled which request.

## Performance optimization and monitoring

**Multi-datacenter deployment** matters because latency to a single, distant rate-limiter location can dominate response time for geographically distant users — the standard fix, as with most latency-sensitive infrastructure, is distributing edge locations globally and routing each client to its nearest one.

**Eventual consistency** for synchronizing rate-limiter data across those distributed locations is an accepted tradeoff — perfect real-time consistency isn't necessary for a system whose whole job is enforcing an approximate cap, not an exact one.

**Monitoring** exists to answer two ongoing questions: is the *algorithm* actually working (catching real abuse without excessive false positives), and are the *rules* themselves well-calibrated (too strict, and you're dropping legitimate traffic; too loose, and you're not actually protecting anything)? A concrete example of rules needing to adapt: a sudden legitimate traffic spike (a flash sale) might reveal that your current algorithm can't tolerate bursts well — a sign to switch toward something like token bucket, which explicitly tolerates burstiness by design.

## Additional talking points worth having ready

- **Hard vs. soft limits**: a hard limit never allows the threshold to be exceeded, even briefly; a soft limit tolerates a short grace period over the threshold before actually rejecting requests.
- **Rate limiting isn't only an application-layer (L7/HTTP) concern** — it's equally possible to rate-limit at the network layer (L3) using IP-level tooling, a different mechanism entirely from the HTTP-level middleware discussed throughout this chapter.
- **Advice for well-behaved clients** to avoid being throttled in the first place: cache responses locally to avoid redundant calls, understand and respect the documented limits, handle rate-limit errors gracefully in code rather than crashing, and back off with increasing delay on retries rather than hammering the API immediately again.

## Interview framing

- **The tell**: any prompt mentioning abuse prevention, cost control on paid APIs, or protecting backend services from overload is pointing at this exact problem.
- **The follow-up question an interviewer usually asks next**: "what happens when you have multiple rate-limiter instances?" — this is testing whether you understand that a single-server rate limiter is the easy 20% of the problem, and the distributed synchronization piece is where the real design thinking has to happen.

## What I'd forget in 6 months

- The exact formula for the sliding window counter approximation — worth re-deriving the *intuition* (weight the previous window's count by how much it still overlaps the current rolling window) rather than memorizing the formula verbatim.
- Which specific companies use which algorithm (Amazon/Stripe → token bucket, Shopify → leaking bucket) — useful color for an interview, not the actual substance of the answer.

## Questions I still don't have a crisp answer to

- In practice, how do teams decide between Lua scripts and Redis sorted sets for solving the race-condition problem — is one clearly preferred for most real deployments?
- How often does the sliding window counter's "assume even distribution within the previous window" assumption actually cause a meaningful problem in practice, beyond the specific measurement one company reported?
