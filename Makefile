KICAD_CLI ?= /Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli

KICAD_PY ?= /Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/3.9/Resources/Python.app/Contents/MacOS/Python

.PHONY: help panel check suite-check pinout rules ringout clean

help:
	@echo "make rules    push the JLCPCB 4-layer rule set into every project"
	@echo "make panel    rebuild panel/ from carrier/ (close KiCad first)"
	@echo "make check    rules in sync, pinout, then ERC+DRC on both projects"
	@echo "make pinout   verify tools/pinout.py invariants"
	@echo "make ringout  check the recorded XGecu adapter ring-out"
	@echo "              (no args: print the probe checklist)"

rules:
	@./tools/drc-rules.py

panel:
	@./tools/panelize.sh

pinout:
	@python3 tools/pinout.py && echo "pinout ok"

# Not part of `check`: it needs readings a human took with a meter.
ringout:
	@python3 tools/ringout.py docs/ringout-results.txt

suite-check:
	@python3 tools/pinout.py >/dev/null && python3 tools/families.py
	@python3 tools/check_package.py
	@python3 tools/tests/test_families.py
	@python3 tools/tests/test_vfbga67_package.py
	@$(KICAD_PY) tools/tests/test_gen_footprint.py 2>/dev/null
	@$(KICAD_PY) tools/tests/test_gen_board.py 2>/dev/null
	@$(KICAD_PY) tools/check_interposer.py --all-boards 2>/dev/null

check: suite-check pinout
	@python3 tools/check_mating.py
	@$(KICAD_PY) tools/check_interposer.py 2>/dev/null
	@./tools/drc-rules.py --check
	@check_result=0; for p in carrier base chip; do \
		printf '%-8s erc  ' $$p; \
		$(KICAD_CLI) sch erc --exit-code-violations --severity-error \
			-o /tmp/$$p-erc.json --format json $$p/$$p.kicad_sch >/dev/null 2>&1 \
			&& echo clean || { echo FAIL; check_result=1; }; \
		printf '%-8s drc  ' $$p; \
		$(KICAD_CLI) pcb drc --refill-zones --exit-code-violations --severity-error \
			-o /tmp/$$p-drc.json --format json $$p/$$p.kicad_pcb >/dev/null 2>&1 \
			&& echo clean || { echo FAIL; check_result=1; }; \
	done; exit $$check_result

clean:
	@rm -f /tmp/carrier-drc.json /tmp/panel-drc.json /tmp/base-drc.json
	@rm -rf tools/__pycache__
