#!/usr/bin/env python3
import argparse
import json
from typing import Any

UINT64_MOD = 1 << 64
ALLOWED_DUMP_OPCODES = {"add", "sub", "mulu", "divu", "remu"}
ALLOWED_INPUT_OPCODES = {"add", "addi", "sub", "mulu", "divu", "remu"}


class CheckerError(Exception):
    pass


def fail(rule: str, cycle: int, message: str) -> None:
    raise CheckerError(f"[MICRO][{rule}] cycle={cycle}: {message}")


def parse_instruction(inst: str, pc: int) -> dict[str, int | str]:
    parts = inst.replace(",", "").replace("x", "").split()
    if len(parts) != 4:
        raise CheckerError(f"[MICRO][INPUT] malformed instruction at PC {pc}: {inst}")

    opcode = parts[0]
    if opcode not in ALLOWED_INPUT_OPCODES:
        raise CheckerError(f"[MICRO][INPUT] unsupported opcode at PC {pc}: {opcode}")

    dst = int(parts[1])
    src_a = int(parts[2])
    src_b_or_imm = int(parts[3])

    if not (0 <= dst < 32 and 0 <= src_a < 32):
        raise CheckerError(f"[MICRO][INPUT] register out of bounds at PC {pc}: {inst}")
    if opcode != "addi" and not (0 <= src_b_or_imm < 32):
        raise CheckerError(f"[MICRO][INPUT] register out of bounds at PC {pc}: {inst}")

    return {
        "opcode": opcode,
        "dst": dst,
        "src_a": src_a,
        "src_b_or_imm": src_b_or_imm,
    }


def to_uint64(value: int) -> int:
    return int(value) % UINT64_MOD


def simulate_sequential(program: list[str]) -> tuple[list[list[int]], int | None]:
    regs = [0] * 32
    states = [regs.copy()]
    fault_pc = None

    for pc, raw in enumerate(program):
        inst = parse_instruction(raw, pc)
        op = inst["opcode"]
        dst = int(inst["dst"])
        a = regs[int(inst["src_a"])]

        if op == "addi":
            b = int(inst["src_b_or_imm"])
            res = a + b
        else:
            b = regs[int(inst["src_b_or_imm"])]
            if op == "add":
                res = a + b
            elif op == "sub":
                res = a - b
            elif op == "mulu":
                res = to_uint64(a) * to_uint64(b)
            elif op == "divu":
                if to_uint64(b) == 0:
                    fault_pc = pc
                    break
                res = to_uint64(a) // to_uint64(b)
            elif op == "remu":
                if to_uint64(b) == 0:
                    fault_pc = pc
                    break
                res = to_uint64(a) % to_uint64(b)
            else:
                raise AssertionError("unreachable")

        regs[dst] = to_uint64(res)
        states.append(regs.copy())

    return states, fault_pc


def expect_type(cycle: int, key: str, value: Any, expected: type) -> None:
    if type(value) is not expected:
        fail("TYPE", cycle, f"key '{key}' expected {expected.__name__}, got {type(value).__name__}")


def validate_cycle_schema(cycle_idx: int, cycle: dict[str, Any], n_inst: int) -> None:
    required = {
        "ActiveList": list,
        "BusyBitTable": list,
        "DecodedPCs": list,
        "Exception": bool,
        "ExceptionPC": int,
        "FreeList": list,
        "IntegerQueue": list,
        "PC": int,
        "PhysicalRegisterFile": list,
        "RegisterMapTable": list,
    }

    for key, typ in required.items():
        if key not in cycle:
            fail("SCHEMA", cycle_idx, f"missing key '{key}'")
        expect_type(cycle_idx, key, cycle[key], typ)

    bbt = cycle["BusyBitTable"]
    prf = cycle["PhysicalRegisterFile"]
    rmt = cycle["RegisterMapTable"]
    free_list = cycle["FreeList"]
    decoded = cycle["DecodedPCs"]
    active = cycle["ActiveList"]
    iq = cycle["IntegerQueue"]

    if len(bbt) != 64:
        fail("LEN", cycle_idx, f"BusyBitTable length must be 64, got {len(bbt)}")
    if len(prf) != 64:
        fail("LEN", cycle_idx, f"PhysicalRegisterFile length must be 64, got {len(prf)}")
    if len(rmt) != 32:
        fail("LEN", cycle_idx, f"RegisterMapTable length must be 32, got {len(rmt)}")
    if len(decoded) > 4:
        fail("WIDTH", cycle_idx, f"DecodedPCs width > 4: {len(decoded)}")
    if len(active) > 32:
        fail("WIDTH", cycle_idx, f"ActiveList size > 32: {len(active)}")
    if len(iq) > 32:
        fail("WIDTH", cycle_idx, f"IntegerQueue size > 32: {len(iq)}")

    for idx, bit in enumerate(bbt):
        if type(bit) is not bool:
            fail("TYPE", cycle_idx, f"BusyBitTable[{idx}] is not bool")

    for idx, value in enumerate(prf):
        if type(value) is not int:
            fail("TYPE", cycle_idx, f"PhysicalRegisterFile[{idx}] is not int")

    for idx, p in enumerate(rmt):
        if type(p) is not int or not (0 <= p < 64):
            fail("RANGE", cycle_idx, f"RegisterMapTable[{idx}] out of range: {p}")

    if len(set(rmt)) != 32:
        fail("RMT", cycle_idx, "RegisterMapTable must map to 32 distinct physical registers")

    for idx, p in enumerate(free_list):
        if type(p) is not int or not (0 <= p < 64):
            fail("RANGE", cycle_idx, f"FreeList[{idx}] out of range: {p}")

    if len(set(free_list)) != len(free_list):
        fail("FREELIST", cycle_idx, "FreeList has duplicate physical registers")

    for idx, pc in enumerate(decoded):
        if type(pc) is not int or not (0 <= pc < n_inst):
            fail("RANGE", cycle_idx, f"DecodedPCs[{idx}] out of range: {pc}")

    if decoded != sorted(decoded):
        fail("DECODE", cycle_idx, "DecodedPCs must be sorted")

    if len(decoded) > 1:
        for i in range(1, len(decoded)):
            if decoded[i] != decoded[i - 1] + 1:
                fail("DECODE", cycle_idx, "DecodedPCs must be contiguous")

    prev_pc = -1
    for idx, entry in enumerate(active):
        if type(entry) is not dict:
            fail("TYPE", cycle_idx, f"ActiveList[{idx}] is not object")
        for key, typ in {
            "Done": bool,
            "Exception": bool,
            "LogicalDestination": int,
            "OldDestination": int,
            "PC": int,
        }.items():
            if key not in entry:
                fail("SCHEMA", cycle_idx, f"ActiveList[{idx}] missing '{key}'")
            expect_type(cycle_idx, f"ActiveList[{idx}].{key}", entry[key], typ)

        v_dest = entry["LogicalDestination"]
        old_dest = entry["OldDestination"]
        pc = entry["PC"]
        if not (0 <= v_dest < 32):
            fail("RANGE", cycle_idx, f"ActiveList[{idx}].LogicalDestination out of range: {v_dest}")
        if not (0 <= old_dest < 64):
            fail("RANGE", cycle_idx, f"ActiveList[{idx}].OldDestination out of range: {old_dest}")
        if not (0 <= pc < n_inst):
            fail("RANGE", cycle_idx, f"ActiveList[{idx}].PC out of range: {pc}")
        if pc <= prev_pc:
            fail("ORDER", cycle_idx, "ActiveList PCs must be strictly increasing")
        prev_pc = pc

        if entry["Exception"] and not entry["Done"]:
            fail("EXCEPTION", cycle_idx, "ActiveList exception entry must be done")

    for idx, entry in enumerate(iq):
        if type(entry) is not dict:
            fail("TYPE", cycle_idx, f"IntegerQueue[{idx}] is not object")

        base_keys = [
            "DestRegister",
            "OpAIsReady",
            "OpARegTag",
            "OpAValue",
            "OpBIsReady",
            "OpBRegTag",
            "OpBValue",
            "OpCode",
            "PC",
        ]
        for key in base_keys:
            if key not in entry:
                fail("SCHEMA", cycle_idx, f"IntegerQueue[{idx}] missing '{key}'")

        expect_type(cycle_idx, f"IntegerQueue[{idx}].DestRegister", entry["DestRegister"], int)
        expect_type(cycle_idx, f"IntegerQueue[{idx}].OpAIsReady", entry["OpAIsReady"], bool)
        expect_type(cycle_idx, f"IntegerQueue[{idx}].OpARegTag", entry["OpARegTag"], int)
        expect_type(cycle_idx, f"IntegerQueue[{idx}].OpAValue", entry["OpAValue"], int)
        expect_type(cycle_idx, f"IntegerQueue[{idx}].OpBIsReady", entry["OpBIsReady"], bool)
        expect_type(cycle_idx, f"IntegerQueue[{idx}].OpBRegTag", entry["OpBRegTag"], int)
        expect_type(cycle_idx, f"IntegerQueue[{idx}].OpBValue", entry["OpBValue"], int)
        expect_type(cycle_idx, f"IntegerQueue[{idx}].OpCode", entry["OpCode"], str)
        expect_type(cycle_idx, f"IntegerQueue[{idx}].PC", entry["PC"], int)

        if entry["OpCode"] not in ALLOWED_DUMP_OPCODES:
            fail("OPCODE", cycle_idx, f"IntegerQueue[{idx}].OpCode unknown: {entry['OpCode']}")

        if not (0 <= entry["DestRegister"] < 64):
            fail("RANGE", cycle_idx, f"IntegerQueue[{idx}].DestRegister out of range")
        if not (0 <= entry["PC"] < n_inst):
            fail("RANGE", cycle_idx, f"IntegerQueue[{idx}].PC out of range")
        if not (0 <= entry["OpARegTag"] < 64):
            fail("RANGE", cycle_idx, f"IntegerQueue[{idx}].OpARegTag out of range")
        if not (0 <= entry["OpBRegTag"] < 64):
            fail("RANGE", cycle_idx, f"IntegerQueue[{idx}].OpBRegTag out of range")

    pc = cycle["PC"]
    if pc < 0:
        fail("RANGE", cycle_idx, f"PC out of range: {pc}")
    if pc != 0x10000 and pc > n_inst:
        fail("RANGE", cycle_idx, f"PC out of range for program length {n_inst}: {pc}")


def validate_cross_cycle(trace: list[dict[str, Any]], fault_pc: int | None, n_inst: int) -> None:
    saw_exception = False
    saw_fault_entry = False

    for idx, cycle in enumerate(trace):
        exc = cycle["Exception"]
        if exc:
            saw_exception = True
            if fault_pc is None:
                fail("EXCEPTION", idx, "trace enters exception mode but sequential execution has no exception")
            if cycle["ExceptionPC"] != fault_pc:
                fail("EXCEPTION", idx, f"ExceptionPC mismatch: expected {fault_pc}, got {cycle['ExceptionPC']}")
            if cycle["DecodedPCs"]:
                fail("EXCEPTION", idx, "DecodedPCs must be empty during exception recovery")
            if cycle["IntegerQueue"]:
                fail("EXCEPTION", idx, "IntegerQueue must be empty during exception recovery")
            if cycle["PC"] != 0x10000:
                fail("EXCEPTION", idx, f"PC should be 0x10000 in exception mode, got {cycle['PC']}")

        for entry in cycle["ActiveList"]:
            if entry["Exception"]:
                if fault_pc is None:
                    fail("EXCEPTION", idx, "ActiveList contains exception-marked entry with no sequential fault")
                if entry["PC"] < fault_pc:
                    fail("EXCEPTION", idx, "ActiveList exception entry PC is older than sequential fault PC")
                if entry["PC"] == fault_pc:
                    saw_fault_entry = True

    for idx in range(len(trace) - 1):
        cur = trace[idx]
        nxt = trace[idx + 1]

        if cur["PC"] != 0x10000 and nxt["PC"] != 0x10000:
            if nxt["PC"] < cur["PC"]:
                fail("PC", idx + 1, f"PC decreased from {cur['PC']} to {nxt['PC']}")
            if nxt["PC"] - cur["PC"] > 4:
                fail("PC", idx + 1, f"PC advanced by more than fetch width: {cur['PC']} -> {nxt['PC']}")

        if cur["Exception"] and nxt["Exception"]:
            cur_len = len(cur["ActiveList"])
            nxt_len = len(nxt["ActiveList"])
            if nxt_len > cur_len:
                fail("RECOVER", idx + 1, "ActiveList grew while recovering from exception")
            if cur_len - nxt_len > 4:
                fail("RECOVER", idx + 1, "Exception recovery removed more than 4 entries in one cycle")

    if fault_pc is not None and not saw_exception:
        raise CheckerError("[MICRO][EXCEPTION] expected an exception but trace never entered exception mode")

    if fault_pc is not None and not saw_fault_entry:
        raise CheckerError("[MICRO][EXCEPTION] oldest sequential fault was never marked in ActiveList")

    last = trace[-1]
    if fault_pc is None and last["Exception"]:
        raise CheckerError("[MICRO][FINAL] trace ended with Exception=true for non-faulting program")

    if fault_pc is not None:
        if last["Exception"]:
            raise CheckerError("[MICRO][FINAL] trace ended while still in exception recovery")
        if last["ActiveList"]:
            raise CheckerError("[MICRO][FINAL] ActiveList not empty after exception recovery")

    if last["PC"] != 0x10000 and last["PC"] < n_inst and (last["ActiveList"] or last["DecodedPCs"]):
        raise CheckerError("[MICRO][FINAL] trace appears truncated before quiescence")


def main() -> int:
    parser = argparse.ArgumentParser(description="Cycle-strict microarchitecture trace checker")
    parser.add_argument("input", help="Path to input instruction JSON")
    parser.add_argument("trace", help="Path to produced trace JSON")
    args = parser.parse_args()

    with open(args.input, "r", encoding="utf-8") as f:
        program = json.load(f)
    with open(args.trace, "r", encoding="utf-8") as f:
        trace = json.load(f)

    if type(program) is not list or not all(type(x) is str for x in program):
        raise CheckerError("[MICRO][INPUT] input program must be a JSON list of instruction strings")
    if type(trace) is not list or not trace:
        raise CheckerError("[MICRO][TRACE] trace must be a non-empty JSON list")

    _, fault_pc = simulate_sequential(program)
    n_inst = len(program)

    for cycle_idx, cycle in enumerate(trace):
        if type(cycle) is not dict:
            fail("TYPE", cycle_idx, "cycle entry is not an object")
        validate_cycle_schema(cycle_idx, cycle, n_inst)

    validate_cross_cycle(trace, fault_pc, n_inst)

    print("MICRO_CHECKER_PASSED")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except CheckerError as exc:
        print(str(exc))
        raise SystemExit(1)
