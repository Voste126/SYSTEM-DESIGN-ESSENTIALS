# 02 — Back-of-the-envelope estimation
Source: System Design Interview, Alex Xu, ch. 2

## The pattern

Before you can argue for a specific architecture in an interview, you need numbers to argue with — how many requests per second, how much storage, how many servers. Back-of-the-envelope estimation is the skill of turning a vague prompt ("design Twitter") into concrete load parameters using a handful of memorized reference numbers plus simple arithmetic, not precision.

## Reference numbers worth memorizing

**Power of two — data volume units.** The book's text describes this table but doesn't reproduce the numbers, so here's the standard version to actually memorize:

| Power | Approximate value | Name | Short name |
|---|---|---|---|
| 2^10 | 1 thousand | 1 kilobyte | 1 KB |
| 2^20 | 1 million | 1 megabyte | 1 MB |
| 2^30 | 1 billion | 1 gigabyte | 1 GB |
| 2^40 | 1 trillion | 1 terabyte | 1 TB |
| 2^50 | 1 quadrillion | 1 petabyte | 1 PB |

**Latency numbers every programmer should know** (Jeff Dean's numbers, the commonly-cited 2020-updated version — the book references a visualization tool but doesn't list the actual figures):

| Operation | Time |
|---|---|
| L1 cache reference | 0.5 ns |
| Branch mispredict | 5 ns |
| L2 cache reference | 7 ns |
| Mutex lock/unlock | 100 ns |
| Main memory reference | 100 ns |
| Compress 1 KB with a fast compressor | 10,000 ns = 10 μs |
| Send 1 KB over 1 Gbps network | 10,000 ns = 10 μs |
| Read 4 KB randomly from SSD | 150,000 ns = 150 μs |
| Read 1 MB sequentially from memory | 250,000 ns = 250 μs |
| Round trip within same data center | 500,000 ns = 500 μs |
| Read 1 MB sequentially from SSD | 1,000,000 ns = 1 ms |
| Disk seek | 10,000,000 ns = 10 ms |
| Read 1 MB sequentially from disk | 20,000,000 ns = 20 ms |
| Send packet from California to Netherlands and back | 150,000,000 ns = 150 ms |

The one-sentence version: **memory is fast, disk is slow, and crossing the network between data centers costs more than almost anything else on this list** — three orders of magnitude more than a same-datacenter round trip.

**Availability numbers — "the nines."** The book references a table without the actual figures; here's the standard downtime-per-year for each availability tier:

| Availability | Downtime per year |
|---|---|
| 99% (two nines) | ~3.65 days |
| 99.9% (three nines) | ~8.76 hours |
| 99.99% (four nines) | ~52.6 minutes |
| 99.999% (five nines) | ~5.26 minutes |
| 99.9999% (six nines) | ~31.5 seconds |

Most major cloud provider SLAs (AWS, GCP, Azure) sit at 99.9% or above — three nines is the common baseline to design against unless a requirement says otherwise.

## The worked example, restated as a formula

Given: MAU, % daily active, posts/day/user, % of posts with media, avg media size, retention period —

```
DAU = MAU × daily-active-%
average QPS = (DAU × posts/day) / 86,400 seconds
peak QPS ≈ 2 × average QPS   (a common rough multiplier, not a law of physics)
daily media storage = DAU × posts/day × media-% × avg media size
total storage = daily media storage × 365 × retention years
```

The book's own example: 300M MAU, 50% daily active, 2 tweets/day, 10% with 1MB media, 5-year retention → ~3,500 QPS average, ~7,000 QPS peak, 30 TB/day, ~55 PB over 5 years.

## Interview framing

- **The tell**: any prompt asking you to "design X" without given numbers is implicitly asking you to produce your own load parameters first — skipping straight to architecture without stating assumptions is a common early mistake.
- **The follow-up question an interviewer usually asks next**: "what if that number were 10x higher — what's the first thing that breaks?" This is really testing whether you understand *why* you chose the numbers you chose, not just whether you can multiply.

## What I'd forget in 6 months

- The exact latency numbers (memorize the *shape* — memory << SSD << disk << cross-datacenter network — rather than exact nanosecond figures, which will be stale in a few years anyway).
- The nines-to-downtime conversion — worth deriving on the spot (365.25 days × 24 × 60 minutes × (1 − availability)) rather than memorizing the table.

## Questions I still don't have a crisp answer to

- Where does the "2x for peak" multiplier actually come from — is it a real measured pattern or just a convenient interview heuristic?
- How do you sanity-check an estimate when you have no real production data to compare it against?
