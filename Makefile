# NV-Disruptron — use ./scripts/disruptron <command>
.PHONY: help setup validate test monitor start start-daemon start-stack configure install

ROOT := $(abspath $(dir $(lastword $(MAKEFILE_LIST))))
DISRUPTRON := $(ROOT)/scripts/disruptron
export DISRUPTRON_ROOT := $(ROOT)

help:
	@$(DISRUPTRON) help

setup:
	@$(DISRUPTRON) setup

validate:
	@$(DISRUPTRON) validate

test:
	@$(DISRUPTRON) test all

monitor:
	@$(DISRUPTRON) monitor

start:
	@$(DISRUPTRON) run

start-daemon:
	@$(DISRUPTRON) daemon

start-stack:
	@$(DISRUPTRON) run --channels

configure:
	@$(DISRUPTRON) configure

install:
	@$(DISRUPTRON) install
