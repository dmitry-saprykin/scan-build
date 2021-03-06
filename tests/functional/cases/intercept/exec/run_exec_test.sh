#!/usr/bin/env bash
# REQUIRES: preload
# RUN: cmake -B%T -H%S
# RUN: make -C %T
# RUN: intercept-build --cdb %T/result.json %T/exec -C %T -o expected.json
# RUN: cdb_diff %T/result.json %T/expected.json
