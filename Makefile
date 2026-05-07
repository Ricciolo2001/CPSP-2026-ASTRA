# SPDX-FileCopyrightText: 2026 Alessandro Ricci
# SPDX-FileCopyrightText: 2026 Eyad Issa
# SPDX-FileCopyrightText: 2026 Giulia Pareschi
#
# SPDX-License-Identifier: MIT


PIO ?= pio


.PHONY: all cf-app cf-app-clean cf-esp-module cf-esp-module-clean flash flash-cf flash-esp clean help

all: cf-app .WAIT cf-esp-module
	@echo ""
	@echo "========================================="
	@echo "  Build complete!"
	@echo "========================================="
	@echo ""
	@echo "Next steps:"
	@echo ""
	@echo "  1. Flash the Crazyflie firmware:"
	@echo "       make flash-cf"
	@echo ""
	@echo "  2. Flash the ESP32 module:"
	@echo "       make flash-esp"
	@echo ""
	@echo "  3. Start the tracking software:"
	@echo "       cd pc-python && uv run track"
	@echo ""
	@echo "  Tip: run 'make help' to see all available targets."
	@echo ""

cf-app:
	@echo "Building cf-app..."
	cd cf-app && $(MAKE)

cf-app-clean:
	cd cf-app && $(MAKE) clean

cf-esp-module:
	@echo "Building cf-esp-module..."
	cd cf-esp-module && $(PIO) run $(PIO_FLAGS)

cf-esp-module-clean:
	cd cf-esp-module && $(PIO) run --target clean $(PIO_FLAGS)

flash: flash-cf flash-esp

flash-cf:
	cd cf-app && $(MAKE) flash

flash-esp:
	cd cf-esp-module && $(PIO) run --target upload $(PIO_FLAGS)

clean: cf-app-clean cf-esp-module-clean

help:
	@echo "Targets:"
	@echo "  all             Build cf-app and cf-esp-module"
	@echo "  cf-app          Build the Crazyflie app"
	@echo "  cf-esp-module   Build the ESP32 module"
	@echo "  flash           Flash both targets"
	@echo "  flash-cf        Flash the Crazyflie app"
	@echo "  flash-esp       Flash the ESP32 module"
	@echo "  clean           Clean all build artifacts"
	@echo ""
	@echo "Variables:"
	@echo "  PIO=<path>      Path to the PlatformIO CLI (default: pio)"
	@echo "  VERBOSE=1       Show full build output (default: 0)"
