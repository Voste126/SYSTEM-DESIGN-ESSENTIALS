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

---

# Part 2 — B-trees, comparing B-trees and LSM-trees, and other indexing structures
(Continuing the same chapter 3 notes — this is the second half: the far more common indexing approach, how it stacks up against everything in part 1, and the indexing structures that go beyond a plain key-value index.)

## Read this version first (the simple one)

Part 1 was entirely about log-structured indexes (hash indexes, SSTables, LSM-trees) — append-only, never overwrite in place. **B-trees are the opposite design philosophy**, and they're actually the far more common one: almost every relational database, and plenty of non-relational ones, use B-trees as their default index. Instead of ever-growing segments, a B-tree carves the database into fixed-size pages (typically 4 KB) and *does* overwrite pages in place — which lines up neatly with how disks themselves are physically organized into fixed-size blocks.

Beyond plain key-value indexes, this half of the chapter also covers: how to index more than one column at once, how to index things that aren't sortable numbers or strings (like geographic coordinates), how to search for "close enough" matches instead of exact ones, and what changes when you just keep everything in RAM instead of on disk.

## The deeper version

### How a B-tree actually works

A B-tree is a tree of fixed-size pages, each identified by an address that lets one page reference another — like a pointer, but living on disk. One page is the designated root; every lookup starts there. A page holds several keys plus references to child pages, where each child is responsible for a specific, continuous range of keys — the keys stored in the parent page mark the boundaries between those ranges. You keep following references, narrowing the range at each step, until you reach a **leaf page** that either holds the actual value for a key directly, or a reference to where that value lives.

The number of child references a single page holds is the **branching factor** — typically several hundred in practice, constrained mainly by how much space page references and range boundaries take up. This is what keeps B-trees so shallow: with n keys, the tree depth is O(log n), and because the branching factor is so large, even a huge database usually fits in a tree only three or four levels deep. A concrete sense of scale: a four-level tree of 4 KB pages with a branching factor of 500 can hold up to 256 TB.

**Updating** an existing key is simple: find the leaf page containing it, change the value, write that one page back to disk — every reference pointing at that page stays valid, since its location never changes. **Inserting** a new key means finding the page whose range contains it and adding it there; if that page is full, it **splits** into two half-full pages, and the parent page gets updated to reflect the new subdivision of key ranges. This splitting process is exactly what keeps the tree balanced as it grows.

### Making B-trees crash-safe

The core write operation here — overwriting a page on disk in place — is a fundamentally different physical operation than a log-structured index's "just append." On a spinning disk, it means physically moving the disk head, waiting for the right spot on the platter, then overwriting that sector; SSDs handle it differently but with their own complications (erasing and rewriting entire blocks at once).

The real danger: some operations touch *multiple* pages at once — splitting a page requires writing both new half-pages *and* updating the parent's references. If a crash happens after only some of those writes complete, you can end up with a corrupted tree (e.g., an orphaned page nothing points to). The fix nearly every B-tree implementation uses: a **write-ahead log (WAL)**, an append-only file that every modification is written to *before* it's ever applied to the actual tree pages. After a crash, replaying the WAL restores the tree to a consistent state.

There's a second complication unique to in-place updates: since multiple threads might touch the tree concurrently, you need careful concurrency control — typically **latches** (lightweight locks) protecting the tree's internal structures. This is notably *simpler* in log-structured designs, since all the merging happens in the background without ever interfering with live queries, and old segments get atomically swapped for new ones.

### B-tree optimizations worth knowing

- **Copy-on-write** (used by LMDB, for example) sidesteps the WAL entirely: a modified page is written to a *new* location instead of overwritten, with new parent-page versions created to point at it. This also turns out to help with concurrency control (relevant later for snapshot isolation).
- **Abbreviated keys**: interior pages don't need to store a key's full value, just enough to act as a range boundary — this packs more entries per page, raising the branching factor and reducing tree depth.
- **Sequential leaf layout**: pages can physically live anywhere on disk by default, which is inefficient for range scans (a seek per page). Many implementations try to keep leaf pages in roughly sequential disk order — though that's hard to maintain as the tree grows, which is exactly where LSM-trees have a structural advantage, since their background merges naturally rewrite large chunks sequentially in one pass.
- **Sibling pointers**: leaf pages linking directly to their left/right neighbors lets you scan a range in order without climbing back up to the parent each time.
- **Fractal trees**: a B-tree variant that borrows log-structured ideas to cut down on disk seeks (the name has nothing to do with actual fractals).

### B-trees vs. LSM-trees, head to head

As a rule of thumb: **LSM-trees tend to win on writes, B-trees tend to win on reads** — though real benchmarks are workload-sensitive enough that this needs empirical testing for any specific case, not blind trust in the rule of thumb.

**Where LSM-trees win:**
- A B-tree writes every piece of data at least twice (once to the WAL, once to the actual page — sometimes a page gets written twice just to guard against a partially-updated page surviving a power failure) and always writes a full page even if only a few bytes changed. LSM-trees also rewrite data repeatedly, just via compaction/merging instead — this repeated-rewriting effect in general is called **write amplification**, and it matters a lot on SSDs, which can only survive a limited number of block overwrites before wearing out.
- LSM-trees typically sustain higher write throughput, both because they often have lower write amplification and because they write sequentially (compact SSTable files) instead of overwriting scattered pages — a difference that's especially pronounced on spinning disks.
- LSM-trees usually compress better and produce smaller files, since B-trees leave unused space behind from page splits and pages that don't perfectly fill (fragmentation); LSM-trees periodically rewrite SSTables anyway, incidentally eliminating that fragmentation — especially with leveled compaction.
- (Note: many SSD firmwares already convert random writes into sequential ones internally via their own log-structured logic — so the storage engine's write pattern matters less on SSDs than the theory alone suggests, though lower write amplification and less fragmentation are still genuinely beneficial there.)

**Where B-trees win:**
- Background compaction in an LSM-tree can compete with live reads/writes for limited disk bandwidth — usually a small effect on average throughput, but it can show up as unpredictable spikes at high percentiles (tail latency), where B-trees tend to be more consistent.
- At high write throughput, compaction can fail to keep up with incoming writes if not tuned carefully — unmerged segments then pile up, eating disk space and slowing reads (since more segments means more places to check). Most SSTable-based engines don't throttle incoming writes automatically when this happens, so it needs active monitoring to catch.
- Each key exists in exactly one place in a B-tree, versus potentially several copies across different segments in a log-structured index. This single-location property is genuinely useful for strong transactional guarantees — many relational databases implement transaction isolation using range locks that attach directly to the B-tree structure.

The honest conclusion: B-trees are deeply entrenched and reliably good across many workloads, LSM-trees are gaining ground especially in newer datastores, and there's no universal rule for which wins — it has to be tested against your actual workload.

### Beyond a single primary-key index

Everything so far has really been about a **primary key index** — the thing that uniquely identifies one row/document/vertex. **Secondary indexes** are just as common (e.g., a `CREATE INDEX` in SQL) and are often essential for making joins efficient. The one real difference: secondary index keys aren't unique, so either each index entry stores a *list* of matching row IDs (like a postings list), or the key gets a row ID appended to force uniqueness. Both B-trees and log-structured indexes work fine as secondary indexes either way.

### Where the actual row data lives: heap files, clustered, and covering indexes

An index's value can be either the actual row itself, or a reference to where the row is stored elsewhere. In the latter case, that separate storage area is called a **heap file** — data with no particular order, possibly append-only, or reusing space from deleted rows. The advantage: multiple secondary indexes can all point at the same single copy of the data in the heap, avoiding duplication. Updating a value in place in the heap is cheap if the new value isn't larger than the old one; if it's larger, the record has to move, which means either updating every index that points to it, or leaving a forwarding pointer behind at the old location.

Sometimes that extra hop from index to heap file costs too much for read-heavy workloads, so the actual row gets stored *directly inside* the index instead — this is a **clustered index** (MySQL's InnoDB always makes the primary key a clustered index; SQL Server allows one clustered index per table). A middle ground, a **covering index** (or index with included columns), stores *some* of a table's columns inside the index — enough that certain queries can be answered from the index alone, without ever touching the underlying table. All of these trade write overhead and extra storage for faster reads, and — since they duplicate data — require extra care to keep that duplication transactionally consistent.

### Multi-column and multi-dimensional indexes

A single-key index can't efficiently answer a query touching multiple columns at once. The common fix is a **concatenated index**: combine several fields into one key by literally appending one to another, in a specified order — exactly like an old paper phone book indexed by (lastname, firstname). This works great for "all Smiths" or "all Smith, John" lookups, but is useless for "everyone named John" regardless of last name, since that's not how the sort order is structured.

**Multi-dimensional indexes** solve a fundamentally different problem: querying several columns *simultaneously* in a genuinely two-way (or more) sense — the canonical example being geospatial search (find all restaurants within a rectangular map region). A standard B-tree or LSM-tree can efficiently give you a range on latitude *or* longitude, but not both together. Solutions include translating 2D coordinates into a single number via a space-filling curve (then using an ordinary B-tree), or purpose-built structures like **R-trees** (used by PostGIS via PostgreSQL's generalized search-tree indexing). This idea isn't limited to geography either — a 3D index over (red, green, blue) could power color-based product search, or a 2D index over (date, temperature) could efficiently answer "all 2013 readings between 25–30°C" without scanning everything by one dimension and filtering by the other (an approach used by HyperDex).

### Full-text search and fuzzy matching

Everything above assumes you know the exact key you want. **Fuzzy querying** — matching misspellings, synonyms, grammatical variants, or words near each other — needs different techniques entirely. Lucene, for instance, can find matches within a given **edit distance** (how many single-character insertions/removals/substitutions separate two words) by representing its term dictionary's in-memory index not as a sparse list of offsets (like LevelDB) but as a **finite state automaton** over the characters in the keys — essentially a trie — which can then be transformed into a Levenshtein automaton to support efficient edit-distance search. Beyond this, more advanced fuzzy techniques move into document classification and machine learning territory.

### In-memory databases

Every data structure discussed in this chapter exists because of disk's specific limitations — disks need careful data layout, but they're durable (survive power loss) and cheap per gigabyte compared to RAM. As RAM gets cheaper, that cost argument weakens, and many real datasets are small enough to just live entirely in memory, sometimes distributed across multiple machines.

Not all in-memory stores are the same:
- **Cache-only** (e.g., Memcached) — acceptable to lose everything on restart.
- **Durable in-memory databases** — durability achieved via battery-backed RAM, an on-disk change log, periodic snapshots, or replication to other machines. Even though these write to disk, they're still "in-memory" because reads are served entirely from RAM; disk is purely for durability, with the side benefit that on-disk files can be backed up and inspected with ordinary tools.

Counterintuitively, **the speed advantage of in-memory databases usually isn't about avoiding disk reads** — a disk-based engine with enough RAM barely touches disk anyway, since the OS caches recently-used blocks in memory regardless. The real advantage is avoiding the overhead of encoding in-memory structures into a disk-writable format at all.

In-memory databases also unlock data models that are awkward to build on top of disk indexes — Redis's priority queues and sets are comparatively simple to implement precisely because everything just lives in memory. Newer research (the "anti-caching" approach) extends this further: evict least-recently-used data to disk when memory runs low, reload it on demand — similar to OS virtual memory/swap, but operating at the granularity of individual records rather than whole memory pages. This still requires the *index* itself to fit fully in memory (the same constraint Bitcask has). Non-volatile memory (NVM) hardware may eventually reshape storage engine design further, but that's still an active research area.

## The one comparison table worth memorizing

| | B-trees | LSM-trees (log-structured) |
|---|---|---|
| **On-disk layout** | fixed-size pages (~4KB), overwritten in place | variable-size segments, append-only, never modified in place |
| **Typical strength** | reads | writes |
| **Crash safety mechanism** | write-ahead log (WAL) | none needed for segments themselves; memtable needs its own WAL |
| **Concurrency control** | latches (locks) on shared mutable structure | simpler — background merges don't block live queries |
| **Key uniqueness on disk** | exactly one copy per key | possibly several copies across segments until compacted |
| **Write amplification** | at least 2x (WAL + page), often more | also present, via repeated compaction/merging |
| **Storage compactness** | fragmentation from page splits/partial pages | tends to compress better, especially with leveled compaction |
| **Tail latency predictability** | more predictable | can spike during compaction |
| **Best fit for strong transactional locking** | yes — locks attach directly to tree structure | harder, since one key can exist in multiple places |

## Terms worth being able to define cold

- **Page (B-tree)** — a fixed-size block (commonly 4KB) that's the basic unit of read/write.
- **Branching factor** — how many child references one B-tree page holds; typically in the hundreds.
- **Write-ahead log (WAL)** — an append-only log every change is written to before it touches the actual tree, for crash recovery.
- **Write amplification** — one logical write causing multiple physical disk writes over a system's lifetime.
- **Heap file** — unordered storage for actual row data, referenced by one or more indexes.
- **Clustered index** — an index that stores the actual row data directly, not just a reference to it.
- **Covering index** — an index storing enough extra columns that some queries never need to touch the underlying table at all.
- **Concatenated index** — a multi-column index built by literally appending one field's value to another's.
- **R-tree** — a spatial index structure supporting true multi-dimensional range queries (e.g., geographic search).
- **Edit distance** — the number of single-character changes separating two strings; the basis of fuzzy/typo-tolerant search.

## Questions I still don't have a crisp answer to

- In practice, how do teams actually decide "our compaction can't keep up" before it becomes an incident, given the book notes most engines don't throttle writes automatically?
- Is the "B-trees for reads, LSM-trees for writes" rule of thumb still broadly true today, or has it shifted as SSDs (with their own internal log-structured firmware) have become the default storage medium?



---

# Part 3 — OLTP vs. OLAP, data warehousing, and column-oriented storage
(Continuing the same chapter 3 notes. This part is deliberately split into two clearly separate topics, as requested: data warehousing first, column-oriented storage second, with the second one built up from zero for someone meeting it for the first time.)

## Topic A: Transaction processing vs. analytics — read this first (the simple one)

Every database access pattern falls roughly into one of two shapes:

- **OLTP (online transaction processing)**: the pattern behind almost every user-facing app. Look up a *small* number of records by key ("this user's profile," "this order"), read or write them, done. High volume of requests, each one touching very little data. Disk *seek time* is usually the bottleneck.
- **OLAP (online analytic processing)**: the pattern behind business reporting and dashboards. Scan a *huge* number of records, but only a handful of columns per record, and boil it all down into an aggregate (a sum, an average, a count). Low volume of queries, but each one is enormous. Disk *bandwidth*, not seek time, is usually the bottleneck.

**Why they ended up on separate databases entirely**: an OLTP database has to stay fast and available for real users — a business analyst running a sprawling ad hoc query against it would scan huge chunks of data and could visibly slow down real customer transactions happening at the same time. The fix that emerged: copy the data out into a completely separate, read-only database built specifically for heavy scanning — a **data warehouse** — so analysts can query however they like without ever touching the live system.

### Getting data into the warehouse: ETL

Data warehouses don't invent new data — they copy it in from every OLTP system in the business (the customer website, point-of-sale systems, inventory tracking, supplier management, and so on), each of which typically operates as its own independent, autonomously-run system. That copying process is called **Extract–Transform–Load (ETL)**: pull data out of each source system, reshape it into a schema suited for analysis and clean it up, then load it into the warehouse. It's why data warehouses are common in large enterprises (many separate OLTP systems worth consolidating) and nearly nonexistent in small companies (one small database is often small enough to just query directly, or even analyze in a spreadsheet).

### Star schemas — the standard shape of warehouse data

Unlike OLTP, where data models vary a lot by application, warehouse schemas converge on one dominant pattern: the **star schema**. At the center is a **fact table**, where each row represents one event — a single purchase, a single page view, a single click — at a specific point in time. Some columns in the fact table are plain attributes (the sale price, say); others are foreign keys pointing out to **dimension tables**, which describe the *who, what, where, when, how, why* of that event (which product, which store, which customer, which date). Drawn out, the fact table sits in the middle with dimension tables radiating outward like the points of a star — hence the name.

A **snowflake schema** is the same idea taken one step further: dimensions themselves get broken down into sub-dimensions (e.g., a product's brand and category become their own separate tables rather than plain strings inside the product dimension). This is more normalized, but star schemas are usually preferred anyway, because they're simpler for analysts to actually query. Fact tables in a real warehouse are routinely huge — tens of petabytes at the scale of a major retailer — and individual tables (fact *or* dimension) are often extremely wide, sometimes hundreds of columns, since a dimension table tends to accumulate every piece of metadata that might ever be relevant to some future analysis.

> **The one thing to remember about this whole topic:** a data warehouse isn't a different *technology* so much as a different *purpose* — same relational/SQL interface on the surface in most cases, but internally optimized for "scan millions of rows, touch few columns, aggregate" instead of "find one row by key, fast." That mismatch in purpose is exactly what motivates everything in the next topic.

---

## Topic B: Column-oriented storage — built from zero

*This section assumes no prior exposure to the idea at all — if you've only ever thought about rows, this rebuilds the concept from the ground up.*

### Step 0 — the problem that makes this necessary

Picture a warehouse fact table with over 100 columns — price, tax, discount, employee ID, store ID, timestamp, and on and on. Now picture a typical analytics query: something like "what's the total quantity sold for fruit and candy, broken down by day of the week, in 2013." That query only actually needs **three** of those hundred-plus columns: the date, the product category, and the quantity. Every other column is dead weight for this particular question — but a traditional storage layout can't skip loading them.

### Step 1 — why "traditional" storage is the wrong shape here

Almost every OLTP database (and document databases too) stores data **row-oriented**: every value belonging to one row sits physically next to each other on disk, so reading "row 42" means reading one contiguous chunk. This is exactly right when your query wants *one whole row* (a user's profile, an order) — which is the OLTP access pattern. But for our fruit-and-candy query, a row-oriented engine still has to pull every single one of those 100+ columns off disk for every matching row, just to throw away 97 of them after reading only 3. You pay the disk cost for data you never asked for.

### Step 2 — the column-oriented idea, in one sentence

**Instead of storing everything from one row together, store everything from one column together.** Give each column its own file (or contiguous chunk). Now, our query only needs to open and read *three* files — `date`, `category`, `quantity` — completely ignoring the other 97+, cutting the amount of data pulled from disk dramatically. The one rule that makes this work: every column file must store its values in the *same row order*, so the 23rd entry in every column file always belongs to the same underlying row — that's the only way to reassemble a full row later if you ever need to.

### Step 3 — column storage compresses beautifully (and here's exactly how)

Columns tend to have far fewer distinct values than there are rows — a retailer might have billions of sales rows but only a few hundred thousand distinct products, or a few hundred distinct countries. This repetitiveness is what makes columns compress so well, and one especially effective technique for it is **bitmap encoding**:

1. Take a column with *n* distinct values (say, `product_sk` with 100,000 distinct products).
2. Create *n* separate bitmaps — one per distinct value — each with exactly one bit per row in the table.
3. In the bitmap for product X, a row's bit is `1` if that row sold product X, `0` otherwise.

If *n* is small, storing one bit per row per bitmap is already compact. If *n* is large, most bitmaps end up mostly zeros ("sparse"), so they get **run-length encoded** on top (storing "40,000 zeros, then a 1, then 200,000 zeros" instead of literally writing out every bit) — shrinking things dramatically further.

**Why this specific format is so useful, not just compact:** a query like "find rows where product is 30, 68, or 69" becomes a bitwise **OR** across three bitmaps — a famously cheap CPU operation. A query like "product 31 AND store 3" becomes a bitwise **AND** across two bitmaps. Both work correctly specifically *because* every column's bitmap lines up row-for-row — the k-th bit always means the same row across every bitmap in the table.

*(Side note worth flagging: Cassandra and HBase's "column families," inherited from Bigtable, are not actually this technique — within a column family they store an entire row's columns together, with no column compression. Despite the name, that design is still fundamentally row-oriented.)*

### Step 4 — column storage also helps the CPU, not just the disk

Once data physically fits comfortably in a CPU's L1 cache (which compressed column data does far more easily than fat, uncompressed rows), a query engine can iterate through it in a tight, function-call-free loop — which a CPU executes dramatically faster than code full of per-record branching and function calls. Techniques like bitwise AND/OR operate directly on these compressed chunks. This overall approach — designing operators to work on compact chunks of column data at once, rather than one value at a time — is called **vectorized processing**.

### Step 5 — sort order turns compression up even further

Row order within a column store doesn't strictly matter (insertion order is the simplest default — a new row just appends to every column file). But choosing to *impose* a sort order — the same way SSTables do — can make queries much faster and compression much better. The critical rule: **you can't sort each column independently**, or you'd lose the row-alignment that lets you reconstruct anything. Sorting has to happen at the level of "pick full rows in this order," even though the data is *physically stored* by column.

Pick your primary sort key based on your most common query pattern — if analysts mostly filter by recent date ranges, sorting by `date` first lets a query skip straight to the relevant chunk instead of scanning everything. A second sort key then orders any rows that tie on the first key (e.g., sort by product within each date, so same-product-same-day sales end up physically adjacent). And sorting supercharges compression: a low-cardinality column that's been sorted ends up with *long unbroken runs* of the same repeated value, which run-length encoding can crush down to almost nothing — even across billions of rows. This effect is strongest on the *first* sort key and gets progressively weaker on the second, third, and so on, since those columns are only sorted "within ties" of the columns before them.

**Taking it further — multiple sort orders at once.** Since data usually needs to be replicated across machines for durability anyway, why not store each replica sorted a *different* way, and let the query optimizer pick whichever replica's sort order best matches the query at hand? (This is the approach taken by C-Store and its commercial descendant, Vertica.) It's conceptually similar to having several secondary indexes on a row store — except a column store's "alternate sort orders" hold the actual data itself, not just pointers back to it.

### Step 6 — the catch: writes get harder

Everything above optimizes reads at the direct expense of writes. You cannot update a compressed, sorted column file in place the way a B-tree overwrites a page — inserting one row in the middle of a sorted table could mean rewriting entire column files. The fix should look familiar: **use the LSM-tree approach from earlier in this chapter.** Writes land first in an in-memory sorted buffer (row- or column-oriented, doesn't matter at this stage); once enough writes accumulate, they get merged into the on-disk column files in bulk, all at once. A query simply checks both the in-memory buffer and the on-disk columns and combines results — the query optimizer hides that split from the person writing the query, so as far as an analyst is concerned, a just-inserted row shows up immediately in the next query.

### Step 7 — pre-computing the aggregates: materialized views and data cubes

If many different queries all compute the same aggregate (say, total sales by store, over and over), it's wasteful to recompute it from raw data every single time. A **materialized view** is the fix: unlike a normal (virtual) SQL view — which is just a saved query, expanded and re-run every time you read it — a materialized view is an actual, physical copy of a query's *results*, written to disk once and reused. The cost: whenever the underlying data changes, the materialized view has to be updated too, which makes writes more expensive — exactly why these are rare in OLTP but genuinely useful in a read-heavy warehouse.

A **data cube** (or OLAP cube) is a specific, common flavor of materialized view: a grid of pre-computed aggregates across multiple dimensions at once. With two dimensions (say, date and product), you get a 2D grid where each cell holds the aggregate (a sum, say) for that exact date-product combination — and you can further collapse rows or columns to get "total by product regardless of date" or "total by date regardless of product" essentially for free. With five dimensions (date, product, store, promotion, customer — a realistic warehouse scenario) the same idea extends into a five-dimensional structure, impossible to draw but identical in principle.

**The genuine trade-off**: a data cube makes specific, anticipated queries (like "total sales per store yesterday") extremely fast, since the answer is already sitting there precomputed. But it loses the flexibility of the raw data — if "price" was never one of the cube's dimensions, you simply cannot later ask "what fraction of sales came from items over $100," no matter how the existing dimensions are sliced. This is exactly why most warehouses keep the full raw fact table around regardless, and treat cubes purely as a targeted performance boost for known, frequent queries — not a replacement for the underlying data.

## The one comparison table worth keeping for this whole topic

| | Row-oriented storage | Column-oriented storage |
|---|---|---|
| **Best fit** | OLTP: fetch one whole row by key | OLAP: scan millions of rows, touch few columns |
| **Physical layout** | all of one row's values stored together | all of one column's values stored together |
| **Compression** | limited (mixed data types per row) | excellent — repetitive values, bitmap + run-length encoding |
| **Writes** | in-place updates work fine (B-trees) | hard — needs an LSM-style buffered-write approach |
| **CPU efficiency** | more branching, more function calls per record | vectorized processing on compact chunks |
| **Bottleneck it targets** | disk seek time | disk bandwidth + CPU cache efficiency |

## Terms worth being able to define cold

- **OLTP / OLAP** — transaction-processing vs. analytics access patterns; small-lookups-by-key vs. huge-scans-with-aggregation.
- **Data warehouse** — a separate, read-optimized copy of an organization's OLTP data, built specifically for analysts.
- **ETL** — Extract, Transform, Load: the pipeline that populates a data warehouse from source OLTP systems.
- **Star schema** — a fact table (events) surrounded by dimension tables (context), the standard warehouse data shape.
- **Snowflake schema** — a more normalized star schema, with dimensions broken into sub-dimensions.
- **Column-oriented storage** — storing each column contiguously instead of each row, so queries only load the columns they actually need.
- **Bitmap encoding** — representing a column's distinct values as one bitmap per value, enabling cheap bitwise AND/OR queries.
- **Vectorized processing** — operating on compact chunks of compressed column data in tight loops, exploiting CPU cache and avoiding per-record overhead.
- **Materialized view** — a query's results, physically saved to disk, instead of recomputed on every read.
- **Data cube (OLAP cube)** — a materialized view of aggregates across multiple dimensions simultaneously.

## Questions I still don't have a crisp answer to

- In practice, how do teams decide which columns get the "first sort key" privilege when there are several equally common query patterns competing for it?
- Is the "keep the raw fact table around regardless of cubes" advice still the default in modern warehouses, or have improvements in raw-scan performance (columnar formats, better compression) made cubes less necessary than they used to be?
