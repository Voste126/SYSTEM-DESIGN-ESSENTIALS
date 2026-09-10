# 02 — Data models: relational, document, and the ghosts of the 1970s
Source: Designing Data-Intensive Applications, Kleppmann, ch. 2 (part 1: relational vs. document model)

## Read this version first (the simple one)

Every app is really a stack of translations: real-world things (people, jobs, money) → objects in your code → a general-purpose data model (tables, JSON, graphs) → bytes on disk → electricity. Chapter 2 is entirely about that third layer — how you choose to shape data before it hits storage.

Two shapes dominate:

- **Relational (tables)**: data lives in separate tables, linked by IDs (foreign keys). A person's job history lives in a *different table* than the person, connected by `user_id`. To get the full picture, you *join* the tables back together.
- **Document (JSON)**: one record is one nested blob. A person's job history lives *inside* their own document, as a list. To get the full picture, you just... read the document. No join needed.

The catch, in one sentence: **documents are great when the data is a tree (one thing has many of another thing, and that's it), but painful when the data is a web (many things reference many other things).** Relational databases are the mirror image — joins are their whole reason for existing, so many-to-many is comfortable, but a simple "one resume has many jobs" forces you into extra tables you didn't conceptually need.

## The deeper version

**Object-relational mismatch.** Your code thinks in objects; SQL thinks in rows and columns. The translation layer (ORMs like Hibernate, ActiveRecord) reduces boilerplate but never fully hides the seam.

**Why IDs instead of strings (normalization).** Storing `"Greater Seattle Area"` directly in every row duplicates that string everywhere it's used. Storing `region_id: 91` and looking the name up once avoids that duplication — the tradeoff is that now you need a way to resolve the ID back to a name, which is exactly what a join does. IDs also don't need to change even if the human-readable name does (a city renaming doesn't break every record referencing it).

**Locality is the document model's real selling point.** A JSON document is stored as one continuous blob, so fetching an entire profile is one read. The relational equivalent needs either multiple queries or a multi-way join across several tables. The catch: that locality advantage disappears the moment you only need part of the document, since the database still has to load the whole thing — and most writes to a document require rewriting the entire thing, not just the changed field.

**The historical loop (this is the part that reframed the whole chapter for me).** This debate isn't new — it's literally the same fight databases had in the 1970s:
- **Hierarchical model (IBM's IMS, 1968)**: data as nested trees. Great for one-to-many, terrible for many-to-many. Sound familiar? That's structurally the same shape as a document database.
- **Network model (CODASYL)**: fixed the many-to-many problem by allowing a record to have multiple parents — but the only way to find data was to manually follow a specific chain of pointers ("access paths") that a programmer had to memorize. Even the people who designed it described it as navigating an n-dimensional space in your head.
- **Relational model (Codd, 1970)**: threw out access paths entirely. Just declare what you want; a query optimizer figures out how to get it, built once, benefiting every application that ever uses that database. This is *why* relational won the 1970s debate — not because tables are inherently superior to trees, but because "ask a question, let the system find the fastest path" beats "memorize the path yourself" as an engineering strategy at scale.

Document databases today are, in a real structural sense, replaying the hierarchical model's strengths and weaknesses — they just didn't inherit CODASYL's pointer-chasing solution to many-to-many. They resolve many-to-many the same way relational databases do: a reference (ID) resolved at read time — they just call it a "document reference" instead of a "foreign key."

**Schema-on-read vs. schema-on-write.** Document databases typically don't enforce any schema — the *reading* code decides how to interpret whatever fields happen to be there (schema-on-read). Relational databases enforce a schema up front, at write time (schema-on-write). This is the same philosophical split as dynamic vs. static typing in programming languages, and just like that debate, neither side is objectively correct — it depends on whether your data is naturally uniform (schema-on-write shines) or naturally heterogeneous / externally-controlled (schema-on-read shines). One practical wrinkle: `ALTER TABLE` is near-instant in Postgres but can lock the whole table for hours in MySQL, which is where "schema changes are slow and scary" reputations mostly come from — it's implementation-specific, not inherent to the relational model.

## The one metaphor that actually made the network-model section click

The network model's "access paths" are like navigating a building by memorizing specific hallways from memory — if the layout changes, you're lost until you re-memorize the new route. The relational model's query optimizer is a building directory: you ask "where's room 214," and it finds the current fastest route for you, automatically, even after the building gets renovated. You never had to memorize anything in the first place.

## Where I've seen this go wrong in something I've actually worked on

*(fill in — a schema that started clean and became either an over-normalized join nightmare, or an under-normalized document blob that couldn't answer a "which users are in region X" query)*

## How this differs from the interview-book treatment of the same idea

Alex Xu's book treats "SQL vs. NoSQL" as a scale/latency decision — pick NoSQL when you need to go faster or bigger. Kleppmann's actual point is subtler and, honestly, more useful day to day: the deciding factor isn't raw scale at all, it's **the shape of your relationships**. A document model that fits beautifully today can become awkward not because load grew, but because a *feature* got added (recommendations, linked organizations) that turned a one-to-many tree into a many-to-many web.

## Terms worth being able to define cold

- **Impedance mismatch** — the friction between objects in code and rows/columns in storage.
- **Normalization** — removing duplication by referencing shared data via an ID instead of copying it everywhere.
- **Schema-on-read vs. schema-on-write** — who enforces structure, and when.
- **Locality** — whether related data is physically stored together, and whether that helps you (only if you need most of it at once).
- **Polyglot persistence** — using different data models for different parts of the same system, rather than forcing everything into one.

## Questions I still don't have a crisp answer to

- At what point does a "mostly one-to-many, occasionally many-to-many" data shape tip from "fine in documents, denormalize the rare case" to "should have been relational from day one"?
- Is schema-on-read actually cheaper long-term, or does it just move the cost from a visible migration to invisible scattered `if (!user.first_name)` checks throughout the codebase?
