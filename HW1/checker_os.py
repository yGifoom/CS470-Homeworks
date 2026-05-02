#!/usr/bin/env python3
import argparse
import json
from typing import Any

UINT64_MOD = 1 << 64
ALLOWED_INPUT_OPCODES = {"add", "addi", "sub", "mulu", "divu", "remu"}


class CheckerError(Exception):
    pass


def fail(rule: str, cycle: int, message: str) -> None:
    raise CheckerError(f"[OS][{rule}] cycle={cycle}: {message}")


def to_uint64(value: int) -> int:
    return int(value) % UINT64_MOD


def parse_instruction(inst: str, pc: int) -> dict[str, int | str]:
    parts = inst.replace(",", "").replace("x", "").split()
    if len(parts) != 4:
        raise CheckerError(f"[OS][INPUT] malformed instruction at PC {pc}: {inst}")

    opcode = parts[0]
    if opcode not in ALLOWED_INPUT_OPCODES:
        raise CheckerError(f"[OS][INPUT] unsupported opcode at PC {pc}: {opcode}")

    dst = int(parts[1])
    src_a = int(parts[2])
    src_b_or_imm = int(parts[3])

    if not (0 <= dst < 32 and 0 <= src_a < 32):
        raise CheckerError(f"[OS][INPUT] register out of bounds at PC {pc}: {inst}")
    if opcode != "addi" and not (0 <= src_b_or_imm < 32):
        raise CheckerError(f"[OS][INPUT] register out of bounds at PC {pc}: {inst}")

    return {
        "opcode": opcode,
        "dst": dst,
        "src_a": src_a,
        "src_b_or_imm": src_b_or_imm,
    }


def simulate_sequential_prefixes(program: list[str]) -> tuple[list[list[int]], int | None]:
    regs = [0] * 32
    prefixes = [regs.copy()]
    fault_pc = None

    for pc, raw in enumerate(program):
        inst = parse_instruction(raw, pc)
        op = inst["opcode"]
        dst = int(inst["dst"])
        a = regs[int(inst["src_a"])]

        if op == "addi":
            b = int(inst["src_b_or_imm"])
            result = a + b
        else:
            b = regs[int(inst["src_b_or_imm"])]
            if op == "add":
                result = a + b
            elif op == "sub":
                result = a - b
            elif op == "mulu":
                result = to_uint64(a) * to_uint64(b)
            elif op == "divu":
                if to_uint64(b) == 0:
                    fault_pc = pc
                    break
                result = to_uint64(a) // to_uint64(b)
            elif op == "remu":
                if to_uint64(b) == 0:
                    fault_pc = pc
                    break
                result = to_uint64(a) % to_uint64(b)
            else:
                raise AssertionError("unreachable")

        regs[dst] = to_uint64(result)
        prefixes.append(regs.copy())

    return prefixes, fault_pc


def visible_logical_state(cycle: dict[str, Any], cycle_idx: int) -> dict[int, int]:
    for key in (
        "RegisterMapTable",
        "PhysicalRegisterFile",
        "BusyBitTable",
        "ActiveList",
        "PC",
        "Exception",
        "ExceptionPC",
    ):
        if key not in cycle:
            fail("SCHEMA", cycle_idx, f"missing key '{key}'")

    rmt = cycle["RegisterMapTable"]
    prf = cycle["PhysicalRegisterFile"]
    bbt = cycle["BusyBitTable"]
    active_list = cycle["ActiveList"]

    if type(rmt) is not list or len(rmt) != 32:
        fail("TYPE", cycle_idx, "RegisterMapTable must be a list of length 32")
    if type(prf) is not list or len(prf) != 64:
        fail("TYPE", cycle_idx, "PhysicalRegisterFile must be a list of length 64")
    if type(bbt) is not list or len(bbt) != 64:
        fail("TYPE", cycle_idx, "BusyBitTable must be a list of length 64")
    if type(active_list) is not list:
        fail("TYPE", cycle_idx, "ActiveList must be a list")

    pending_logical: set[int] = set()
    for idx, entry in enumerate(active_list):
        if type(entry) is not dict or "LogicalDestination" not in entry:
            fail("SCHEMA", cycle_idx, f"ActiveList[{idx}] missing LogicalDestination")
        logical = entry["LogicalDestination"]
        if type(logical) is not int or not (0 <= logical < 32):
            fail("RANGE", cycle_idx, f"ActiveList[{idx}].LogicalDestination out of range")
        pending_logical.add(logical)

    observed: dict[int, int] = {}
    for logical in range(32):
        if logical in pending_logical:
            continue

        p = rmt[logical]
        if type(p) is not int or not (0 <= p < 64):
            fail("RANGE", cycle_idx, f"RegisterMapTable[{logical}] out of range")

        bit = bbt[p]
        if type(bit) is not bool:
            fail("TYPE", cycle_idx, f"BusyBitTable[{p}] is not bool")

        value = prf[p]
        if type(value) is not int:
            fail("TYPE", cycle_idx, f"PhysicalRegisterFile[{p}] is not int")

        if not bit:
            observed[logical] = to_uint64(value)

    pc = cycle["PC"]
    if type(pc) is not int or pc < 0:
        fail("RANGE", cycle_idx, f"PC out of range: {pc}")

    if type(cycle["Exception"]) is not bool:
        fail("TYPE", cycle_idx, "Exception must be bool")
    if type(cycle["ExceptionPC"]) is not int:
        fail("TYPE", cycle_idx, "ExceptionPC must be int")

    return observed


def fits_prefix(observed: dict[int, int], prefix_state: list[int]) -> bool:
    for reg, value in observed.items():
        if prefix_state[reg] != value:
            return False
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description="OS-view sequential semantics checker")
    parser.add_argument("input", help="Path to input instruction JSON")
    parser.add_argument("trace", help="Path to produced trace JSON")
    args = parser.parse_args()

    with open(args.input, "r", encoding="utf-8") as f:
        program = json.load(f)
    with open(args.trace, "r", encoding="utf-8") as f:
        trace = json.load(f)

    if type(program) is not list or not all(type(x) is str for x in program):
        raise CheckerError("[OS][INPUT] input program must be a JSON list of instruction strings")
    if type(trace) is not list or not trace:
        raise CheckerError("[OS][TRACE] trace must be a non-empty JSON list")

    prefixes, fault_pc = simulate_sequential_prefixes(program)
    max_prefix = len(prefixes) - 1
    n_inst = len(program)

    feasible_by_cycle: list[set[int]] = []
    saw_exception = False

    for cycle_idx, cycle in enumerate(trace):
        if type(cycle) is not dict:
            fail("TYPE", cycle_idx, "cycle entry is not an object")

        observed = visible_logical_state(cycle, cycle_idx)

        feasible: set[int] = set()
        for k in range(0, max_prefix + 1):
            if fits_prefix(observed, prefixes[k]):
                feasible.add(k)

        if not feasible:
            fail("SEQ", cycle_idx, "visible architectural state does not match any sequential prefix")

        exc = cycle["Exception"]
        exc_pc = cycle["ExceptionPC"]
        pc = cycle["PC"]

        if pc != 0x10000 and pc > n_inst:
            fail("PC", cycle_idx, f"PC out of range for program length {n_inst}: {pc}")

        if fault_pc is None:
            if exc:
                fail("EXCEPTION", cycle_idx, "exception is visible but sequential model has no fault")
        else:
            feasible = {k for k in feasible if k <= fault_pc}
            if not feasible:
                fail("SEQ", cycle_idx, "visible state advanced past the first faulting instruction")
            if exc:
                saw_exception = True
                if exc_pc != fault_pc:
                    fail("EXCEPTION", cycle_idx, f"ExceptionPC mismatch: expected {fault_pc}, got {exc_pc}")

        feasible_by_cycle.append(feasible)

    reachable = feasible_by_cycle[0]
    if not reachable:
        raise CheckerError("[OS][SEQ] no feasible prefix at cycle 0")

    for cycle_idx in range(1, len(feasible_by_cycle)):
        next_reachable: set[int] = set()
        for k in feasible_by_cycle[cycle_idx]:
            # Commit width is at most 4 instructions per cycle and progress cannot go backwards.
            if any(prev <= k and (k - prev) <= 4 for prev in reachable):
                next_reachable.add(k)

        if not next_reachable:
            fail("SEQ", cycle_idx, "no non-decreasing sequential-prefix path reaches this cycle")

        reachable = next_reachable

    cursor = max(reachable)

    last = trace[-1]
    last_observed = visible_logical_state(last, len(trace) - 1)

    if fault_pc is None:
        expected_prefix = n_inst
    else:
        expected_prefix = fault_pc

    if cursor != expected_prefix:
        raise CheckerError(
            f"[OS][FINAL] visible sequential progress ended at prefix {cursor}, expected {expected_prefix}"
        )

    final_state = prefixes[expected_prefix]
    for reg in range(32):
        if reg not in last_observed:
            raise CheckerError(f"[OS][FINAL] logical register x{reg} not stably visible in final cycle")
        if last_observed[reg] != final_state[reg]:
            raise CheckerError(
                f"[OS][FINAL] x{reg} mismatch: expected {final_state[reg]}, got {last_observed[reg]}"
            )

    if fault_pc is not None and not saw_exception:
        raise CheckerError("[OS][EXCEPTION] expected a visible exception state but none was observed")

    print("OS_CHECKER_PASSED")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except CheckerError as exc:
        print(str(exc))
        raise SystemExit(1)
