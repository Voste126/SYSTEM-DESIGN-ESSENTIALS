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
