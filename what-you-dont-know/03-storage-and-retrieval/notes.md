# 03 — Data structures that power your database (part 1: hash indexes & SSTables/LSM-trees)
Source: Designing Data-Intensive Applications, Kleppmann, ch. 3

*Full detail preserved as requested — this covers everything in the "Data Structures That Power Your Database," "Hash Indexes," and "SSTables and LSM-Trees" sections. B-trees and the direct B-tree/LSM-tree comparison come later in the same chapter and are a separate future addition, not covered here.*

## Read this version first (the simple one)

Every database needs to do two things: take data in, and give it back when asked. The simplest possible way to "take data in" is to just append every new record to the end of a file — nothing is ever overwritten, updates are just new lines added at the end. This is fast to write, because appending is close to the cheapest possible disk operation there is.

The problem is reading it back. If your only storage is "one long file," finding a value means scanning the *entire file* from the start every single time — and that gets linearly slower as the file grows. The rest of this section is entirely about solving that one problem: how do you make reads fast *without* giving up the speed of append-only writes?

Two different answers, in one sentence each:
- **Hash index**: keep an in-memory lookup table mapping every key straight to its exact byte position in the file, so a read becomes "jump directly to that spot" instead of "scan everything."
- **SSTable / LSM-tree**: keep the data on disk *sorted by key*, so you can find things efficiently even with a much smaller in-memory index, and — as a bonus — range queries and efficient merging become possible too.

## The deeper version

### The problem, made concrete with the simplest database imaginable

A key-value store can be built from two shell functions: `db_set` appends a `key,value` line to a file; `db_get` searches the file for the most recent line starting with that key. It genuinely works — you can set a key multiple times, and since old lines are never deleted, `db_get` finds the *last* matching line, i.e., the newest value.

Writes here are excellent: appending to a file is about as fast as a write operation can be. Reads are terrible: `db_get` has to scan the *whole file*, top to bottom, every single time. That's O(n) — double the number of records, and every lookup takes twice as long.

The general fix for "reads are too slow" in any database is an **index**: extra, separately-maintained structure that acts like a signpost pointing you toward the data you actually want, without changing the underlying data itself. The fundamental trade-off to internalize here: **an index only ever helps reads, and it always costs something on writes**, because every index has to be kept up to date every time data changes. This is exactly why databases don't index every column automatically — you (the developer or DBA) choose which indexes are worth their write-cost, based on your actual query patterns.

### Hash indexes — the simplest fix

If your storage is still "just an append-only file," the simplest possible index is: keep an in-memory hash map where every key points to the *byte offset* in the file where its most recent value lives. Writing a new value means appending to the file *and* updating the hash map's offset for that key. Reading means: look up the offset in the hash map, jump straight to that byte position in the file, read the value. No scanning at all.

This is a real, production technique — it's essentially how Bitcask (Riak's default storage engine) works. It performs extremely well as long as **all your keys fit in RAM** (since the hash map itself lives entirely in memory) — values can be much larger than available RAM, since fetching one only costs a single disk seek. This shape of engine is a great fit for workloads where a bounded set of keys gets updated very frequently — the classic example is a "views per video" counter: relatively few distinct keys, huge write volume per key.

**The problem this immediately raises: an append-only file grows forever. How do you not run out of disk?** The answer is **segmentation and compaction**. Once a log file (a "segment") reaches a size threshold, you close it and start writing to a fresh segment. Then, in the background, you run **compaction**: throw away every value for a key except the most recent one within that segment. Because compaction usually shrinks a segment a lot (if keys get overwritten often), you can also **merge** several compacted segments together into one new file at the same time — segments are never edited after being written, so a merge always produces a brand-new file. This merge-and-compact process runs in a background thread while reads and writes keep being served normally from the old segments; once the merged file is ready, reads switch over to it and the old segment files get deleted.

With multiple segments, each one keeps its own in-memory hash map. A lookup checks the newest segment's hash map first, then the next-newest, and so on — merging keeps the total number of segments small, so this doesn't become slow.

### The practical details that make a real implementation work

A handful of unglamorous but essential engineering details sit underneath the simple idea above:

- **File format**: a real engine uses a binary format (length-prefixed strings) rather than something CSV-like, which avoids escaping headaches and is faster to parse.
- **Deleting records**: you can't just remove a line from an append-only file. Deletion is done by appending a special marker — a **tombstone** — for that key; when segments merge, the tombstone tells the merge process to drop all older values for that key.
- **Crash recovery**: the in-memory hash maps vanish on restart. Rebuilding them by re-reading an entire segment file from scratch works, but is painfully slow for large segments — Bitcask speeds this up by periodically snapshotting each segment's hash map to disk, so recovery just reloads the snapshot instead of replaying the whole file.
- **Partially written records**: a crash can happen mid-write, corrupting a record. Bitcask includes checksums so corrupted partial records can be detected and skipped rather than silently corrupting a lookup.
- **Concurrency control**: since writes must be strictly sequential to the log, a common design uses a single writer thread — but because finished segments are immutable, they can be safely read by many threads at once, concurrently, with zero coordination needed.

### Why append-only, specifically, rather than overwriting in place?

This seems wasteful at first — why not just overwrite the old value directly? Three concrete reasons append-only wins:

1. Sequential writes (appending, and the sequential writes involved in merging) are much faster than random writes on spinning disks, and still meaningfully faster even on SSDs.
2. Concurrency and crash recovery get dramatically simpler when segments are append-only/immutable — there's no scenario where a crash leaves you with a file that's half old-value and half new-value spliced together, because nothing is ever overwritten in place.
3. Merging old segments naturally prevents the data file from becoming fragmented over time.

### Where hash indexes hit a wall

Two real limitations motivate the next data structure entirely:

1. **The hash table must fit in memory.** An on-disk hash map is possible in theory, but hard to make perform well in practice — it needs a lot of random-access I/O, is expensive to grow once full, and hash collisions add fiddly complexity.
2. **Range queries don't work.** There's no way to efficiently ask "give me every key between `kitty00000` and `kitty99999`" — a hash map has no concept of nearby keys, so you'd be forced to look each one up individually.

### SSTables — the fix: keep data sorted by key

Take the exact same segment-file idea, but add one requirement: **key-value pairs within a segment are sorted by key**, and each key appears only once per merged segment (which compaction already guarantees). This format is called a **Sorted String Table**, or **SSTable**. Sorting unlocks three real advantages over a plain hash-indexed log:

**1. Merging segments becomes simple and efficient, even when the files are far bigger than available memory.** The process is essentially mergesort: read all input segments side by side, always copy whichever current key is lowest (by sort order) into the output, and repeat — this naturally produces a new, still-sorted, merged segment. When the same key exists in multiple segments, since segments are merged in time order, the newer segment's value simply wins and the older one is discarded.

**2. You no longer need every key held in memory to find things.** If you're looking for `handiwork` and don't know its exact offset, but you *do* know the offsets of `handbag` and `handsome`, sorting guarantees `handiwork` — if it exists — sits between them in the file. So you can jump to `handbag`'s offset and scan forward a short distance until you either find it or pass where it would be. This means the in-memory index only needs to be **sparse** — one entry per few kilobytes of file is plenty, since scanning a few kilobytes is essentially free.

**3. Since a read already has to scan a small range of nearby records anyway, that range can be grouped into a block and compressed before it's written to disk** — each sparse index entry then points at the start of a compressed block. This saves disk space *and* reduces the amount of I/O a read needs to do.

### Building and maintaining SSTables — where memtables come from

Incoming writes arrive in arbitrary key order, so how do you get a file that's sorted? Maintaining sort order *in memory* is easy — well-known balanced tree structures (red-black trees, AVL trees) let you insert in any order and read back in sorted order effortlessly. Maintaining sort order *on disk* directly is much harder (that's what B-trees are for, covered separately in this chapter). So the practical design becomes:

1. Every write first goes into an in-memory sorted tree structure — called a **memtable**.
2. Once the memtable grows past a size threshold (typically a few megabytes), write it out to disk as a new SSTable file — this is cheap, since the tree is already sorted. This becomes the newest segment. Writes continue into a brand-new, empty memtable while the old one is being flushed.
3. A read checks the memtable first, then the most recent on-disk segment, then the next-older one, and so on.
4. A background process periodically merges and compacts segments, same as before, discarding overwritten and deleted values.

**The one gap this leaves: a crash loses whatever's currently sitting in the memtable, since it was never written to disk.** The fix is a separate, unsorted, append-only log on disk that every write hits immediately (structurally identical to the very first log-file idea this whole chapter started with) — its only job is letting you rebuild the memtable after a crash. Once a memtable is safely flushed to an SSTable, its corresponding log can simply be thrown away.

### This is the LSM-tree — and where the name and the real-world engines come from

The scheme above — a memtable, flushed to SSTables, periodically merged and compacted in the background — is essentially what LevelDB and RocksDB (embeddable key-value engine libraries) implement; LevelDB, notably, can be used inside Riak as an alternative to Bitcask. Cassandra and HBase use similar engines, both directly inspired by Google's Bigtable paper, which is actually where the terms "SSTable" and "memtable" originated. The overall technique was originally described under the name **Log-Structured Merge-Tree (LSM-Tree)** by Patrick O'Neil and colleagues, building on earlier log-structured filesystem research — hence "LSM storage engines" as the general category name.

The same underlying idea shows up outside plain key-value storage too: Lucene (the indexing engine behind Elasticsearch and Solr) stores its term dictionary the same way — mapping each search term (the key) to the list of document IDs that contain it (the value, called a *postings list*) — in SSTable-like sorted files that get merged in the background as needed.

### Performance optimizations worth knowing about

**The "does this key even exist" problem.** A lookup for a key that *isn't* in the database is the worst case for an LSM-tree: you must check the memtable, then every segment all the way back to the oldest, potentially hitting disk each time, before you can conclude the key truly isn't there. **Bloom filters** solve this: a memory-efficient probabilistic structure that can tell you, with certainty, when a key is *definitely not* in a given segment — letting you skip disk reads for segments that can't possibly contain the key you're after, without needing to actually store or check every key.

**Compaction strategy — size-tiered vs. leveled.** There's more than one strategy for deciding when and how to merge SSTables:
- **Size-tiered compaction**: newer, smaller SSTables get progressively merged into older, larger ones. HBase uses this.
- **Leveled compaction**: the total key range is split into smaller SSTables, and older data moves into separate "levels" — this lets compaction proceed more incrementally and use less disk space overall. LevelDB and RocksDB use this (it's literally where "LevelDB" gets its name).
- Cassandra supports both, letting you choose per use case.

**The overall payoff.** Despite all these subtleties, the core LSM-tree idea — a cascade of SSTables, continually merged in the background — stays simple and effective even when the dataset is much larger than available memory. Because data ends up sorted on disk, range queries work efficiently, and because the actual disk writes are sequential, LSM-trees can sustain remarkably high write throughput.

## The one mental model to keep

Every technique in this section is answering the exact same question in a progressively more sophisticated way: **"appending to a file is the fastest possible write — how do we get fast reads without giving that up?"** Hash indexes answer it with "remember exactly where everything is." SSTables answer it with "keep things sorted, so you barely need to remember anything, and sorted data brings range queries and cheap merging along for free." Every added complexity in this chapter — segments, compaction, memtables, WALs, Bloom filters — exists purely in service of that one trade-off.

## Terms worth being able to define cold

- **Log** (in this context) — an append-only sequence of records, not necessarily human-readable.
- **Index** — extra structure derived from primary data, purely to speed up reads; always has a write-time cost.
- **Segment** — a bounded, eventually-immutable chunk of an append-only log.
- **Compaction** — discarding all but the most recent value per key within a segment.
- **SSTable** — a segment file with the added guarantee that its key-value pairs are sorted by key, each key appearing once.
- **Memtable** — the in-memory sorted structure (e.g., a red-black tree) that buffers writes before they're flushed to an SSTable.
- **LSM-tree** — the overall technique: a cascade of SSTables, produced from memtable flushes, continuously merged and compacted in the background.
- **Bloom filter** — a probabilistic structure that can definitively rule out "this key isn't here," saving unnecessary disk reads.

## Questions I still don't have a crisp answer to

- How do you choose between size-tiered and leveled compaction for a given workload in practice, beyond "Cassandra lets you pick either"?
- At what actual key-count or data-volume threshold does a hash index (Bitcask-style) stop being the right choice and an LSM-tree become clearly worth the added complexity?

---

## Reference addendum — real-world implementations, Bitcask/Riak, and compaction types
(These points already exist in the sections above; pulled out here as standalone lookup tables so they're easy to find again later without re-reading the full prose.)

### The practical engineering details, as a checklist

These are the unglamorous pieces that turn "keep a hash map of offsets" into a real, crash-safe storage engine:

| Concern | What it means | How it's solved |
|---|---|---|
| **File format** | CSV-style text is slow and needs escaping | Binary format: length-prefixed strings, no escaping needed |
| **Deleting records** | Can't remove a line from an append-only file | Append a **tombstone** marker for that key; merging drops all older values once it sees the tombstone |
| **Crash recovery** | In-memory hash maps vanish on restart | Re-scanning a whole segment works but is slow; Bitcask snapshots each segment's hash map to disk so recovery just reloads the snapshot |
| **Partially written records** | A crash mid-write can corrupt a record | Checksums let corrupted partial records be detected and skipped |
| **Concurrency control** | Multiple writers could corrupt the log | One writer thread appends sequentially; finished segments are immutable, so many readers can read concurrently with zero coordination |

### Bitcask and Riak — the concrete example worth remembering

**Bitcask** is Riak's default storage engine, and it's the real-world implementation of the plain hash-index approach (not SSTables/LSM — this is the simpler, earlier design in the chapter). Worth keeping distinct in your notes because it's a genuinely different trade-off than everything that follows it:

- **Requirement**: every key must fit in RAM, since the hash map lives entirely in memory. Values can be far larger than RAM, since fetching one only costs a single disk seek.
- **Best-fit workload**: a relatively small, bounded set of keys that get updated very frequently — the classic example is a play-count counter per video. Lots of writes, but few distinct keys, so keeping all keys in memory is realistic.
- **Where it breaks down**: once your key count grows too large to fit in memory, or you need range queries (e.g., "every key between X and Y"), Bitcask's approach structurally can't help — this is exactly the gap SSTables/LSM-trees exist to close.

### Real-world software mapped to the data structure it actually uses

| System | Data structure | Notes |
|---|---|---|
| **Bitcask** (Riak's default engine) | Hash index over log segments | The simplest design in the chapter; all keys must fit in RAM |
| **LevelDB** | LSM-tree (memtable + SSTables) | Embeddable key-value library; can also be used inside Riak as a Bitcask alternative; uses **leveled compaction** (where the name comes from) |
| **RocksDB** | LSM-tree (memtable + SSTables) | Also embeddable; uses **leveled compaction**, same lineage as LevelDB |
| **Cassandra** | LSM-tree (memtable + SSTables) | Inspired by Google's Bigtable paper; supports **both** size-tiered and leveled compaction, chosen per use case |
| **HBase** | LSM-tree (memtable + SSTables) | Also Bigtable-inspired; uses **size-tiered compaction** |
| **Lucene** (powers Elasticsearch, Solr) | SSTable-like sorted files for its term dictionary | Not a plain key-value store — key is a search term, value is a *postings list* (document IDs containing that term); same sorted-and-merged-in-background idea applied to full-text search |

Worth noting explicitly: **the terms "SSTable" and "memtable" both originate from Google's Bigtable paper** — LevelDB, RocksDB, Cassandra, and HBase all trace back to that same lineage, even though they're separate projects. The technique itself was formally named **Log-Structured Merge-Tree (LSM-Tree)** by Patrick O'Neil and colleagues, building on earlier log-structured filesystem research — that's where "LSM" in "LSM-tree" comes from, and it predates all of the specific systems in the table above.

### Compaction strategies, compared directly

| Strategy | How it works | Used by |
|---|---|---|
| **Size-tiered** | Newer, smaller SSTables get progressively merged into older, larger ones | HBase; also available in Cassandra |
| **Leveled** | The key range is split into smaller SSTables; older data moves into separate "levels," letting compaction proceed incrementally and use less disk space overall | LevelDB, RocksDB (literally where "LevelDB" gets its name); also available in Cassandra |

Cassandra deliberately supports both, so the choice can be made per use case rather than being locked into the engine's default.

