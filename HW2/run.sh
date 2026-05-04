#!/bin/bash

INFILE="$1"
OUTFILE="$2"
OUTFILE_PIP="$3"

python3 main.py "$INFILE" "$OUTFILE" "$OUTFILE_PIP"
