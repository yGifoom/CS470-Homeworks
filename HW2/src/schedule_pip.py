from .instructions import InputInstructions
from .instructions import Instruction
from .instructions import get_nop
from .dep_table import DependancyTableRow
import copy


def put_instr_in_schedule(instr: Instruction, occupied_dict: dict[tuple[int, int], bool], new_pc: int):
    bundle_idx: int = -1

    while bundle_idx == -1:
        if instr.opcode in ("add", "addi", "sub", "mov"):
            # ALU 1
            if not occupied_dict.get((new_pc, 0), False):
                bundle_idx = 0
            # ALU 2
            elif not occupied_dict.get((new_pc, 1), False):
                bundle_idx = 1
        elif instr.opcode == "mulu":
            # Mult
            if not occupied_dict.get((new_pc, 2), False):
                bundle_idx = 2
        elif instr.opcode in ("ld", "st"):
            # Mem
            if not occupied_dict.get((new_pc, 3), False):
                bundle_idx = 3
        elif instr.opcode in ("loop", "loop.pip"):
            # Branch
            if not occupied_dict.get((new_pc, 4), False):
                bundle_idx = 4
        else:
            raise AssertionError("unknown opcode")

        if bundle_idx == -1:
            # no free slots in this bundle, go for the next one
            print("no free slots!")
            new_pc += 1
    
    occupied_dict[(new_pc, bundle_idx)] = True
    instr.new_pc = new_pc
    print(f"    saved to {new_pc}, {bundle_idx}")
    instr.bundle_idx = bundle_idx

def attempt_pip_schedule(
    input_instructions: InputInstructions,
    dep_table: list[DependancyTableRow],
    ii_attempt: int,
) -> tuple[
    list[tuple[Instruction, Instruction, Instruction, Instruction, Instruction]], bool
]:
    """
    Returns (schedule, True) if we managed to make a schedule with the given II.
    """
    print(f"\n==> attempt pip schedule (ii: {ii_attempt}) <==\n")

    instructions: list[Instruction] = input_instructions.instructions
    # REMINDER: [bbs[0], bbs[1]) is the pre-loop bb, [bbs[1], bbs[2]] is the loop bb,
    #           [bbs[2] + 1, bbs[3]) is the post-loop bb
    bbs: list[int] = input_instructions.bbs
    print(f"bbs: {bbs}")

    # if in the schedule (pc, executinon unit index) is occupied
    occupied_dict: dict[tuple[int, int], bool] = {}
    # `S` as described in section 3.2.2.
    stage_occupied_dict: dict[tuple[int, int, int], bool] = {}

    # The output format is going to be what is described in the picture in
    # Figure 11 b).

    # The initiation interval is the size of a stage. When you occupy something in a stage,
    # it is occupied in all stages.

    # First, schedule all pre-loop instructions (BB0)
    assert 0 == bbs[0]
    print("> BB0")
    for i in range(0, bbs[1]):
        instr: Instruction = instructions[i]
        deps: DependancyTableRow = dep_table[i]
        assert deps.instr == i

        print(f"== processing instr {i}, {instr.to_string()} ==")

        new_pc: int = 0

        # We can only encounter local dependencies and (maybe? loop invariant dependencies) here.
        
        for _, depped_instr_idx in deps.local_dep:
            # `instr` uses operand `_`, which is produced by instruction at index `depped_instr_idx`
            depped_instr: Instruction = instructions[depped_instr_idx]
            new_pc = max(new_pc, depped_instr.new_pc + depped_instr.latency)

        for _, depped_instr_idx in deps.loop_invariant_dep:
            depped_instr: Instruction = instructions[depped_instr_idx]
            new_pc = max(new_pc, depped_instr.new_pc + depped_instr.latency)

        put_instr_in_schedule(instr, occupied_dict, new_pc)

    # Calculate the earliest the loop body can start, is one instruction after the last
    # instruction in BB0.
    loop_start_pc: int = 0
    for i in range(0, bbs[1]):
        loop_start_pc = max(loop_start_pc, instructions[i].new_pc)
    loop_start_pc += 1

    # The loop instruction is at `ii_attempt` + (first instruction in loop body) - 1 and
    # will in practice be executed for every stage, but will not be there at the end of
    # BB1 in the output format (unless we only have 1 stage).

    # Schedule BB1 instructions.
    # We don't handle the loop instruction in here
    print("> BB1")
    for i in range(bbs[1], bbs[2]):
        instr: Instruction = instructions[i]
        deps: DependancyTableRow = dep_table[i]
        assert deps.instr == i

        print(f"== processing instr {i}, {instr.to_string()} ==")

        new_pc: int = loop_start_pc

        for _, depped_instr_idx in deps.local_dep:
            # Producer is instruction before us in BB1, simple.
            depped_instr: Instruction = instructions[depped_instr_idx]
            new_pc = max(new_pc, depped_instr.new_pc + depped_instr.latency)

        for _, depped_instr_idx in deps.loop_invariant_dep:
            # Producer is instruction in BB0, simple.
            depped_instr: Instruction = instructions[depped_instr_idx]
            new_pc = max(new_pc, depped_instr.new_pc + depped_instr.latency)

        for _, depped_instr_idx in deps.interloop_dep:
            # Interloop dependency means the producer is either in BB0 or in
            # the previous iteration of BB1 (possibly after us in the body).
            # Here we check only the former case, and the latter we check after
            # everything has been scheduled.

            if depped_instr_idx < bbs[1]:
                depped_instr: Instruction = instructions[depped_instr_idx]
                new_pc = max(new_pc, depped_instr.new_pc + depped_instr.latency)

        # BB1 instructions don't have post loop dependencies.

        put_instr_in_schedule(instr, occupied_dict, new_pc)

    # Now we schedule the `loop` instruction.
    # 1. Find the loop instruction.
    loop_instr: Instruction | None = None
    for instr in instructions:
        if instr.branch is not None:
            assert loop_instr is None, "multiple loops?"
            loop_instr = instr

    if loop_instr is not None:
        # We do indeed have a loop.
        
        # 2. Fix its target
        assert loop_instr.branch is not None
        loop_instr.branch = instructions[loop_instr.branch].new_pc

        # 3. Move it to the appropriate place using the II
        loop_place = loop_instr.branch + ii_attempt - 1
        put_instr_in_schedule(loop_instr, occupied_dict, loop_place)

        # Start of BB2 must be after the loop instruction
        epilog_start: int = loop_instr.new_pc + 1

        # Schedule BB2 instructions
        assert len(instructions) == bbs[3]
        print("> BB2")
        for i in range(bbs[2] + 1, bbs[3]):
            instr: Instruction = instructions[i]
            deps: DependancyTableRow = dep_table[i]
            assert deps.instr == i

            print(f"== processing instr {i}, {instr.to_string()} ==")

            new_pc: int = epilog_start

            # We don't have inter-loop deps here.

            for _, depped_instr_idx in deps.local_dep:
                depped_instr: Instruction = instructions[depped_instr_idx]
                new_pc = max(new_pc, depped_instr.new_pc + depped_instr.latency)

            for _, depped_instr_idx in deps.loop_invariant_dep:
                depped_instr: Instruction = instructions[depped_instr_idx]
                new_pc = max(new_pc, depped_instr.new_pc + depped_instr.latency)

            for _, depped_instr_idx in deps.post_loop_dep:
                depped_instr: Instruction = instructions[depped_instr_idx]
                new_pc = max(new_pc, depped_instr.new_pc + depped_instr.latency)

            put_instr_in_schedule(instr, occupied_dict, new_pc)

        # We need to check that the loop instruction is not before the last instruction
        # of the loop body since we don't think about this when selecting the initiation interval.
        for i in range(bbs[2]):
            if instructions[i].new_pc > loop_instr.new_pc:
                return [], False 

    # Now we check equation 2, i.e. if all inter-loop deps are valid.
    for i in range(len(instructions)):
        for _, depped_instr_idx in dep_table[i].interloop_dep:
            depped_instr: Instruction = instructions[depped_instr_idx]
            if depped_instr.new_pc + depped_instr.latency > instructions[i].new_pc + ii_attempt:
                return [], False
            
    # Okay, we have a working schedule, let's transform it into the appropriate datastructure.
    highest_pc: int = -1
    for instr in instructions:
        highest_pc = max(highest_pc, instr.new_pc)

    print("==== normal schedule decision ====")
    for instr in instructions:
        print("instr: ", instr.to_string(), " @ ", instr.new_pc, instr.bundle_idx)
    print("==== ======================== ====")

    schedule: list[tuple[Instruction, Instruction, Instruction, Instruction, Instruction]] = []
    for i in range(highest_pc + 1):
        nop = get_nop()
        nop.new_pc = i

        sched_row = [nop, nop, nop, nop, nop]

        # Iterate over all instr's to see if one fits here
        for instr in instructions:
            if instr.new_pc == i:
                sched_row[instr.bundle_idx] = instr

        schedule.append(tuple(sched_row)) # type: ignore

    return schedule, True


def pip_schedule(
    input_instructions: InputInstructions,
    dep_table: list[DependancyTableRow],
    initial_ii: int,
) -> list[tuple[Instruction, Instruction, Instruction, Instruction, Instruction]]:
    ok: bool = False
    schedule = []
    ii: int = initial_ii
    while not ok:
        instr_copy = copy.deepcopy(input_instructions)
        schedule, ok = attempt_pip_schedule(instr_copy, dep_table, ii)
        ii += 1

    return schedule
