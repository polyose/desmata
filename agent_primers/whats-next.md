# What's next — the desmata ⇄ Semantic Paint thesis

**Status:** living plan, written 2026-07-13. This is the answer to
"what's next here." Its twin is SemanticPaint's `docs/ROADMAP.md`
(`~/src/SemanticPaint`), which carries the same plan from SP's vantage —
when priorities move, move them in both. Items are tagged **[desmata]**,
**[SP]**, or **[both]**.

**Background:** [semantic-paint-trust-layer.md](./semantic-paint-trust-layer.md)
(the record projection, and the verification loop closed 2026-07),
[desmata-as-semantic-paint-app.md](./desmata-as-semantic-paint-app.md)
(the process boundary), [lightweight-cells.md](./lightweight-cells.md)
(artifact-pinned wasm cells, WAVE determinism).

## The thesis

Crowd-sourced memoization over a web of trust: every verified-pin
`dsm call` witnesses `evaluates_to(C, F, X, Y)` (`paint.witnessed_call`),
`dsm paint` signs the ledger under the peer key and ships claim + component
bytes to an SP node, and any node can verify the claim mechanically — fetch
C by hash, re-execute F(X) in a zero-capability wasmtime, byte-compare
against Y. Confirmation outranks trust on the SP side; trust is the
fallback that lets a reader accept the memoized answer because peers they
trust already re-executed it.

**The method**, made explicit as two design laws (canonical in SP
`docs/design/`): new dynamics are palette colors/rules/facets, never host
policy (`interest_and_sync.md` §1); and a verifiable claim is a *projection* of
structure the artifact already commits to — the WIT in the component bytes, the
derivation graph in the flake, the engine's canonical rendering of a call —
never invented metadata an author asserts (`projection.md`). `evaluates_to` is
the seed; the interface witness (§3) and the deferred cell notes
([language-neutral-cells.md](./language-neutral-cells.md),
[derivation-manifest.md](./derivation-manifest.md),
[cross-arch-provisioning.md](./cross-arch-provisioning.md)) are the same move
repeated — the WIT half already landed, the flake half deferred.

**Where it stands:** proven whole, in a repeatable artifact — SP's
`scenarios/memoized_call.yaml` (landed 2026-07-17, §1), in SP's full
pytest tier and replayable in the viewer. Since then the whole planned
build arc closed on both sides: SP's §2 holes, the interface palette
(§3, both halves — witness here, `wit-parse` there, byte-for-byte
canonical WIT), demo v2 (a node wiring a stranger's two cells), and
stroke dependencies (SP §4: value-by-reference, blob co-shipping, FK
closures, the closure hash) all landed 2026-07-17→23. **Next is a
polish era, not a build rung** — testing, observability (`semp`),
sharp-edge shaving — before the demo era. SP's 2026-07-24 demos audit
(SP ROADMAP status paragraph + new §5 rows; decision records
`design/supersession.md`, `design/confidentiality_posture.md`) found
**no missing fundamentals** on either side of the seam. **The §5
keystone (palettes are cells) was ADOPTED 2026-07-24** — its wake-up
fired (SP `docs/design/palettes_are_cells.md` is the decision record;
build order in SP's ROADMAP status paragraph), and the keystone is
**COMPLETE 2026-07-25**: content-addressed palettes (desmata's palette
constants are hash pins now), the palette-cell layout + the
margin-palette pilot, `semp build`/`fmt` (SP palettes compile from `.dl`
sources — pins move when bytes move), and the egress gate + `semp node`
inspection. The §2 pubkey residue also closed (`1bfc3dc`): `dsm paint`
introduces its own key via `signer_pubkeys`, and SP's harness deleted
its pre-introduction crutch. **Now: the deliberate pause-and-review.** desmata's polish-era share stays small and already
filed: the two keystone door-openers in §5 below (reserve the `palette`
interface kind; `semp` on the one nushell convention), the deferred
`dsm publish` verb and the memoization-cache-as-usage-docs tooling
(both §3.2 residue), and keeping the pinned-`dsm` flake-bump ritual
green as SP's test tiers grow.

---

## 1. LANDED (2026-07-17): the whole-thesis demo scenario [both]

**`dsm paint` wired against real `spd` nodes** — SP's
`scenarios/memoized_call.yaml`. A `paint` scenario action drives the real
`dsm` CLI non-interactively (no desmata changes were needed — the
`--home <dir>` sandbox was the whole isolation story): fresh userspace,
`dsm call` on gnize-cell witnesses `evaluates_to`, `dsm paint` ships blob
+ signed stroke to a live node, which preserves the pre-signed signer.
Then, all asserted in one run: a wasmtime reader confirms over a
zero-weight edge (confirmation outranks trust), an engineless node
accepts on trust of a confirming-and-adopting relayer, a forged Y is
refuted wherever an engine runs — and believed where only trust decides —
and far readers hold the claim adopted under their friend's key,
never holding a reference to the desmata signer at all.

SP consumes desmata via a `git+file` flake input pinned to this repo's
`interface` branch — after committing here, bump SP with
`nix flake update desmata`.

## 2. Soon

- **LANDED (2026-07-18): Session lifecycle + hermetic home for cells
  [desmata]** — the non-deferred half of session cells
  ([session-cells.md](./session-cells.md) §3.1–3.2): a `Cell.session()`
  seam that generalizes `serve.py`'s `running()` (one bring-up per N
  operations, not per call), plus ephemeral-by-default homes with an
  opt-in overlay of declared inputs / snapshot so runtime state is
  *declared*, never ambient (a missing declared input fails loud —
  `CellUnavailable` — not a silent run off left-over state). Landed with
  it: `tally`, a serverful sample cell (a nix-built python kept alive as a
  counter server), and the ipfs builtin's daemon now runs through the same
  seam (`with builtins.session()` yields a live daemon; the `Inherit` home
  policy serves the peer's identity repo like `dsm serve`, `Ephemeral`
  gives an isolated throwaway node). Carries **no** SP dependency — it is
  what packaging SP itself as a (Category-2, distributable-artifact) cell
  needs. The gossip half (`cell-session` runner + predicate colors) stays
  deferred (§5). Next: SP-as-a-cell (its spd daemon reuses this seam).
- **LANDED (2026-07-25): Send our pubkey with the paint [desmata]** —
  `post_publish` now carries the peer's raw Ed25519 key as
  `signer_pubkeys` (self-certifying: the signer id is the key's SHA-256),
  so a first paint from a stranger verifies at SP's publish door (its
  §2.1 check LANDED 2026-07-17) with no out-of-band introduction; SP's
  harness deleted its pre-introduction crutch the same day. Our
  `PublishMismatch` round-trip still fails loudly if a node rejects the
  stroke.
- **LANDED (2026-07-17): Forward-compatibility rule [both]** — "ignore
  unknown fields" on the brushstroke wire record and palette JSON is now
  normative (SP `protocol_design.md` §6) and pinned by tests on all
  sides. Every consumer already behaved this way; the work was locking
  it in: SP's pylib codegen now emits an explicit `extra="ignore"`, SP
  tests pin all three targets, and our share landed as
  `test_brushstroke_from_dict_ignores_unknown_fields`
  (`from_dict` pulls named keys only; `canonical_bytes()` stays closed
  over the pinned field list, so extras never perturb content ids or
  signatures). Spec'd corollary: unknown fields are *unsigned* — never
  put anything load-bearing outside the schema. Unknown suite IDs stay
  rejected (crypto agility, not shape).
- **LANDED (2026-07-18): Deterministic fuel budgets for `cell-wasm`
  [both]** — adopted from the homestar review (§6). SP side: resource
  exhaustion (wall-clock or fuel) is now `unavailable`, never `refuted` —
  only a completed mismatch or a trap refutes (SP protocol_design.md
  §2.8, "giving up is not failing") — and the verification facet grew an
  optional `budget` the wasmtime engine renders as `-W fuel=N`. Our
  share: the reference `Invoker` protocol (`invoke.py`) now defines
  `budget: int | None` on `invoke`/`invoke_raw` — the contract's
  metering ceiling, engine-defined accounting, exhaustion is abstention
  — and the wasmtime CLI impl passes it as fuel. Budget is a generous
  ceiling, not part of the compared artifact; a witness minted under one
  engine's accounting stays valid under every other. Whether exhaustion
  should ever harden to `refuted` stays a contract-spec question,
  deferred.
- **LANDED (2026-07-18): Palette schema at the Haxe root [SP]** — the
  palette format's single source of truth is now `haxe/src/api/types/`
  (SP ROADMAP §2.4): the shipped-but-untyped `retention`/`requires`
  keys became Models, the arg-type vocabulary closed as an enumeration
  (`preimage`/`digest` — the sha256 pilot's types — included, so the
  out-of-tree palette kept validating untouched), and the drifted
  §6.1-vs-shipped-JSON docs were reconciled to the root. Notable
  doctrine now spec'd: SP's harness fails closed on unknown arg types
  at load; SP's node stays shape-permissive and abstains at use; and a
  rule carrying an unknown side-condition kind never fires (was
  fail-open). The palette format stays ready for the deferred
  generate-a-client workflow (§5): typed stroke-constructor stubs per
  color, of which a CLI is just one projection — cells already carry
  their half as the WIT world. desmata's share: none required —
  `paint.py`'s hand-built stroke shapes still match; adopting the
  generated schema stays a §5 wake-up.

## 3. The interface palette [both] — §3.1 + §3.2 LANDED 2026-07-20

**SP §3.1 LANDED 2026-07-20** (SP ROADMAP §3.1): the `interface/v1` palette
ships, `wit-parse` confirms `type_def` as a preimage-hash check and `exports`
by shelling to `wasm-tools component wit --json` and comparing canonical type
hashes, and `compatible` derives from `exports` strokes sharing a type hash.
It **pins the canonical WIT text projection** (SP
`docs/design/interface_palette.md` §4: F is the bare function name — as in
`evaluates_to`; params names-dropped; resolved-type text inlines
primitives/list/record and abstains on the rest; sha256 of that text is the
`type_def` hash).

**§3.2 the witness LANDED 2026-07-20** (desmata): `dsm call` mints
`type_def`/`exports` strokes beside `evaluates_to`. A `WitExtractor` seam
(`wit.py`, beside the `Invoker` seam) shells the cell's pinned `wasm-tools`
(a new `.#wasm-tools` flake output, sibling to `.#wasmtime`), and
`wit.canonical_signature` — a faithful port of SP's `wit.gleam` — renders the
called function's signature, which `paint.interface_strokes` hashes into
strokes and `witness_interface` writes to the ledger + outbox for the next
`dsm paint`. Cross-repo agreement is **proven, not asserted**: `test_wit.py`
runs the renderer over the *same* `wasm-tools --json` fixtures SP's runner
tests use (`test/fixtures/{gnize,sha256}_wit.json`) to the identical canonical
texts, and a live `dsm`-path extraction reproduces those fixture bytes exactly
— so the type hashes both sides mint are byte-equal, the discipline
`invoke.py`/`wave.py` keep for values kept here for types. Graceful-optional:
a cell flake without `wasm-tools`, or a non-projectable interface, mints
nothing and the evaluation witness stands alone (the *absent → trust fallback*
posture SP's node mirrors). Deferred within the row: a `dsm publish` verb
(minting interface facts for a never-called cell — `witness_interface` already
supports it), and surfacing confirmed `evaluates_to` as usage docs (primer
§3 item 5). §3.3 typed DataRefs LANDED 2026-07-20 — closing §3.

**§3.3 typed DataRefs LANDED 2026-07-20** (SP + desmata). SP grew `DataRef`
from `{hash, suite}` to also carry `type_ref` (a `type_def` hash), `mime_type`
(opaque data), and `size` — all optional, so a bare ref still decodes and
none of it enters any signed record's canonical bytes (the fields are
descriptive, and `type_ref` is a *self-checkable* hint: confirm it via the
`type_def` color, don't trust it). Our share is the consumer's:
`paint.post_put_data` now returns the whole DataRef the node minted, and
`ship_blobs` cross-checks the node-reported `size` against the bytes shipped —
the hash round-trip discipline extended to the new field, tolerant of an older
node that omits it. **Producer half LANDED 2026-07-21** (SP
`docs/design/stroke_dependencies.md` §8): `dsm call --result-by-ref` witnesses
the result Y **by content-address** — `paint.witnessed_call` decodes the result
to its canonical value bytes (`result_ref_value`: a `string` is its UTF-8, a
`list<u8>` its raw bytes — the inverse of SP's `render_wave`, restricted to that
renderable set, else inline), `stash_blob`s them into the outbox `ship_blobs`
already ships, and emits Y as a `DataRef {hash, suite, type_ref}` whose
`type_ref` is the same `result_t` the interface witness mints. An SP wasmtime
node then confirms by re-executing **and dereferencing Y** (SP's consumer half,
both `X` and `Y`). **Input half LANDED 2026-07-22** (same §8): `dsm call` takes
a `DataRef` *argument* — `--fetch-from <node>` (or the local outbox, for a value
this peer produced) supplies the referent bytes via the new `post_fetch` (the
read inverse of `post_put_data`), `deref_arg_value` renders them per a
self-checked `typeRef`, and the call witnesses `X` **by reference** while the
engine runs on the concrete value. So a composer feeds one cell's by-reference
output straight into the next; only automatic closure shipping (§4 proper, the
referent arriving without a fetch/preload) remains.

Design: [interface-palette.md](./interface-palette.md) (desmata's half);
canonical doc in SP `docs/design/interface_palette.md`. The problem:
cross-cell wiring leans on Python type hints — nothing language-agnostic
tells a consumer how to craft X or whether C₁'s output feeds C₂'s input,
so shapes are learned by runtime failure. The fix is projection, not
invention: every component already carries its WIT world; emit it as
verifiable `type_def`/`exports` brushstrokes (`interface/v1` palette,
`wit-parse` runner on the SP side), and wiring compatibility becomes a
derived Datalog fact over content-addressed type hashes. Typed DataRefs
(add type ref + size to `{hash, suite}`) ride along.

**Demo v2 LANDED 2026-07-21** (SP `scenarios/demo_v2.yaml`, SP ROADMAP §3.4):
a node discovering *how to call a cell it has never seen* from gossiped
interface facts, deriving `compatible(sha256,digest, caps,caps)`, wiring
digest→caps (feeding sha256's hex output into a new `caps` cell, uppercase),
witnessing the composition, and having it confirmed by a reader's own
re-execution (confirmation outranks trust) and held by an engineless reader on
trust. **desmata's share:** the arity-1-bare rule in `wit.py`'s
`canonical_signature` — a single-parameter function renders its ParamsT as the
bare inner type (no wrapping parens), still byte-for-byte with SP's `wit.gleam`
over the shared fixtures (`test/test_wit.py`, caps fixture added). WIT has no
1-tuples, so a unary function's input type *is* that type; without this the
`compatible` join fires for no real pair of cells (digest's `string` result
vs. a `(string)` param). The new `caps-cell` sibling mirrors sha256-cell; both
now expose `.#wasm-tools` so `dsm call` mints the interface strokes SP verifies.
Sequencing: after committing here, `nix flake update desmata` in SP so the
pinned `dsm` mints bare params (else the SP full-tier test skips). That demo's
composition dataflow should crib homestar/IPVM's `await/ok` promise shape (§6):
instructions referencing prior results by content address, scheduled as a DAG
that resumes from the first unmemoized step. Spec reference, not code. Still
ahead: the intermediate value travels inline as WAVE; a value moving by
*content-address* (a typed DataRef) is the richer dataflow, unbuilt.

## 4. Then: stroke dependencies — data moves the way software moves [both]

Design: SP `docs/design/stroke_dependencies.md` (canonical). The cell is
desmata's answer for software dependencies — they travel as one closure;
this extends the same discipline to the data layer. A color declares
which colors it depends on with explicit arg mappings, foreign-key style
("my arg 3 binds that color's arg 5"), so a synapse shipping a stroke
ships the strokes it presupposes; transmission-time rewrites must
commute with the FK maps; a Merkle closure hash over stroke content ids
lets a recipient verify the shipment in one comparison — the same
structural-commitment trick as the cell hash embedding the nucleus
manifest. Mostly [SP] work; desmata's share is the vantage: `dsm paint`'s
`put_data` blob preload is the hand-rolled special case (stroke → blob
edge) that the general closure eventually replaces, and the closure-hash
spec should be defined the way `invoke.py`/`wave.py` defined the
invocation contract. Standing note: SP keeps its store behind an
interface these closure/FK queries fit, in-memory now, database later.

## 5. Deferred, deliberately

**Keystone — palettes are cells [mostly SP] — ADOPTED 2026-07-24.** The
wake-up fired (`semp` + content-addressed palette-cells wanted together, ahead
of the planned pause-and-review); SP `docs/design/palettes_are_cells.md` is the
decision record and carries the build order. SP's
`docs/ROADMAP.md` §5 names the organizing decision this doc's rows had
been circling: *a palette is a cell whose interface kind is `palette`*, which
collapses five deferred rows into one — content-addressed palettes, the `semp`
CLI (palette-derived clients), the Scenario-playground row's palette cells
(already named below), language-neutral cells' `cell.toml`-as-`palette.toml`,
and palette-authored trust primitives. It is the nucleus-membrane discipline
([language-neutral-cells.md](./language-neutral-cells.md)) applied to palettes.
desmata's share is small but real, and both halves are door-opening, not build:
**(a)** when the `cell.toml` schema is written (Language-neutral cells row),
**reserve a `palette` interface kind** so a palette-cell is not a special case —
the extraction SP needs is "read the palette JSON + its verifier-cell closure
out of a cell through its declared interface," the same shape as any other kind
([interface-palette.md](./interface-palette.md) §4's open kind vocabulary);
**(b)** `semp` and `dsm` are two apps on one node
([desmata-as-semantic-paint-app.md](./desmata-as-semantic-paint-app.md)) and a
user in a palette-cell repo wants both, so `semp` must share the **one**
nushell-typed-output convention the [nushell-plugin.md](./nushell-plugin.md)
work just established (`--output json` + a generic converter), not fork a second
one. No new desmata mechanism — the session/hermetic-home seams the playground
rides already landed (§2).

| Item | Why deferred | Wake-up condition |
|---|---|---|
| Content-addressed palettes (reference by hash, not name+version) | name+version unambiguous at current scale | palettes evolve incompatibly / second palette author |
| Spec'd deterministic canonical encoding (DAG-CBOR/DRISL-style) replacing the hand-rolled JSON array | twin byte-pinned test vectors (`test_provenance.py` ↔ `canonical.gleam`) do the job; migration breaks every sig and content id | a second independent wire implementation |
| `nix` runner (rebuild-and-compare) — the *verifier* half of the derivation-manifest row below | no foundry-class node exists; `builds_to` staying trust-mediated is fine — we deliberately don't ship those artifacts (`paint.py`) | someone stands up a foundry node |
| `cell-session` runner + predicate colors — gossipable claims about *serverful* cells ([session-cells.md](./session-cells.md) §3.3, §6; SP ROADMAP §5) | `cell-session` is `nix`'s sibling: heavy, foundry-only, trust-mediated on pocket nodes. Wants SP §3's runner-name-in-gossip pattern first; the bug-repro travel story wants SP §4's blob co-shipping so an injected home overlay reaches peers by hash. **Distinct from** the session lifecycle + hermetic home ([session-cells.md](./session-cells.md) §3.1–3.2), which is desmata-side, carries no SP dependency, and LANDED 2026-07-18 (`Cell.session()` + `HomePolicy`, the `tally` sample, ipfs daemon over the seam) | SP §3 lands **and** a serverful cell wants a non-trivial claim gossiped (first crowd-verified bug report, or SP-as-a-cell reproducibility) |
| desmata server mode — a long-running `dsm serve` exposing the `invoke` seam over HTTP with a memoization cache, runner-plural (`cell-wasm`/`nix`/`cell-session`) ([server-mode.md](./server-mode.md), [server-interface.md](./server-interface.md)) | one-shot subprocess covers the PoC; the seams it rides all landed 2026-07-18 — `serve.py`'s daemon lifecycle, `session.py`'s `Cell.session()`/`HomePolicy`, and the `evaluates_to` provenance ledger that *is* the cache (content-addressed, deduped, monotonic — never read as a cache today) — so it's an HTTP surface + lookup-before-invoke + an invoker pool keyed by nucleus hash, not new mechanism. One tier below spd's per-palette claim store; SP's share is a third `SP_ENGINE=dsm-remote` registration against the runner seam it already has, and delegating *verification* re-execution to it is sound only within one operator's trust domain ([desmata-as-semantic-paint-app.md](./desmata-as-semantic-paint-app.md) §2a) | a node operator serves more than one tenant — a neighborhood/city cluster deduping duplicate pure-computation requests — or IPFS-by-hash fetch makes "have a server running" necessary anyway, or spd wants to delegate `cell-wasm` re-execution to a colocated cache; sharding (consistent-hash on `C`) rides on top, a mis-route being a cache miss, never a wrong answer |
| Scenario-playground cells (SP `docs/design/scenario_runner.md`) — SP-as-a-cell (Category-2 session cell, [session-cells.md](./session-cells.md) §4: `spd` in the tally/ipfs shape), palette cells (palette JSON + its verifier-cell closure, by CID — the vehicle; the palette id stays the wire identity), behavior cells (scenario+trace+paths bundle); the runner cell's declared interface kind is `browser` ([interface-palette.md](./interface-palette.md) §4) | the SP-side simulation layer already exists (mobility harness, client-side viewer); desmata's share is packaging, which rides the landed session/hermetic-home seams | SP-as-a-cell begins, or a first outside collaborator wants the playground's fork-and-retry loop |
| Blob co-shipping along dependency closures (replaces `put_data` preload) | `put_data` is the declared MVP stand-in, fine at demo scale | SP interest-driven sync matures |
| iroh content backend (`content.py`) | IPFS covers the thesis path | phase-2 transport work resumes |
| Key rotation (`keys.py`) | single peer key per userspace suffices pre-demo | multi-device / revocation needs |
| Palette-derived clients (typed stroke-constructors per color; CLI/client-lib/OpenAPI-style projections of the SP §2.4 schema) | PoC phase: apps embed stroke construction in author-written functions; the schema work keeps the format generation-ready | an app author outside these repos, or observed palette-authoring friction |
| Version lenses — palette *and cell* compatibility declarations (SP `docs/design/version_lenses.md`) | nothing has two versions yet; palettes/cells are immutable by hash, so evolution means publishing "v2 relates to v1 modulo Δ" as hash-pinned data — the cell half ("this cell is like that one, but different in this way") is desmata's vantage | a palette or cell evolves and both populations must interoperate |
| Agent bench — scored cold-start episodes (SP `docs/design/agent_bench.md`) | usability measurement is post-PoC by decision (2026-07-15) | demo v2 lands, or a first outside user (human or agent) onboards cold |
| Language-neutral cells — demote Python from the nucleus to just-another-language ([language-neutral-cells.md](./language-neutral-cells.md)): a `cell.toml` manifest (interface kinds + closure declaration) replaces `cell.py` in the nucleus, and bindings move to `languages/{python,haskell,…}/` in the membrane | `cell.py` fuses three roles — nucleus trust-anchor, Python driver, *and* closure declaration (build metadata, so hashing a cell means executing Python, which the hash path refuses) — making Python first-class *by structure*. The fix wants the interface-palette manifest (§4, the at-rest twin of §3's gossip projection) and the closure metadata lifted out of Python into inert TOML. Bindings-in-membrane is the payoff: "same nucleus, +Haskell" leaves `nucleus_hash` unchanged, so trust stacks across it (idea 5) — a free membrane op, **not** a version lens (overlaps the row above: binding additions don't touch the nucleus; contract changes do) | a second language wants first-class cell access, or an author/forker publishes a cross-language enrichment |
| Derivation manifest — a cell advertises "these parts are pure functions of those parts" ([derivation-manifest.md](./derivation-manifest.md)): the intra-cell build/codegen DAG (Rust→wasm, `haxe/src/api/`→generated, …) as verifiable `builds_to`/`generates_to` edges in `cell.toml`, so a reviewer audits only sources + pinned tools and treats every derived blob as verifiable-by-re-derivation | the primitive exists coarsely — `builds_to(N,A)` + the `nix` runner (deferred) — and desmata already captures Trustix-shaped provenance ([trustix-interop.md](./trustix-interop.md)); what's new is the fine-grained *advertised* DAG generalized past wasm to all generated code (SP's `_GeneratedFiles.json` is a proto-manifest missing the input edge + tool pin). Same projection move as §3: the flake's derivation graph → gossip, as the WIT world → gossip. Expensive-to-verify tier (full rebuild) ⇒ trust-leaning by design — one honest foundry rebuild, gossiped + confirmed, protects everyone; only *reproducible* builds refute, non-reproducible **abstain** (§2.3). Shares the `nix` runner's verifier and §4's closure-hash discipline | a foundry-class node exists to confirm builds, or a cell ships generated code a reviewer wants to skip auditing (SP-as-a-cell + its Haxe codegen is the first in-house case), or a supply-chain review wants the reduced trusted surface |
| Cross-architecture provisioning — a cell that survives the partition on any machine ([cross-arch-provisioning.md](./cross-arch-provisioning.md)): walk the derivation DAG's `system` coordinate to ship arch-neutral outputs as-is (wasm + the FOD fetch layer) and handle the arch-specific frontier by a per-deployment policy — pre-build for named systems (fat) or ship the build closure for offline rebuild | wasm cells already cross architectures for free (arch-neutral bytes + the cross-arch bit-determinism `evaluates_to` requires); the residue is the engine, Category-2 nix-closure cells (nushell-cell), and rebuild-to-verify. The nix floor makes offline bootstrap principled ("bootstrap to wasm-freedom" from a standard nix env, which desmata depends on for exactly this). Cross-arch reproducibility being hard is dodged by splitting `builds_to` per `system` — same-`(recipe,system)` divergence = the existing conflicting-attestation case (refutable); cross-system difference = benign, so `system` becomes a key arg and is the metadata distinguishing a malicious variant from atypical hardware. Provisioning is a user dial: game-night (wasm, light) ↔ end-of-world (full multi-arch closure), user supplies the resources | a cross-arch offline deployment is attempted, or disaster-prep (end-of-world) packaging is requested, or SP-as-a-cell runs on a mixed-arch foundry |
| Shared-dependency trust units ([shared-nuclei.md](./shared-nuclei.md)) — factor a dependency shared across unrelated cells into its own content-addressed, independently-attested unit (nucleus idea 5 pushed below whole-nucleus granularity); multi-nucleus manifest + dep-closure-as-referenceable-units, plus SP's `has_dependency` color + audit/vuln palette | trust already stacks on shared *nuclei*, deps are already content-addressed (`deps_by_hash`, provenance `references`), SP attestation is already hash-agnostic — so this is a generalization, not new mechanism; audit dedups and communities normalize trusted versions (the anti-"update-ASAP" argument). Door open: spd FODs are a lockfile projection | a second cell shares a substantial dependency, or a community wants to normalize a version |
| Palette-authored trust primitives (**[SP]**, SP `docs/design/trust_primitives.md`) — make the trust model palette data, not host policy: a fail-closed strategy seam for signer transport + entity-arg *visibility*, so authors can experiment (e.g. leader-visible identity) without editing SP | **no desmata stake** beyond authoring palettes that select strategies — the identity model lives in SP's node. Recorded here only to keep the twins in step; design law #1 applied to the trust layer | mirrors the SP row: a palette author wants a second trust model |

## 6. Considered and not adopted

**AT Protocol (data model, 2026-07).** Reviewed atproto's data model for
the wire layer. Adopted: typed blob refs, forward-compat rule, and two
deferred rows above. Rejected: the **no-floats rule** (their fix for
float-hash nondeterminism; ours is the engine's canonical WAVE rendering
captured verbatim — already closed) and **multiformat CIDs**
(`dsm:<backend>:<digest>` and `DataRef.suite` are already the
self-describing-hash idea; the cells-as-CIDs vs
components-as-bare-sha256 spelling split can be absorbed by `suite` if
it ever bites).

**homestar / IPVM (2026-07).** Fission's IPVM runtime is the closest
prior art to the whole thesis — content-addressed wasm, receipts keyed
by instruction CID, gossiped over libp2p — and it is the thesis minus
the load-bearing property: receipts are unsigned in practice and stored
on the transport signature alone, never verified by re-execution. Its
executor also breaks the `cell-wasm` contract (WASI linked, so guests
reach clock/entropy and purity stops being statically checkable; silent
int→float coercion; IPLD/DAG-CBOR values instead of canonical WAVE — its
outputs can never byte-compare against a desmata witness), and it is
unmaintained (last real commit 2024-05, wasmtime 18, Fission wound
down). Disposition: conceptual alternative; adopted fuel budgets (§2)
and the `await/ok` dataflow reference (§3); no code. Their
memoization key `{resource, op, input, nonce}` is independently the
`evaluates_to(C, F, X)` shape — convergent evolution in our favor.

Full rationale for both: SP `docs/ROADMAP.md` §6.
