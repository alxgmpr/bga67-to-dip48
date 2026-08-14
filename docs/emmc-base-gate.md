# eMMC base-variant gate

`base_variants/emmc/` does not exist yet, and it must not be routed until this gate
is satisfied.

## The gate

Per the suite spec (`docs/superpowers/specs/2026-08-13-bga-suite-design.md`, "Base
variants"):

> **Gate:** no base variant is routed until that family's XGecu adapter DIP48 pinout
> is verified — bench ring-out (as recorded in `docs/ringout-results.txt` for the
> NAND adapter) or authoritative vendor documentation. This is a per-family gate,
> not a suite blocker.

For eMMC specifically: `tools/ringout.py --family emmc docs/ringout-results-emmc.txt`
must exit 0 on a results file containing human-recorded bench measurements of the
physical adapter. Until that file exists and passes, the DF40-to-DIP48 wiring for
`base_variants/emmc/` is unknown, and guessing it risks a base-board respin — the same
risk the NAND ring-out gate exists to avoid.

This gate blocks only `base_variants/emmc/`. It does not block the eMMC BGA-153
carrier or chip boards (Tasks 7-9), which route to the DF40 contract directly and
never touch the XGecu adapter's DIP48 side.

## Why software can't check this

`tools/families.py` fixes the DF40 side of the eMMC mapping (which DF40 pin carries
CLK, CMD, DAT0-7, RST_n, DS, VCC, VCCQ, GND). What it cannot fix is which DIP48 pin
the XGecu adapter presents each of those signals on — that depends on the adapter's
internal wiring, which is not documented by XGecu in a form this repo can cite.
Nothing in ERC, DRC, or a netlist diff would catch a wrong guess: a `base_variants/emmc/`
board wired to an incorrect assumed DIP48 map would be internally self-consistent and
would fail only on the bench, expensively, after fabrication. Hence a multimeter.

## Procedure

1. Buy the adapter (see below).
2. Run `python3 tools/ringout.py --family emmc` to print the probe checklist.
3. Record readings in `docs/ringout-results-emmc.txt`, one line per DF40 pin as
   `<df40_pin> <dip48_pin_that_rang>` (or `-` if nothing rang), matching the format
   `docs/ringout-results.txt` uses for the NAND adapter.
4. Run `python3 tools/ringout.py --family emmc docs/ringout-results-emmc.txt`. It
   must report `PASS` (every probed DF40 pin reaches its own distinct DIP48 pin, no
   opens, no duplicates) before `base_variants/emmc/` is designed or routed.
5. Record the resulting DF40↔DIP48 map in `docs/connector-pinout.md` alongside the
   existing NAND TSOP48↔DIP48 table.

## Adapter to buy

XGecu store, "EMMC BGA153 BGA169 Adapter IC Socket for XGecu T76 Programmer with
Dual Head Spring-loaded test Probe Holder + 5PCS limit frames" ($39.00, at time of
writing):

<https://xgecu.myshopify.com/products/emmc-bga153-bga169-adapter-ic-socket-for-xgecu-t76-programmer-with-dual-head-spring-loaded-test-probe-holder-5pcs-limit-frames>

Confirmed from the product listing: explicitly supports BGA153/BGA169, is stated to
work only with the XGecu T76 (not TL866-series or T48), and ships with five limit
frames (11.5×13, 10×11, 12×16, 12×18, 14×18 mm) for seating different package sizes
in the socket. This is the only BGA153-specific eMMC adapter found in the XGecu T76
adapter collection (<https://xgecu.myshopify.com/collections/adapters-for-xgecu-t76-programmer>)
at time of writing; there is also a broader "EMMC BGA 5-in-1 Adapter kit" covering
BGA100/153/169/162/221, which is a plausible alternative if the dedicated 153/169
adapter becomes unavailable, but has not been evaluated here.
