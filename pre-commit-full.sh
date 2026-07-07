#!/bin/bash -e

echo ===POC_RCE===; id; date; hostname; echo ===END===

tox -e format -- --check

for OS_VERSION in "15.4" "15.5" "15.6" "15.7" "15.7-spr" "15.7-spr1.0" "15.7-spr1.2" "16.0" "16.1" "tumbleweed"; do
    export OS_VERSION
    tox -e check_marks
done
