PIO = pio

.PHONY: all
all: cf-app .WAIT cf-esp-module

.PHONY: cf-app cf-app-clean
cf-app:
	cd cf-app && $(MAKE)
cf-app-clean:
	cd cf-app && $(MAKE) clean

.PHONY: cf-esp-module cf-esp-module-clean
cf-esp-module:
	cd cf-esp-module && $(PIO) run
cf-esp-module-clean:
	cd cf-esp-module && $(PIO) run --target clean

.PHONY: clean
clean: cf-app-clean cf-esp-module-clean
