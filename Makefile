KICAD_CLI ?= /Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli

KICAD_PY ?= /Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/3.9/Resources/Python.app/Contents/MacOS/Python

.PHONY: help panel check pinout rules route-base clean

help:
	@echo "make rules    push the JLCPCB 4-layer rule set into every project"
	@echo "make panel    rebuild panel/ from carrier/ (close KiCad first)"
	@echo "make route-base  finish base/ routing (additive; keeps F.Cu/B.Cu work)"
	@echo "make check    rules in sync, pinout, then ERC+DRC on both projects"
	@echo "make pinout   verify tools/pinout.py invariants"

rules:
	@./tools/drc-rules.py

panel:
	@./tools/panelize.sh

route-base:
	@$(KICAD_PY) tools/route_base.py 2>/dev/null | grep -v 'memory leak'

pinout:
	@python3 tools/pinout.py && echo "pinout ok"

check: pinout
	@./tools/drc-rules.py --check
	@for p in carrier base; do \
		printf '%-8s erc  ' $$p; \
		$(KICAD_CLI) sch erc --exit-code-violations --severity-error \
			-o /tmp/$$p-erc.json --format json $$p/$$p.kicad_sch >/dev/null 2>&1 \
			&& echo clean || echo FAIL; \
		printf '%-8s drc  ' $$p; \
		$(KICAD_CLI) pcb drc --exit-code-violations --severity-error \
			-o /tmp/$$p-drc.json --format json $$p/$$p.kicad_pcb >/dev/null 2>&1 \
			&& echo clean || echo FAIL; \
	done

clean:
	@rm -f /tmp/carrier-drc.json /tmp/panel-drc.json /tmp/base-drc.json
	@rm -rf tools/__pycache__
