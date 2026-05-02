#!/bin/bash
set -u

TEST_MODE="${1:-stress}"
CAP_FACTOR="${MAX_CYCLE_FACTOR:-6}"

declare -a TEST_ROOTS
case "$TEST_MODE" in
    stress|stress_tests)
        TEST_ROOTS=("./stress_tests")
        ;;
    given|given_tests)
        TEST_ROOTS=("./given_tests")
        ;;
    both)
        TEST_ROOTS=("./stress_tests" "./given_tests")
        ;;
    *)
        if [ -d "$TEST_MODE" ]; then
            TEST_ROOTS=("$TEST_MODE")
        else
            echo "Unknown mode/path: $TEST_MODE"
            echo "Usage: ./run_stress_semantic.sh [stress|given|both|<test_dir>]"
            exit 2
        fi
        ;;
esac

for root in "${TEST_ROOTS[@]}"
do
    if [ ! -d "$root" ]; then
        echo "Test directory not found: $root"
        exit 2
    fi
done

passed=0
failed=0

for TEST_ROOT in "${TEST_ROOTS[@]}"
do
for tdir in "$TEST_ROOT"/*
do
    [ -d "$tdir" ] || continue

    input="$tdir/input.json"
    output="$tdir/user_output.json"

    if [ ! -f "$input" ]; then
        echo "--"
        echo "SKIP $(basename "$tdir"): missing input.json"
        continue
    fi

    echo "--"
    if [ -f "$tdir/desc.txt" ]; then
        cat "$tdir/desc.txt"
    else
        echo "$(basename "$tdir")"
    fi

    if ! MAX_CYCLE_FACTOR="$CAP_FACTOR" python3 main.py "$input" "$output"; then
        echo "FAIL $(basename "$tdir"): simulator failed"
        failed=$((failed + 1))
        continue
    fi

    meta_file="${output}.meta.json"
    if [ -f "$meta_file" ]; then
        cycle_report="$(python3 - "$meta_file" <<'PY'
import json
import sys

meta_path = sys.argv[1]
try:
    with open(meta_path, "r") as f:
        meta = json.load(f)
    est = int(meta.get("estimated_cycles", -1))
    act = int(meta.get("actual_cycles", -1))
    if est > 0 and act >= 0:
        delta = act - est
        sign = "+" if delta >= 0 else ""
        pct = (delta / est) * 100.0
        print(f"Cycles: estimate={est} actual={act} delta={sign}{delta} ({sign}{pct:.1f}%)")
    else:
        print("Cycles: estimate unavailable")
except Exception:
    print("Cycles: estimate unavailable")
PY
)"
        echo "$cycle_report"
    else
        echo "Cycles: estimate unavailable"
    fi

    if ! python3 checker_micro.py "$input" "$output"; then
        echo "FAIL $(basename "$tdir"): checker_micro"
        failed=$((failed + 1))
        continue
    fi

    if ! python3 checker_os.py "$input" "$output"; then
        echo "FAIL $(basename "$tdir"): checker_os"
        failed=$((failed + 1))
        continue
    fi

    echo "PASS $(basename "$tdir")"
    passed=$((passed + 1))
done
done

echo "--"
echo "Summary: mode=$TEST_MODE passed=$passed failed=$failed"

if [ "$failed" -ne 0 ]; then
    exit 1
fi
