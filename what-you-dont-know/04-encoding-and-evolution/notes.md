# 04 — Encoding and evolution (part 1: formats for encoding data)
Source: Designing Data-Intensive Applications, Kleppmann, ch. 4 (through Thrift/Protocol Buffers and the start of schema evolution — the chapter continues into JSON-schema formats like Avro and modes of dataflow like REST/RPC/message queues, covered separately later)

*Written assuming zero prior exposure to this topic — start at the glossary if any term below is unfamiliar.*

## Glossary — read this first if you're new to the topic

- **Encoding (= serialization = marshalling)** — turning an in-memory object (with pointers, references, live structure) into a flat sequence of bytes you can write to a file or send over a network.
- **Decoding (= parsing = deserialization = unmarshalling)** — the reverse: turning that byte sequence back into an in-memory object.
- **Schema** — a definition of what fields exist, in what order, and what type each one is.
- **Backward compatibility** — newer code can correctly read data that was written by older code.
- **Forward compatibility** — older code can correctly read data that was written by newer code (harder, because old code has to gracefully ignore things it's never seen before).
- **Field tag** — a small number that identifies a field, used instead of a field name, in schema-based binary formats like Thrift and Protocol Buffers.

## Why this whole topic exists in the first place

Applications change constantly — new features mean new fields, new record types, or old data needing to be read in a new way. In a small system you'd just update everything at once and move on. Real systems can't do that: server-side deployments roll out gradually across many machines (a rolling upgrade), and client-side apps update whenever the *user* feels like installing an update — sometimes never. The practical consequence: **old code, new code, old data, and new data all end up coexisting in the same system at the same time**, and everything still has to keep working. That's the entire problem this chapter is about.

## Two representations, one translation problem

While a program is running, data lives in memory as objects, structs, arrays, hash tables — structures built around pointers, optimized for the CPU to manipulate quickly. The moment you need to write that data to a file or send it over a network, pointers become meaningless (a memory address on your machine means nothing to a different process, let alone a different machine) — so you need a **self-contained** byte representation instead. Translating from the in-memory shape to that byte sequence is **encoding**; translating back is **decoding**. (Note: "serialization" is the more common everyday term, but this book reserves that word for a different meaning entirely in the transactions chapter, so it deliberately says "encoding" instead — worth knowing so the terminology doesn't confuse you later.)

## Why your programming language's built-in encoder is a trap

Most languages ship a built-in way to serialize objects (Java's `Serializable`, Python's `pickle`, Ruby's `Marshal`, and similar). These feel convenient — almost zero extra code — but they carry real, structural problems:

1. **Lock-in**: the format is tied to that specific language. Committing to it means committing your data to that language indefinitely, and makes integrating with any system written in a different language painful or impossible.
2. **A genuine security hole**: decoding often requires the ability to instantiate *arbitrary* classes to reconstruct the original object graph. If an attacker can get your application to decode a byte sequence they control, that "instantiate anything" capability can be turned into arbitrary code execution — this isn't a hypothetical, it's a well-documented class of real vulnerability.
3. **Versioning is usually an afterthought**: these formats were built for quick save/restore, not for the forward/backward compatibility problem this whole chapter cares about.
4. **Performance is often bad**: some of these encoders (Java's built-in serialization is the frequently-cited example) are notoriously slow and produce bloated output.

**The practical rule this leads to**: don't use your language's built-in serialization for anything beyond short-lived, throwaway purposes.

## Textual formats: JSON, XML, and CSV — good enough, with real sharp edges

These are the obvious next step up: standardized, language-independent, human-readable. JSON won out over XML mostly because it's simpler and browsers understand it natively (it's literally a subset of JavaScript syntax). But all three have subtler problems than just "verbose" or "ugly":

- **Number ambiguity.** XML and CSV can't distinguish a number from a string of digits without an external schema telling you which it is. JSON *does* distinguish strings from numbers, but doesn't distinguish integers from floating-point, and specifies no precision at all. This bites in a very concrete way: a 64-bit integer larger than about 9 quadrillion (2^53) can't be represented exactly by the IEEE 754 double-precision floats that JavaScript uses for all its numbers — so genuinely large integers silently lose precision when parsed in JavaScript. Twitter's actual workaround for this: every tweet ID appears *twice* in their API responses — once as a plain JSON number (which JavaScript will mangle) and once as a string (which won't lose precision) — purely to route around this limitation.
- **No native binary data.** JSON and XML handle Unicode text beautifully but have no way to represent a raw sequence of bytes that isn't text. The common workaround is Base64-encoding binary data into a text string — functional, but it inflates the data size by about 33%, and needs a schema on the side just to say "by the way, decode this field as Base64."
- **Schemas are optional, and that optionality has teeth.** Both XML and JSON support schema languages, but they're powerful enough to be genuinely complex, and plenty of JSON tooling skips them entirely — which means the correct way to interpret ambiguous data (is this a big number or a string? is this Base64?) often ends up hardcoded into application logic instead of declared anywhere machine-readable.
- **CSV has essentially no schema at all** — meaning your application, not the format, has to define what each column means, and there's no structured way to handle a newly added column. Its escaping rules (what happens when a value contains a comma or a newline) are formally specified, but not every parser actually implements the spec correctly.

Despite all of this, these formats remain genuinely good enough for a lot of real use — especially for exchanging data *between organizations*, where simply getting everyone to agree on a shared format at all is a bigger challenge than optimizing that format's efficiency.

## Binary encodings of JSON: same model, smaller bytes — but not by much

Once data volume gets large (terabytes, not megabytes), the size and parsing cost of a purely textual format starts to matter, which motivated a whole family of binary encodings for JSON (MessagePack among the best known) and XML. These formats don't change the underlying data model — they still have no schema of their own — which means **every field name still has to be spelled out inside the encoded bytes**, since there's no schema anywhere else to say what field 1, field 2, etc. actually mean.

**A worked example, byte by byte.** Take this small record: a username, a favorite number, and a list of interests. Encoded with MessagePack, the byte stream starts by tagging what's coming: one byte says "an object follows, with exactly 3 fields," the next byte says "a string follows, 8 bytes long" (the length of the field name `userName` itself), then those 8 literal ASCII bytes spell out `userName`, then a byte marks "here's a 6-byte string" followed by the literal bytes for `Martin`, and so on for every field. **The field's name is data, embedded directly in every single encoded record** — that's the structural cost of having no schema.

The actual payoff here is smaller than you'd expect: this record comes out to 66 bytes in MessagePack, versus 81 bytes as plain whitespace-free JSON text. A real reduction, but not a dramatic one — and it raises the obvious question the chapter answers next: can you do meaningfully better than "same model, marginally smaller"?

## Thrift and Protocol Buffers: the answer is "yes, if you add a schema"

Thrift (originally Facebook) and Protocol Buffers/protobuf (originally Google) both take a fundamentally different approach: **the schema is defined separately, ahead of time**, in a small interface-definition language, and a code generator produces classes in your target language(s) from that schema. Your application then encodes and decodes through that generated code rather than hand-rolling anything.

The schema for that same username/favorite-number/interests record looks structurally identical in both — a small block naming each field, giving it a type, and critically, giving it a small integer: its **field tag** (1, 2, 3, in order).

**What actually changes in the encoded bytes**: field *names* disappear from the wire format entirely. Instead of embedding the literal text `userName` in every record, the encoded data just contains the number `1` next to that field's value — the number that maps back to `userName` only via the schema, which both sides already have a copy of. This is the entire trick that makes these formats so much more compact.

Concretely, for that same record: Thrift's BinaryProtocol brings it down to 59 bytes; Thrift's CompactProtocol — which packs a field's type and tag into a single byte and uses variable-length integers (small numbers use fewer bytes; the top bit of each byte says "more bytes follow" or not) — gets it to 34 bytes; Protocol Buffers, doing something very similar to CompactProtocol, lands at 33 bytes. Compare that to MessagePack's 66 bytes for the identical data, and you can see exactly where the schema-based approach earns its complexity: nearly half the size, purely by not having to spell out field names on every single record.

One small but important schema detail: marking a field `required` versus `optional` changes nothing about how it's physically encoded — the wire format has no concept of "required" at all. The only effect is a *runtime check*: required fields get validated as present, which is useful for catching bugs, but it's a code-level guarantee, not a wire-format one — worth remembering, because it becomes directly relevant to the compatibility rules below.

## Field tags: the mechanism that makes schema evolution actually work

An encoded Thrift/protobuf record is just its fields, one after another, each one tagged with its number and its type; a field that isn't set is simply omitted entirely. This has a genuinely elegant consequence for evolving a schema over time:

- **You can rename a field freely.** The encoded bytes never contain field names at all — only tag numbers — so renaming in the schema changes nothing about existing encoded data.
- **You must never change a field's tag number.** The tag is the *only* thing tying an encoded value back to its meaning; changing it would silently invalidate every piece of data ever encoded under the old tag.
- **Adding a new field is safe for forward compatibility**, as long as it gets a brand-new tag number. Old code, encountering a tag number it's never seen, simply skips over it — the type annotation tells it exactly how many bytes to skip, without needing to understand what the field *means*. This is precisely what lets old code correctly read data written by newer code.
- **Adding a new field is safe for backward compatibility too — but only if it's optional (or has a default value), never `required`.** If new code writes a record that includes a newly-added required field, and old data (written before that field existed) gets read by the new code, the required-field check would fail, since the old data genuinely never wrote that field. Every field added after a schema's initial deployment has to tolerate simply not being there in older data.
- **Removing a field mirrors adding one, with the compatibility directions reversed**: you can only ever remove a field that was optional to begin with (a required field can never be safely removed, since some old code somewhere might still expect it), and — critically — you can never reuse that tag number for something else later, because old data still floating around in your system may still contain a value under that old tag, and reusing it would make new code misinterpret old bytes as a completely different field.

## The one mental model to keep from this whole page

Every technique here is really answering one question, at increasing levels of sophistication: **"how do two pieces of code, written and deployed at different times, agree on what a sequence of bytes means?"** Language-native serialization answers it badly (only works if it's the same language, same version, mostly). Textual formats answer it loosely (self-describing field names, but ambiguous types). Schema-based binary formats answer it precisely (a tag number is a stable, permanent contract between the schema and the bytes) — and that precision is exactly what makes real backward/forward compatibility rules possible to state and enforce at all.

## Terms worth being able to define cold

- **Rolling upgrade (staged rollout)** — deploying a new version to a few servers at a time rather than everywhere at once, to avoid downtime.
- **Self-describing data** — a format where the data itself states what each field is called (JSON, MessagePack), as opposed to relying on an external schema.
- **Field tag** — the small integer identifying a field in Thrift/Protocol Buffers, standing in for the field's name on the wire.
- **Variable-length integer encoding** — a technique where small numbers take fewer bytes than large ones, using a marker bit to say "more bytes follow."

## Questions I still don't have a crisp answer to

- Given how much smaller protobuf/Thrift are than MessagePack, why does JSON (or its binary variants) remain so dominant for public web APIs rather than schema-based binary formats?
- Is there a practical limit to how many times a schema can evolve (fields added and retired) before the accumulated "never reuse this tag" history becomes a real maintenance burden?

---

# Part 2 — Modes of dataflow (databases, services, and RPC)
(Continuing the same chapter 4 notes. Part 1 covered *how* to encode data; this part covers *who* is encoding and decoding it, and how that relationship changes across three different situations: databases, service calls, and RPC.)

## The one idea that ties this whole part together

Compatibility (forward and backward) is fundamentally a relationship between **whoever encoded some data** and **whoever later decodes it**. That relationship looks completely different depending on *how* data actually travels between those two parties — through a shared database, through a request/response service call, or through something trying to disguise itself as a local function call (RPC). Each of the five sections below is really just: "here's this same compatibility problem, showing up in a different shape."

## Topic A: Dataflow through databases

The simplest way to think about a database: the process that writes is the encoder, the process that reads later is the decoder — and if it's literally the same process reading its own earlier write, **you can think of a database write as sending a message to your own future self**. Backward compatibility is obviously required here, or your future self can't even read what you wrote.

**The twist unique to databases**: it's just as common for a database to have many processes accessing it *concurrently* — different services, or multiple instances of the same service mid-rollout — meaning some instances run newer code and some run older code, at the same moment. So a value might get written by new code and read shortly after by old code that's still running. That makes **forward compatibility** just as necessary here as backward compatibility — a requirement databases share with services, but for a different underlying reason (concurrent versions rather than a future read of your own past write).

**The subtle data-loss trap.** Say new code adds a field and writes a value into it. Old code — which has never heard of that field — reads the record, updates something else about it, and writes the record back. The desirable outcome is that the old code's write *preserves* the field it didn't understand, rather than silently dropping it. Most of the encoding formats from part 1 support this at the wire level (unknown fields just get carried through). But there's a real practical trap: if your application decodes a database record into an in-memory model object, and later re-encodes *that* object to write it back, the unknown field can vanish in that round trip — not because the encoding format failed, but because the in-memory model object never had a slot for a field it didn't know about in the first place. This isn't a hard problem to solve, but it's an easy one to overlook if you're not specifically watching for it.

**"Data outlives code."** A server-side deploy can fully replace an old code version within minutes. Database contents don't work that way — five-year-old data written under a five-year-old schema is often still sitting there, completely untouched, unless something explicitly rewrote it. Rewriting a large existing dataset into a new schema is possible but expensive, so most systems avoid it. Most relational databases sidestep the problem for simple changes (like adding a nullable column) — old rows just get treated as having `null` for a column that didn't exist when they were written, no rewrite needed. Some non-relational systems lean on their encoding format's own schema evolution rules directly for this (LinkedIn's Espresso, for instance, uses Avro for storage specifically to get this for free). The net effect: a database can *appear* to have one single schema in force, even though what's physically stored underneath is really a patchwork of records written under several historical schema versions.

**Archival storage — a case where you get to cheat.** A periodic snapshot or backup dump doesn't have this "many historical versions coexisting" problem, because you're actively rewriting the data during the dump anyway — so you might as well normalize everything to the *latest* schema on the way out, producing a dump that's internally consistent even if the live source database wasn't. Since a data dump is written once and never modified afterward, an immutable, self-describing format (like Avro's object container files) fits naturally — and since you're already touching every record, it's also a convenient moment to switch to an analytics-friendly column-oriented format (the same column storage covered earlier in this chapter's predecessor).

## Topic B: Dataflow through services — REST and RPC, and where SOAP fits

A **service** is just an API exposed over a network by a server, that clients connect to and call. The web itself is the most familiar example: browsers as clients, web servers as servers, HTTP/URLs/HTML as the shared, standardized API everyone agrees on. But "client" isn't limited to browsers — a native mobile app, a desktop app, or client-side JavaScript making Ajax calls are all just as much clients; the difference is usually that the response is a machine-readable format (JSON) meant for further processing, not HTML meant for a human to look at.

**A server can also be a client to another service** — this is the entire basis of decomposing one large application into many smaller ones by area of responsibility, historically called service-oriented architecture (SOA) and more recently rebranded as microservices. A key goal of that architecture is that each service can be independently deployed and evolved — which means old and new versions of any given service's clients and servers will routinely be running side by side, which is exactly the compatibility problem this whole chapter has been building toward.

**Services vs. databases — a useful contrast.** Both let clients submit and query data, but a database accepts arbitrary queries via a general-purpose query language, while a service only accepts the specific inputs and outputs its own business logic has predetermined — a real form of encapsulation, letting a service impose fine-grained control over what clients can and can't do that a raw database query interface can't offer.

**Where a "web service" actually shows up** — not just literal websites: a user-facing client hitting a public API over the internet; one internal service calling another inside the same organization's infrastructure (sometimes supported by "middleware"); and one organization's service calling a completely different organization's service (payment processors, OAuth, and similar cross-company integrations).

**REST vs. SOAP — two philosophies that barely agree on anything.** REST isn't a protocol at all — it's a design philosophy built directly on top of HTTP's existing features: URLs to identify resources, HTTP verbs and headers for caching, auth, and content negotiation, generally favoring simple, readable data formats. SOAP is the opposite instinct: an XML-based protocol that, despite usually running over HTTP, tries to be independent of HTTP and mostly avoids using its native features, instead layering on its own sprawling family of related standards (the "WS-*" ecosystem). SOAP APIs are described in a machine-oriented (not human-readable) language called WSDL, which enables code generation — genuinely useful for statically-typed languages, much less so for dynamic ones — but SOAP messages are typically too complex to write by hand, so real-world SOAP usage leans heavily on tooling and IDEs. Interoperability problems between different vendors' SOAP implementations are common enough, despite the standards being nominally shared, that SOAP has fallen out of favor outside large enterprises that already have deep investment in it. REST, by contrast, has been steadily gaining ground — especially for integration across organizations — and is closely associated with the microservices style; a REST API is typically documented with a format like OpenAPI (Swagger) rather than anything as heavyweight as WSDL.

## Topic C: The problems with RPC

**RPC (remote procedure call)** is an old idea (dating to the 1970s) built around one core promise: make calling a function on a remote machine *look and feel* exactly like calling a function in your own process — the "location transparency" abstraction. A long lineage of technologies chased this (Java RMI, Microsoft's DCOM, CORBA), and the book's assessment is blunt: the whole idea is fundamentally flawed, because a network call is a genuinely different kind of thing from a local function call, in ways that can't be papered over:

1. **Predictability.** A local call succeeds or fails based only on inputs you control. A network call can fail for reasons entirely outside your control — packet loss, a slow or unreachable remote machine — and these failures are common enough that you have to actively plan for them (e.g., retries), not just hope they're rare.
2. **The ambiguous timeout.** A local call returns a result, throws, or (rarely) never returns. A network call has a fourth outcome a local call simply cannot have: it can time out with *no way to know* whether the request was actually processed on the other end or not.
3. **Retries can duplicate real actions.** If you retry after a timeout, and it turns out the original request *did* go through and only the response got lost, a naive retry now performs the action twice — something a local function call structurally cannot do. Avoiding this requires deliberately building deduplication (idempotence) into the protocol; it isn't automatic.
4. **Latency is wildly less predictable.** A local call takes roughly the same time every time. A network call's latency swings enormously — sub-millisecond on a good day, many seconds when the network's congested or the remote service is overloaded, for functionally the same request.
5. **You can't just pass references.** A local call can cheaply hand over a pointer to an object already sitting in memory. A network call has to encode every parameter into bytes first — fine for small primitives, increasingly awkward as the objects being passed get larger or more complex.
6. **Cross-language type mismatches.** If the client and the service are written in different languages, the RPC framework has to translate types between them, and languages don't all agree on what types even exist (JavaScript's large-integer precision problem from part 1 of this chapter is a direct instance of this same issue) — a problem that simply doesn't exist inside a single process written in one language.

**The conclusion the book draws from all of this**: don't try to disguise a network call as a local one — REST's relative popularity partly reflects that it never pretends otherwise, even though people do still build RPC-flavored libraries on top of REST anyway.

## Topic D: Current directions for RPC

Despite the structural problems above, RPC hasn't disappeared — it's just gotten more honest about what it actually is. Modern RPC frameworks are built directly on the encodings from part 1 of this chapter: Thrift and Avro ship RPC support built in; **gRPC** is Protocol-Buffers-based RPC; Finagle is Thrift-based; Rest.li uses JSON over HTTP. The newer generation of these frameworks is explicit about network calls being fundamentally async and failure-prone, rather than hiding it: Finagle and Rest.li represent calls as **futures/promises** (which also make it easy to fire off several service calls in parallel and combine their results later); gRPC supports **streams** — a call that's a whole ongoing series of requests and responses over time, not a single request/response pair. Some of these frameworks also handle **service discovery**: letting a client figure out which IP address and port currently hosts a given service, since that can change dynamically in a large deployment.

**Custom binary RPC vs. REST — the actual tradeoff.** A purpose-built binary RPC protocol can genuinely outperform generic JSON-over-REST. But REST brings real, practical advantages that raw performance doesn't erase: you can poke at a REST API directly with a browser or `curl`, with zero code generation or special tooling; it's supported everywhere, by every mainstream language and platform; and there's a vast surrounding ecosystem (caches, load balancers, proxies, firewalls, monitoring and debugging tools) built to understand HTTP natively. This is why REST tends to dominate for *public*-facing APIs, while RPC frameworks concentrate on internal service-to-service calls within a single organization, often within one datacenter, where the performance edge matters more and the tooling ecosystem gap matters less.

## Topic E: Data encoding, evolution, and versioning for RPC

**A genuine simplification RPC gets that databases don't**: for dataflow through services, you can usually assume servers get upgraded *before* their clients do (not simultaneously, and not the other way around) — which means you really only need **backward compatibility on requests** (a server has to handle requests from older clients) and **forward compatibility on responses** (an older client has to handle responses from a newer server). That's a narrower requirement than the "both directions, all the time" situation databases face, precisely because of that assumed upgrade ordering.

Whatever compatibility guarantees an RPC framework actually gets, it inherits directly from whichever underlying encoding it's built on: Thrift, gRPC (protobuf), and Avro RPC all follow their respective encoding's own evolution rules (the field-tag rules from part 1, for the first two). SOAP requests/responses are defined via XML schemas, which can evolve, though with some known subtle pitfalls. RESTful APIs typically use JSON without any formally specified schema at all for responses, and JSON or URL/form-encoded parameters for requests — in practice, adding new optional request parameters and adding new fields to response objects are both generally treated as compatible changes.

**Why RPC versioning gets genuinely harder across organizational boundaries.** A service provider frequently has zero control over its clients — especially once a service is public — and can't force anyone to upgrade on any particular timeline. That means compatibility sometimes has to be maintained indefinitely, and if a truly breaking change becomes unavoidable, the provider often ends up running multiple API versions side by side rather than forcing a hard cutover. There's no single agreed-upon standard for *how* a client signals which version it wants — common REST approaches include a version number embedded directly in the URL, or specified via the HTTP `Accept` header; for API-key-based services, another option is to store each client's requested version server-side and let that be changed through a separate admin interface rather than in every request.

## Terms worth being able to define cold

- **"Data outlives code"** — a database's stored data can span many more schema versions than any single deployed version of the application ever will.
- **Location transparency** — RPC's core (and, per this chapter, fundamentally flawed) promise: make a remote call look identical to a local one.
- **Idempotence** — designing an operation so that performing it multiple times (e.g., due to a retried request) has the same effect as performing it once.
- **Service discovery** — letting a client dynamically find which network address currently hosts a given service.
- **RESTful** — an API designed according to REST's principles (resources identified by URLs, using native HTTP semantics).

## Questions I still don't have a crisp answer to

- In practice, how do teams decide when a breaking API change is unavoidable enough to justify maintaining multiple live versions, versus finding a compatible workaround?
- Given gRPC's streaming and typed-schema advantages over plain REST, why has REST remained so dominant even for internal service-to-service calls within a single organization, where gRPC's tradeoffs should arguably win more often?
