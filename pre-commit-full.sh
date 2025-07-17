#!/bin/bash -e

tox -e format -- --check

for OS_VERSION in "15.3" "15.4" "15.5" "15.6" "15.6-ai" "15.6-spr" "15.7" "16.0" "tumbleweed"; do
    export OS_VERSION
    tox -e check_marks
done
