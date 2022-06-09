#!/bin/bash

if ! command -v fd > /dev/null; then
    echo "fd not installed, but required for formatting"
    exit 1
fi

if [ "$1" = "--check" ]; then
    set -e
    args="--check"
fi

black . ${args}
for f in $(fd '.*py$'); do
    reorder-python-imports $f
done
