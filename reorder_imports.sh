#!/bin/bash

for f in $(ls *py bci_tester/*py); do
    reorder-python-imports $f
done
