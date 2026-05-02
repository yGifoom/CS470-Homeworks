UINT64_MOD = 1 << 64


def _u64(value: int) -> int:
    return int(value) % UINT64_MOD


def _parse_instruction_fields(inst: str) -> tuple[str, int, int, int | None, int | None]:
    parts = inst.replace(",", "").replace("x", "").split()
    opcode = parts[0]
    v_dest = int(parts[1])
    src_a = int(parts[2])

    if opcode == "addi":
        imm = int(parts[3])
        return opcode, v_dest, src_a, None, imm

    src_b = int(parts[3])
    return opcode, v_dest, src_a, src_b, None


def _find_first_exception_index(instructions: list[str]) -> int | None:
    regs = [0] * 32

    for idx, inst in enumerate(instructions):
        opcode, v_dest, src_a, src_b, imm = _parse_instruction_fields(inst)
        a = regs[src_a]

        if opcode == "addi":
            res = _u64(a + int(imm))
        elif opcode == "add":
            res = _u64(a + regs[src_b])
        elif opcode == "sub":
            res = _u64(a - regs[src_b])
        elif opcode == "mulu":
            res = _u64(a * regs[src_b])
        elif opcode == "divu":
            b = regs[src_b]
            if b == 0:
                return idx
            res = _u64(a // b)
        elif opcode == "remu":
            b = regs[src_b]
            if b == 0:
                return idx
            res = _u64(a % b)
        else:
            continue

        regs[v_dest] = res

    return None


def _schedule_issue_and_retire_ready(instructions: list[str]) -> list[int]:
    n = len(instructions)
    if n == 0:
        return []

    reg_ready_cycle = [0] * 32
    arrival_cycle = [idx // 4 + 2 for idx in range(n)]
    retire_ready_cycle = [-1] * n

    pending: list[int] = []
    next_arrival_idx = 0
    issued_count = 0
    cycle = 0
    max_issue_cycles = max(8, 8 * n)

    while issued_count < n and cycle < max_issue_cycles:
        while next_arrival_idx < n and arrival_cycle[next_arrival_idx] <= cycle:
            pending.append(next_arrival_idx)
            next_arrival_idx += 1

        new_pending: list[int] = []
        issued_this_cycle = 0

        for idx in pending:
            if issued_this_cycle >= 4:
                new_pending.append(idx)
                continue

            _, v_dest, src_a, src_b, _ = _parse_instruction_fields(instructions[idx])
            ready_a = reg_ready_cycle[src_a] <= cycle
            ready_b = True if src_b is None else reg_ready_cycle[src_b] <= cycle

            if ready_a and ready_b:
                retire_ready_cycle[idx] = cycle + 3
                reg_ready_cycle[v_dest] = cycle + 2
                issued_this_cycle += 1
                issued_count += 1
            else:
                new_pending.append(idx)

        pending = new_pending
        cycle += 1

    return retire_ready_cycle


def _estimate_without_exception(instructions: list[str]) -> int:
    n = len(instructions)
    if n == 0:
        return 1

    retire_ready_cycle = _schedule_issue_and_retire_ready(instructions)

    head = 0
    commit_cycle = 0
    max_commit_cycles = max(8, 8 * n)

    while head < n and commit_cycle < max_commit_cycles:
        retired_this_cycle = 0
        while (
            retired_this_cycle < 4
            and head < n
            and retire_ready_cycle[head] != -1
            and retire_ready_cycle[head] <= commit_cycle
        ):
            head += 1
            retired_this_cycle += 1

        commit_cycle += 1

    return max(commit_cycle, 1)


def _estimate_with_exception(instructions: list[str], fault_idx: int) -> int:
    prefix = instructions[: fault_idx + 1]
    retire_ready_cycle = _schedule_issue_and_retire_ready(prefix)

    head = 0
    cycle = 0
    max_cycles = max(8, 8 * len(prefix))

    while cycle < max_cycles:
        retired_this_cycle = 0
        while (
            retired_this_cycle < 4
            and head < fault_idx
            and retire_ready_cycle[head] != -1
            and retire_ready_cycle[head] <= cycle
        ):
            head += 1
            retired_this_cycle += 1

        if (
            head == fault_idx
            and retire_ready_cycle[fault_idx] != -1
            and retire_ready_cycle[fault_idx] <= cycle
        ):
            break

        cycle += 1

    rollback_entries = min(32, len(instructions) - fault_idx)
    recovery_cycles = max(1, (rollback_entries + 3) // 4)

    return max(1, cycle + 1 + recovery_cycles)


def estimate_cycles_microarchitecture(instructions: list[str]) -> int:
    """
    Exception-aware idealized cycle estimator.

    Baseline model assumptions:
    - Fetch/rename/issue/commit width = 4.
    - Decoded instruction i can first reach Issue at cycle floor(i/4) + 2.
    - Operand forwarding makes a producer's result usable 2 cycles after issue.
    - Commit retires up to 4 in-order instructions per cycle, 3 cycles after issue.

    Exception patch:
    - If a divide-by-zero is detected in architectural program order, estimated cycles
      stop at fault recognition and include rollback recovery cycles.
    """
    if not instructions:
        return 1

    fault_idx = _find_first_exception_index(instructions)
    if fault_idx is None:
        return _estimate_without_exception(instructions)

    return _estimate_with_exception(instructions, fault_idx)
