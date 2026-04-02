# SPDX-License-Identifier: MIT
# SPDX-FileCopyrightText: 2026 Eyad Issa <eyadlorenzo@gmail.com>

LLVM_INTERCEPT_TOOL ?= intercept-build

CRAZYFLIE_BASE 	:= ../cf-firmware
OOT_CONFIG 		:= $(PWD)/app-config

include $(CRAZYFLIE_BASE)/tools/make/oot.mk

.PHONY: compile_commands
compile_commands:
	$(LLVM_INTERCEPT_TOOL) $(MAKE)
