#!/bin/bash -e

tox -e format -- --check

for OS_VERSION in "15.4" "15.5" "15.6" "15.6-spr" "15.7" "15.7-spr" "16.0" "tumbleweed"; do
    export OS_VERSION
    tox -e check_marks
done
