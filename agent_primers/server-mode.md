# Primer: desmata server mode — memoized, sharded computation over one node

**Status:** design note, 2026-08-09. **Not scheduled.** Records the
direction and reserves the seams, so later work doesn't re-confuse the
*process boundary* (this note) with the *wire contract* (specced separately
in [server-interface.md](./server-interface.md)). No code yet. Pairs with
[session-cells.md](./session-cells.md) (the runtime lifecycle this leans
on) and [desmata-as-semantic-paint-app.md](./desmata-as-semantic-paint-app.md)
(where dsm ends and spd begins).

**Audience:** anyone reasoning about running `dsm` as a long-lived service
rather than a one-shot subprocess — a node operator serving many tenants, or
an `spd` that wants to delegate computation.

**Source:** design conversation 2026-08-09, grounded in `serve.py`,
`session.py`, `invoke.py`, `paint.py`, `cli/dsm.py`, and SP's
`daemon/src/spd/verify/verify.gleam`.

---

## 1. The idea

`spd` runs on the BEAM, which tolerates many lightweight processes, so one
small cluster can serve a whole neighborhood's worth of tenants. Colocated
tenants touch the same data, so their palettes issue **duplicate
computation requests**. Palette *inference* stays confined per tenant. But
when a palette reaches out for **arbitrary computation** — especially a
function known pure — the node shouldn't recompute per tenant. It can
**memoize** the result and, by sharding on a property of the cell hash (even
/ odd, consistent-hash), route a request to the node likeliest to hold it
cached.

Desmata today is a one-shot subprocess (`dsm <target> <fn> <args>`,
terminates, remembers nothing). This note is the case for a **server mode**:
a long-running `dsm serve` that accepts requests, holds an in-memory + on-disk
cache, and may itself spawn work. Building to the server interface makes the
CLI a thin client of it; building to the CLI first would make the server
hard. And — a point that turned out to matter more than it first seemed —
fetching cells by hash needs a running ipfs daemon, so "have a server
running" is closer to *necessary* than *premature*.

## 2. Why it fits: the invoke seam is already the interface

The tempting picture — "bolt a server onto a CLI" — is wrong, and the truth
is better. **`spd` does not call `dsm` today.** In production `spd`'s
verification runner shells out *directly to `wasmtime`* via an Erlang FFI
port (`spd_wasm_ffi.erl`). Desmata's `invoke.py` is the *reference
implementation of the same runner contract*, not something `spd` drives. The
only place anything shells out to the `dsm` binary is SP's test harness
(`sp_harness/driver.py`), for authoring (`dsm call` / `dsm paint`).

Both sides already share one seam:

```
invoke(component, function, args_wave, budget) -> result_wave
```

— desmata's `Invoker` protocol (`invoke.py`), and SP's `verify.Invoker`
(`verify.gleam`), the latter selected by `SP_ENGINE` (`wasmtime` / `none`).
So server mode is not a bolt-on: it is **making desmata expose, over HTTP,
the invoke contract both sides already treat as pluggable** — plus
memoization behind it. On the SP side, pointing a tenant at it is a *third
`SP_ENGINE` registration* (`dsm-remote` + a host), a drop-in for the local
wasmtime FFI. Zero new concepts on either end.

## 3. Easy or hard — what's already scaffolded

Moderate, and mostly there:

| Need | Already present |
|---|---|
| Long-running process lifecycle | `serve.py`: `spawn_daemon`/`wait_ready`/`shutdown`/`running()`/`serve_forever` |
| "One bring-up, N ops" | `session.py`: `Cell.session()` + `HomePolicy` |
| The invoke seam | `Invoker` protocol, cleanly isolated |
| **The result cache** | the `evaluates_to(C,F,X,Y)` ledger (§4) — content-addressed, deduped |
| HTTP transport | `dsm paint` already POSTs to spd over stdlib `urllib.request` |
| Purity classification | `cell-wasm` (memoizable) vs `cell-session` (not) already first-class |

Genuinely new: an HTTP *server* (none today — `urllib` is client-only; stdlib
`http.server` keeps the nix closure lean; do **not** reach for FastAPI), a
cache-lookup-before-invoke step, an invoker pool (§6.2), and a refactor of
`call`'s body into a `perform_run(request) -> response` core the CLI and the
HTTP route both call.

## 4. The memoization cache is the `evaluates_to` ledger, served

The cache is not new storage. Every witnessed call already writes an
`evaluates_to(C,F,X,Y)` brushstroke into the provenance ledger at
`files.data/provenance/brushstrokes` — content-addressed and deduped. That
*is* a persistent memoization store; it is simply never **read as a cache**
today (`dsm call` always executes). Server mode adds one step:
**lookup-before-invoke** keyed on `(C, F, X)`.

Its defining property: **content-addressed + pure ⇒ the cache is monotonic
and never invalidated.** `(C,F,X)` determines `Y` forever. This is the same
object the SP thesis gossips — the compute cache and the crowd-sourced
memoization layer are one idea at two scopes:

- **Claim tier** (spd's store): per tenant, per palette, trust-scoped.
- **Compute tier** (this cache): shared across every tenant on the box.

The compute tier sits *below* the claim tier and is the new value: it dedups
work across colocated tenants that the per-tenant claim store cannot.

## 5. Three runner weight classes, one dispatch

The server is **runner-plural**, mirroring SP's `verify.gleam` dispatch on
`facet.runner`. The unifying axis is *how fully the input is content-addressed*
× *how strong the output verification policy is*:

| Runner | Input identity | Output policy | Cost / trust |
|---|---|---|---|
| `cell-wasm` | `C` + WAVE args | `exact-hash` (refutable) | cheap; any pocket node re-runs |
| `nix` | source closure | reproducible ⇒ refute, else **abstain** | foundry-only; trust-leaning |
| `cell-session` | `C` + home plan + msg-seq | `predicate` / `attest-only` | highest capability; trust-mediated |

Two laws hold across all three (canonical in
[verifiable-computation.md](./verifiable-computation.md) and
[session-cells.md](./session-cells.md)):

- **Only `cell-wasm` may back an `exact-hash` claim.** Weaker runners carry
  their own name so a pocket node knows to fall back to trust.
- **Abstain is not refute.** Exhaustion, a missing engine, a non-reproducible
  build, an unmet precondition ⇒ `unavailable`/`abstained`. Only a
  *completed* run whose result violates the policy ⇒ `refuted`.

`nix` is the deferred rebuild-and-compare runner from
[whats-next.md](./whats-next.md) §5 (the derivation-manifest row; wake-up:
"someone stands up a foundry node" — a serving node *is* that). `cell-session`
is [session-cells.md](./session-cells.md) §3.3. Server mode is where these
stop being one-offs and become registered engines. Reproducible-build
machinery need not be designed now: it collapses into "a `nix`/`cell-session`
step whose input closure happens to be source and whose output happens to be
an artifact."

## 6. Gotchas

**6.1 A subprocess is not a BEAM lightweight process.** This is where the
"the BEAM tolerates many processes" intuition does *not* transfer. Each cache
*miss* is heavyweight: a `wasmtime` subprocess (fine, sandboxed, parallel) —
and possibly a `nix build` and an ipfs unpack before it. Under load you need
a worker pool / semaphore over misses and **single-flight** (dedup concurrent
identical `(C,F,X)` into one execution). Memoization is what makes the model
viable, so the shared cache is load-bearing, not a nicety.

**6.2 Hoist per-cell setup out of the hot path.** `dsm call` rebuilds the
wasmtime invoker (`build_invoker` → `nix build`) and re-unpacks hash targets
*every call*. A server must cache invokers keyed by `(nucleus_hash,
artifact)` — each cell pins its *own* wasmtime via its flake, so it's a pool
of runners, not one. This is exactly what `Cell.session()` generalizes ("one
bring-up per N ops"); lightweight wasm cells just don't use sessions yet.
This is the main structural addition.

**6.3 Separate pure compute from identity.** Every `dsm` command threads
`--home` to sandbox a userspace (ledger, outbox, **peer key**, ipfs repo). A
server serves many tenants. Keep two things apart: the pure-compute surface
(shared cache, **no signing**) and `paint` (identity-bearing, per-userspace).
A shared server must never sign under one identity on behalf of many tenants
— that collapses SP's `signer = sha256(pubkey)` model. Witnessed facts come
back **unsigned** for the tenant to paint later under its own key.

**6.4 IPFS must be co-resident.** Fetching a cell by hash needs a running
ipfs daemon — which is what `dsm serve` runs *today*. So the compute server
wants the daemon inside it; `serve.py`'s `running()` and the `Inherit` home
policy already serve the identity repo. **Naming to resolve:** `dsm serve`
currently means "serve cells over IPFS." Unify — one `dsm serve` runs both
the ipfs daemon (fetch/announce) and the HTTP API (compute), two halves of
"this box is online."

**6.5 Cache-key correctness.** Key on `(C, F, canonical-input-id)` → `Y`,
`Y` being the engine's own WAVE bytes (never a re-encoding — `invoke_raw`
enforces this). Only memoize `cell-wasm` for `exact-hash`. **Exclude
`budget`/fuel from the key** (a result under one budget is valid under any),
but **never cache an exhausted/abstained run** — completed results only.

**6.6 Outsourcing *verification* re-introduces trust.** SP has two reasons to
invoke: fresh witnessing (low trust sensitivity — the claim is verified
downstream anyway) and verification re-execution (the thing that gives SP
independence from trust, "confirmation outranks trust"). Delegating the
*latter* to a memoizing dsm server means SP's confirmations are only as
honest as that server. **Within one operator's basement (one trust domain),
fine.** Across trust domains it silently re-introduces trust in the executor.
Deployment constraint: delegate verification only to a colocated,
operator-trusted server.

**6.7 Fetch-and-build is arbitrary evaluation.** Accepting a *hash* to
fetch-build-and-run is arbitrary `nix` evaluation + build, even though
`wasmtime` execution is sandboxed. The open, neighborhood-serveable surface
is `cell-wasm` invoking an already-resolved artifact (zero-cap). `nix` and
any `exec` step are build/execute capability and need distinct operator
authz. A server may restrict which cells/plans it will build.

**6.8 Concurrency-safe ledger writes.** The dedup-by-content-id ledger write
is fine single-threaded; under a concurrent server, appends need a lock or
per-file atomicity.

## 7. Sharding is a pure optimization

Even/odd (consistent-hash on `C`) routing is safe *by construction*: a
mis-routed request just makes the target node fetch the cell by CID over
IPFS and compute it — a **cache miss, never a wrong answer**. So sharding is
a client/gateway concern layered above the wire, and it can't corrupt
anything. Because the cache is content-addressed and monotonic, nodes could
even gossip entries to each other — which is, again, the SP thesis.

## 8. Identity & capability boundary

- **Pure compute** (`cell-wasm`, resolved artifact): zero-capability, the
  open surface.
- **Paint** (identity-bearing): stays per-userspace, off the shared server.
- **Build / exec** (`nix`, `exec` steps): higher capability, behind distinct
  authz.

The wire must be able to express this split; the auth *scheme* is reserved
(see [server-interface.md](./server-interface.md) §10).

## 9. Sequencing

1. Refactor `call` → `perform_run(request) -> response` (CLI becomes a
   caller). No behavior change.
2. Add the invoker pool keyed by nucleus hash (§6.2) — useful even in CLI
   mode.
3. Add cache-lookup-before-invoke against the ledger (§4, §6.5) — now plain
   `dsm call` in a persistent userspace memoizes.
4. Wrap `perform_run` in a stdlib HTTP server, co-host with the ipfs daemon
   under one `dsm serve` (§6.4), with single-flight + a worker semaphore.
5. Only then, SP-side: the `dsm-remote` engine. Independent; can lag.

Steps 1–3 are pure desmata refactors with no SP dependency and immediate
payoff. Step 4 is the genuinely new surface.

## 10. Relationship to the other primers

- [server-interface.md](./server-interface.md) — the wire contract this note
  motivates. Read it for the request/response shapes.
- [session-cells.md](./session-cells.md) — the `Cell.session()` + `HomePolicy`
  lifecycle §6.2/§6.4 lean on; the `cell-session` runner (§3.3) and the
  injected-inputs door (§6) this serves. The **home provisioning plan**
  (server-interface.md §5) is that primer's `overlay` model, made executable
  and lifted onto the wire.
- [desmata-as-semantic-paint-app.md](./desmata-as-semantic-paint-app.md) —
  the two hats. Server mode is desmata-the-runner (§2a) exposed over HTTP; the
  identity boundary (§6.3, §8) is why desmata-the-app never handles keys.
- [lightweight-cells.md](./lightweight-cells.md) §4 — runners as named
  pluggable contracts; §5 the three weight classes generalize.
- [whats-next.md](./whats-next.md) §5 — the `nix` runner and `cell-session`
  runner this stands up. **When this is scheduled, it wants a whats-next row
  and its SP `docs/ROADMAP.md` twin** (the `dsm-remote` `SP_ENGINE`); that is
  a synchronized two-repo edit, left to the maintainer.
