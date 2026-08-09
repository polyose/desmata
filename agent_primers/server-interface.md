# Primer: `dsm serve` — the HTTP compute/verify interface (spec draft)

**Status:** spec draft, 2026-08-09. **Not scheduled.** Defines the wire
contract `dsm serve` exposes so a colocated tenant (an `spd` process, another
`dsm`, a script) can delegate computation and get memoized, content-addressed
results. Implementation deferred; this specs the contract only. The *why*
(process boundary, memoization, sharding, gotchas) is
[server-mode.md](./server-mode.md).

**Audience:** anyone implementing the server, writing a client, or wiring an
`spd` runner (`SP_ENGINE=dsm-remote`) against it.

**Source:** design conversation 2026-08-09; grounded in `invoke.py`,
`paint.py` (`DataRef`, the outbox/ledger), `session.py` (`HomePolicy`),
`content.py` (`Hash`), and SP's `verify.gleam` runner dispatch +
`protocol_design.md` forward-compat doctrine.

---

## 1. Scope & non-goals

**In scope:** a request surface for *running a content-addressed computation
and observing a verified result*, across the three runner weight classes
(`cell-wasm`, `nix`, `cell-session`), with a shared memoization cache.

**Out of scope (stays where it is):** signing/painting under a peer identity
(`dsm paint`, per-userspace), SP gossip / trust / inference, and the
palette/color definitions themselves. This server computes and witnesses
*facts*; it never signs claims on a tenant's behalf.

## 2. Design invariants

Load-bearing; every schema below honors them, and no extension may violate
them.

1. **Input identity is content-addressed.** A computation's input `X` is the
   content-id of a canonical structure, never ambient state. Same `X` ⇒ same
   cache key ⇒ same answer, forever.
2. **Control plane / data plane split.** HTTP/JSON carries the *plan and
   hashes* (small). Bytes — home images, diffs, reference data, components —
   move by CID over the content layer (IPFS), out of band. A request body
   never carries a payload blob inline.
3. **Runners are a closed, named namespace.** `runner` selects the weight
   class. Unknown runner ⇒ fail closed (`400`), never a silent default.
4. **Weaker verification carries its own runner name.** Only `cell-wasm` may
   back an `exact-hash` claim; `nix` and `cell-session` carry honest weaker
   policies and can never masquerade as exact-hash.
5. **Abstain is not refute.** Exhaustion, a missing engine, a non-reproducible
   step, or an unmet precondition ⇒ `unavailable`/`abstained`. Only a
   *completed* run whose result violates the asserted policy ⇒ `refuted`.
6. **Closed vocabularies fail closed; unknown descriptive fields are
   ignored.** Enums (runner, step kind, policy kind, verdict) reject unknowns.
   Other fields follow the forward-compat rule (§12).
7. **No shared-identity signing.** No endpoint signs under a tenant's key.
   Witnessed facts are returned unsigned for the tenant to paint later under
   its own identity.

## 3. Transport

- HTTP/1.1, JSON bodies (`application/json`), UTF-8.
- Version negotiated by path prefix: **`/v1/…`**.
- All hashes are the self-describing `Hash` form `dsm:<backend>:<digest>`
  (`content.py`). Value refs reuse the existing `DataRef` shape
  `{hash, suite, type_ref?, mime_type?, size?}` (`paint.py`).
- Referenced bytes are resolved by the server over its own content backend
  (its `dsm serve` ipfs daemon). A referent the server can't resolve ⇒
  `503`, naming the missing hash — never a guess.

## 4. `POST /v1/run` — the one computation verb

Runs a computation and returns a verified observation. Runner-generic; the
runner-specific bindings are §9.

```jsonc
// request
{
  "runner":  "cell-wasm" | "nix" | "cell-session",   // §2.3 closed
  "target":  "dsm:ipfs:<cell>" | "<local-dir>",      // what holds the computation
  "artifact": "wasm",                    // which pinned artifact/output (optional if unambiguous)

  "entrypoint": "gnize",                 // the measured step: a WIT fn / build output / session op
  "args":     [ <json value>, ... ],     // inline values, or DataRefs
  "messages": [ ... ],                    // cell-session only: the drive sequence

  "home":     <ProvisioningPlan>,        // §5 — how the home is constituted (cell-session/nix)
  "assert":   <VerificationFacet>,       // §6 — the policy the result is judged under
  "budget":   <int>,                     // optional metering ceiling; exhaustion ⇒ abstain
  "witness":  false                      // §7 — persist an unsigned fact into the shared ledger/cache
}
```

```jsonc
// response
{
  "verdict":  "confirmed" | "refuted" | "abstained" | "unavailable",
  "policy":   "exact-hash" | "predicate" | "tolerance" | "attest-only",
  "observation": <json>,                 // the decoded result / observed feature
  "witness": {                           // the content-addressed fact, UNSIGNED
    "color": "evaluates_to" | "builds_to" | "<session-color>",
    "c": "<component-or-cell hash>",
    "f": "<entrypoint>",
    "x": "<plan/args content-id>",       // §2.1 — the canonical input identity
    "y": <inline WAVE | DataRef>         // exact result, or by-reference
  },
  "cached":   true | false,
  "detail":   { ... }                    // runner-specific: fuel used, narHash, engine id, abstain reason, sealed steps
}
```

**`verdict` vs HTTP status.** A `200` means *the request was serviced*; the
*verdict* is in the body. Transport/authz/shape failures use HTTP status
(§11). A `refuted` computation is a successful `200` with
`verdict: "refuted"`.

## 5. The provisioning plan (`home`)

The enrichment that carries the interface past wasm calls. A plan is a
**content-addressed data structure over a closed step vocabulary**; its
content-id is the home's contribution to `X` (§2.1). Maps 1:1 onto desmata's
in-process `HomePolicy` (`session.py`).

```jsonc
{
  "base": "blank" | "snapshot:dsm:ipfs:<CID>",   // Ephemeral | FromSnapshot
  "steps": [                                     // applied in order, before the measured step
    { "overlay": "dsm:ipfs:<file-CID>", "at": "config.toml" },     // place a file
    { "patch":   "dsm:ipfs:<diff-CID>", "at": "config.toml" },     // apply a diff
    { "exec":    <RunRequest> }                                    // §5.1 — recursively a /run
  ]
}
```

**Step kinds are closed** (`overlay` | `patch` | `exec` | reserved). Unknown
kind ⇒ fail closed. No step is an opaque shell string — that is the line
between "rich" and "arbitrary RPC," and crossing it forfeits reproducibility,
cacheability, and authz.

### 5.1 `exec` steps are recursive `/run` calls

An `exec` step's value is a `/v1/run` request whose output *is* a home state
("run the tool once"). Plans are therefore compositional (a small DAG), and
sub-steps cache independently. An `exec` step MAY reference a prior step's
result by content-address rather than round-tripping it (the `await/ok`
promise shape; the scheduling beyond by-CID reference is reserved, §14).

### 5.2 Seal vs replay, per step (normative)

Each step is either **replayed** (shipped as recipe; every verifier
reconstructs) or **sealed** (its `exec`/`patch` result substituted by
`base: "snapshot:<CID>"`, pinned to exact bytes). A publisher MAY seal any
subset — sealing the one non-deterministic step and replaying the
deterministic rest is the intended use. Sealed bytes are *asserted* input
(the publisher vouches for them); replayed steps are *reconstructed* input.
The response `detail` MUST report which steps were sealed, so no reader
mistakes a sealed run for a fully-reconstructed one.

**Caveat (from [session-cells.md](./session-cells.md) §3.2):** a verbatim
whole-home snapshot over-specifies — it bakes in absolute paths, hostnames,
and caches, so it may reproduce nowhere else, and its cache can *contain* the
answer, making the re-run vacuous. Prefer surgical `overlay`/`patch` steps;
seal only the minimum. A capture verb should show the diff-from-blank so the
author sees what they are baking in.

## 6. The verification facet (`assert`)

The policy the result is judged under. Closed vocabulary; adding a kind is a
deliberate act (SP §2.4 fail-closed doctrine).

| kind | meaning | may back | mismatch ⇒ |
|---|---|---|---|
| `exact-hash` | `Y` byte-equals the claim | `cell-wasm` only | `refuted` |
| `tolerance` | numeric result within ε | `nix`, `cell-session` | `refuted` if outside; `abstained` if unrenderable |
| `predicate` | `contains`/regex/structured match | `nix`, `cell-session` | `refuted` if false on a *completed* run |
| `attest-only` | no mechanical check; M-of-N ran it | any non-exact | never refutes; attested→`confirmed`, else `abstained` |

Example: `{ "kind": "predicate", "expr": "contains(stdout,'Foo')" }`.
**Reserved:** the predicate expression grammar (§14). Unknown `kind` ⇒ the
facet fails closed and the run `abstains`.

## 7. Witnessing (unsigned facts)

`witness: true` persists the returned `witness` object into the server's
shared provenance ledger (the content-addressed, deduped store
`evaluates_to` already uses, `files.data/provenance/brushstrokes`), so it
(a) seeds the cache for other tenants and (b) is available for a later
`dsm paint` to sign **under the caller's own key**. The server never signs.
The persisted fact is exactly the `witness` block: content-addressed,
unsigned, monotonic.

## 8. Cache endpoints (pure, side-effect-free)

```
GET /v1/cache/<color>/<C>/<F>?x=<input-content-id>
  -> 200 { "y": <inline|DataRef>, "policy": ..., "verdict": ... }
  -> 404   (not computed here)
```

The cache is **content-addressed and monotonic** — an entry is never
invalidated (pure + content-addressed input ⇒ the answer is stable). A hit
under a weaker policy is a *relay* of a prior run, tagged with its
`policy`/`verdict` so the reader knows whether it is a confirmation or a
trust-mediated echo. `/v1/run` consults this before executing; `cached` in
the response reflects the hit.

## 9. Runner bindings

Each runner fills the §4 shape; the differences are which fields apply and
the policy ceiling.

- **`cell-wasm`** — `entrypoint`+`args` (WAVE), no `home`, `assert` defaults
  to `exact-hash`, `budget` = fuel. `Y` is the engine's canonical WAVE
  (inline, or a `DataRef` when witnessing by reference). The pure lane; the
  only lane a pocket node re-runs for free.
- **`nix`** — `target` = a cell/flake, `artifact` = the output to realize,
  `color` = `builds_to`. `Y` = output narHash/sha256. Reproducible ⇒ a
  differing rebuild refutes; otherwise `abstained` (§2.5). `home` usually
  absent.
- **`cell-session`** — `home` (plan §5) + `messages` + `assert`
  (`predicate`/`attest-only`). `X` = plan content-id + message-seq
  content-id. Highest capability; own runner name so pocket nodes fall back
  to trust. Never backs `exact-hash`.

## 10. Identity & capability boundary

- `runner: cell-wasm` on an already-resolved artifact is **low-capability**
  (zero-cap wasm sandbox) — the open, neighborhood-serveable surface.
- `runner: nix` and any `exec` step are **build/execute capability**
  (arbitrary derivation realization or binary execution). These MUST sit
  behind operator authz distinct from the wasm surface (fetch-and-build ⇒
  arbitrary nix evaluation, server-mode.md §6.7). The server MAY restrict
  which cells/plans it will build.
- **No `/paint`.** Painting stays a per-userspace, identity-bearing act off
  this server (§2.7).
- **Reserved:** the auth scheme (bearer token / peer-key challenge, §14). The
  split above must be expressible when it lands.

## 11. Error model (transport, distinct from verdicts)

| status | meaning |
|---|---|
| `400` | malformed body / unknown closed-enum value (runner, step kind, policy kind) |
| `403` | capability not granted for this runner/step |
| `404` | cache miss (§8 only) |
| `422` | well-formed but unrunnable (e.g. `entrypoint` not exported) |
| `503` | referent unresolvable (content backend down / hash not found) — names the missing hash |

Anything the computation *itself* produces (mismatch, exhaustion,
non-determinism) is a `200` with the appropriate `verdict`, never an HTTP
error.

## 12. Versioning & forward-compat

- Path-versioned (`/v1`). Breaking shape changes bump the prefix.
- **Descriptive fields:** consumers ignore unknown keys; unknown keys are
  never load-bearing (SP `protocol_design.md` §6, applied to this wire).
- **Closed enums** (runner, step kind, policy kind, verdict, suite id):
  unknown values fail closed (SP §2.4 doctrine).
- Plan and witness content-ids MUST be computed over a **canonical
  serialization** so `X` agrees cross-implementation. **Reserved:** the exact
  canonical encoding — it rides the existing canonical-bytes machinery (the
  twin byte-pinned vectors), not a hand-roll.

## 13. CLI surface (the three modes)

```
dsm serve --port N                                    # ipfs daemon + this HTTP surface + shared cache
dsm --server http://host:N run <target> <fn> <args>   # thin client → /v1/run
dsm run <target> <fn> <args>                          # in-process, no cache, terminates
```

`run` is the runner-generic verb; `call` remains sugar for
`runner: cell-wasm`. CLI and HTTP route share one
`perform_run(request) -> response` core (server-mode.md §9 step 1).

## 14. Reserved / deferred (door, not room)

- Predicate expression grammar (§6).
- Auth scheme and the build/exec capability gate mechanics (§10).
- Canonical plan/witness encoding (§12) — reserved to the shared
  canonical-bytes vectors.
- `exec`-step DAG scheduling / cross-step promise references beyond by-CID
  (§5.1) — the `await/ok` shape is referenced, not specified.
- Sharding/routing (consistent-hash on `C`): a client/gateway concern layered
  above this surface; a mis-route is a cache miss, never a wrong answer
  (server-mode.md §7), so it needs nothing from the wire.
