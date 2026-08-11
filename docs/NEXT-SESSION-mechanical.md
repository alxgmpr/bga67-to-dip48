# Next session: shrink board B, and design the standoff system

Paste the block below into a fresh session. Everything it needs is either in
here or in the repo.

---

I want to rethink the mechanical design of `~/bga67-to-dip48`, a two-board
BGA-67 NAND → DIP48 adapter for an XGecu T76. **Brainstorm and design first —
do not touch CAD until we've agreed an approach.**

Three linked questions:

1. **Board B is too big.** It is 30.05 × 90.05 mm, but every pad on it fits
   inside 22.47 × 58.42 mm. The DIP48 span (23 × 2.54 = 58.42 mm) is fixed by
   the socket and is the only hard dimensional constraint. Roughly 25 × 62 mm
   looks achievable — about 43 % less area. What is actually forcing the
   current size, and how small can it honestly get?

2. **Closer to NandBug's proportions.** courk's NandBug
   (github.com/courk/Nandbug-Hardware) fits its interposer much more tightly to
   the BGA-67. Read that repo and tell me what is genuinely worth copying.
   **Check the premise before optimising it** — our carrier is already
   package-tight at 9.25 × 7.45 mm against a U1 courtyard of 8.59 × 7.09 mm,
   and NandBug's interposer solves a *different* problem: it uses a mirrored
   BGA footprint and solders into the Home Mini in place of the flash, whereas
   ours carries a desoldered chip into a programmer. Say so if the analogy
   doesn't hold rather than forcing it.

3. **There is no standoff system and there needs to be one.** Neither board has
   a single mounting hole. The assembly hangs **6.6 mm** below board B's bottom
   face: 4.0 mm mezzanine gap + 1.6 mm carrier PCB + 1.0 mm VFBGA67. The
   carrier — with the flash on it — is currently the lowest thing on the
   assembly and would take the load if you set it down. Design a proper
   standoff/seating system sized to the real stack.

## The load case, which is the actual problem

Board B's DIP48 field is **two 1×24 surface-mount socket strips**. The XGecu
adapter's 48 machined pins insert into them from above — roughly **30–50 N**,
straight into SMT pads with **no through-hole anchor anywhere on the board**.
This is simultaneously the highest-force joint, the most-cycled joint, and the
one with the least mechanical retention. Any standoff design should be taking
that force, not just holding the board off the bench.

I already pushed back on going surface-mount here for exactly this reason and
chose it anyway; the goal now is to make that decision safe, not to relitigate
it.

## Current state — all verified, `make check` is green

| | |
|---|---|
| carrier | 9.25 × 7.45 mm, 4-layer. `U1` (VFBGA67, 6.5 × 8.0, 0.8 mm pitch) on B.Cu; `J1` DF40TC-30DP-0.4V(51) plug on F.Cu. Routed, DRC clean, panelised 4×4 at 56.80 × 49.60 mm, 16 up |
| base | 30.05 × 90.05 mm, 4-layer. `J1` DF40TC(4.0)-30DS-0.4V(51) receptacle on **B.Cu**; `J2` DIP48 SMT socket field on F.Cu; C1/C2/R1/R2 on F.Cu. 0 DRC violations, 0 unconnected |
| mezzanine | DF40TC, **4.0 mm** mated. 30 pos, 0.4 mm pitch, no retention tabs, **10 mating cycles**, 0.3 A |
| stack below base | 4.0 + 1.6 + 1.0 = **6.6 mm** |
| mounting holes | **zero, on both boards** |

The carrier hangs centred *between* the two DIP rows, on the underside, and
clears the inner pad edges by ~1.3 mm each side.

## Constraints — do not break these

- `docs/connector-pinout.md` is the interface contract between the two boards.
  Any change to the J1 assignment must land on **both** boards in the same
  commit. `tools/pinout.py` asserts the checkerboard invariants.
- **Do not permute the data bus.** Commands and addresses ride the same I/O
  pins; a swizzle corrupts the command byte and the device stops responding.
- **Do not use the Konnect MCP tools.** Edit files directly.
- **Close KiCad before editing project files** — it writes its in-memory copy
  over yours on save. This has already cost one lost edit.
- `make check` must stay green (rules in sync, pinout, ERC + DRC on both).
- Two routes on board B are hand work `tools/route_base.py` cannot reproduce:
  `J1.6`'s inward B.Cu escape, and the GND pad tie at (121.5, 89.5) →
  (122.56, 89.502). `strip()` preserves F.Cu and B.Cu so a rerun keeps them,
  but verify they survive.
- Resizing the outline invalidates the GND stitching and pour, so `make
  route-base` will need rerunning and re-verifying.
- Shrinking board B moves the carrier relative to the DIP rows — recheck the
  10.04 mm inner channel and the 0603 courtyards, which already had to be
  nudged 0.5 mm once for exactly this reason.

## Open questions worth folding in

- Does the XGecu adapter's **body** overhang board B? Nothing has checked this,
  and the SMT field seats it ~3 mm lower than a through-hole socket would.
- Adapter **pin-1 corner** and DIP48 row spacing are still unconfirmed on the
  bench; `tools/ringout.py` will check readings if measured. The *signal* table
  is confirmed — two manufacturer datasheets plus a working 285 MB dump.
- The DF40TC plug's end pads are unverified; the footprint omits them
  deliberately. See `docs/HANDOFF.md`.

## What I want out of the session

A design proposal with real numbers and trade-offs — board outline, hole
pattern and sizes, standoff heights and hardware (part numbers), and how the
insertion load is carried. Then a plan. Read `README.md`, `docs/HANDOFF.md` and
`docs/connector-pinout.md` first; they carry the reasoning behind decisions
that look arbitrary.
