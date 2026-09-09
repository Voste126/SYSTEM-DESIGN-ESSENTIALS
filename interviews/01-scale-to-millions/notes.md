# 01 — Scale from zero to millions of users
Source: System Design Interview, Alex Xu, ch. 1

## The pattern
Scaling from zero to millions of users is an iterative sequence of eliminating single points of failure, decoupling compute from storage, and pushing reads into lower-latency memory tiers. The standard progression moves from a monolithic box &rarr; separate web/DB instances &rarr; horizontal web tier behind a load balancer &rarr; primary/replica database replication &rarr; memory cache &rarr; edge CDN &rarr; async message queues &rarr; database sharding. At each step, state is pushed further away from application servers so web compute remains entirely disposable.

## What I'd forget in 6 months
- **Replication Lag & Read-Your-Own-Writes**: Async master-to-replica replication means a user might update their profile, refresh, and see their old data because their read hit a replica that is 200ms behind. Fix: route reads for the updating user's own data to the primary for a few seconds, or use timestamps/version vectors.
- **Cache Stampede / Thundering Herd**: When a high-traffic cache key expires, hundreds of simultaneous requests miss the cache and hit the database simultaneously, knocking it over. Fix: mutex locking around cache misses or background TTL refresh (probabilistic early expiration / XFetch).
- **Celebrity / Hotspot Shard Problem**: If you shard by `user_id`, Justin Bieber or a viral brand account with 100M followers will overwhelm a single shard while other shards sit idle. Fix: add a random salt to hot partition keys (e.g. `user_id#1..10`) and fan out reads.
- **Resharding cascades**: Using naive modulo sharding `hash(key) % N` means adding 1 new database node changes the destination of almost every single key, triggering a massive data migration. Always use consistent hashing with virtual nodes.

## Interview framing
- **What's the "tell" in a prompt that signals this technique?**
  - "The system has a 100:1 read-to-write ratio" &rarr; Immediately reach for Read Replicas + Cache-Aside (Redis) + CDN.
  - "The service experiences massive traffic spikes at 9 AM or during flash sales" &rarr; Decouple web workers with Message Queues (buffer/leaky bucket) and stateless auto-scaling web tiers.
  - "Data size is expected to exceed 10 TB in year one or write IOPS exceed a single disk" &rarr; Database Sharding / Horizontal Partitioning.
- **What's the one follow-up question an interviewer usually asks next?**
  - *"How do you handle consistency when a read replica falls behind?"* or *"What happens if your cache goes down—does your database survive?"* (Be ready to discuss circuit breakers, fallback caches, and read-your-writes routing).

## Questions I still don't have a crisp answer to
- At what exact IOPS or database size threshold does sharding an existing relational database (e.g. Postgres) become preferable to simply migrating to a managed distributed SQL engine (like CockroachDB, Vitess, or AWS Aurora Serverless)?
- In high-throughput write-heavy workloads where cache-aside write invalidation is too frequent, how do production teams cleanly structure write-behind (write-back) caching without risking data loss on cache node crash?
