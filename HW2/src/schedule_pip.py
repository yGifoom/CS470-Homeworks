from .instructions import InputInstructions
from .instructions import Instruction
from .instructions import get_nop
from .dep_table import DependancyTableRow
import copy


def check_has_space_bundle(stage_occupied_dict: dict[tuple[int, int, int], bool], bundle_idx: int, ii: int) -> bool:
    for instage_idx in range(ii):
        for stage in range(1000):
            is_full: bool = stage_occupied_dict.get((stage, instage_idx, bundle_idx), False)
            if not is_full:
                return True
    return False

def check_has_space(opcode: str, stage_occupied_dict: dict[tuple[int, int, int], bool], ii: int) -> bool:
    if opcode in ("add", "addi", "sub", "mov"):
        # ALU 1 or ALU 2
        return check_has_space_bundle(stage_occupied_dict, 0, ii) or check_has_space_bundle(stage_occupied_dict, 1, ii)
    elif opcode == "mulu":
        # Mult
        return check_has_space_bundle(stage_occupied_dict, 2, ii)
    elif opcode in ("ld", "st"):
        # Mem
        return check_has_space_bundle(stage_occupied_dict, 3, ii)
    elif opcode in ("loop", "loop.pip"):
        # Branch
        return check_has_space_bundle(stage_occupied_dict, 4, ii)
    else:
        raise AssertionError("unknown opcode")
    

def is_full_slot(stage_occupied_dict: dict[tuple[int, int, int], bool], new_pc: int, bundle_idx: int, loop_start_pc: int, ii: int) -> bool:
    """Returns True if the slot is already occupied, otherwise False"""
    # We pass in new_pc and convert to stage index.
    instage_idx: int = (new_pc - loop_start_pc) % ii
    # Arbitrarily big number.
    for i in range(1000):
        if stage_occupied_dict.get((i, instage_idx, bundle_idx), False):
            return True
    return False

def set_slot_as_full(stage_occupied_dict: dict[tuple[int, int, int], bool], new_pc: int, bundle_idx: int, loop_start_pc: int, ii: int) -> None:
    # FIXME: i'm kinda ignoring the bubbling problem and calculating stages this way
    instage_idx: int = (new_pc - loop_start_pc) % ii
    stage: int = (new_pc - loop_start_pc) // ii
    stage_occupied_dict[(stage, instage_idx, bundle_idx)] = True

def put_instr_in_pip_schedule(
    instr: Instruction,
    new_pc: int,
    occupied_dict: dict[tuple[int, int], bool],
    stage_occupied_dict: dict[tuple[int, int, int], bool],
    loop_start_pc: int,
    ii: int
) -> bool:
    """
    Puts instruction into the BB1 for the schedule.

    Returns False if you couldn't fit the instruction anywhere.
    """
    bundle_idx: int = -1

    if not check_has_space(instr.opcode, stage_occupied_dict, ii):
        return False

    while bundle_idx == -1:
        if instr.opcode in ("add", "addi", "sub", "mov"):
            # ALU 1
            if not occupied_dict.get((new_pc, 1), False) and not is_full_slot(stage_occupied_dict, new_pc, 0, loop_start_pc, ii):
                bundle_idx = 0
            # ALU 2
            elif not occupied_dict.get((new_pc, 1), False) and not is_full_slot(stage_occupied_dict, new_pc, 1, loop_start_pc, ii):
                bundle_idx = 1
        elif instr.opcode == "mulu":
            # Mult
            if not occupied_dict.get((new_pc, 2), False) and not is_full_slot(stage_occupied_dict, new_pc, 2, loop_start_pc, ii):
                bundle_idx = 2
        elif instr.opcode in ("ld", "st"):
            # Mem
            if not occupied_dict.get((new_pc, 3), False) and not is_full_slot(stage_occupied_dict, new_pc, 3, loop_start_pc, ii):
                bundle_idx = 3
        elif instr.opcode in ("loop", "loop.pip"):
            # Branch
            if not occupied_dict.get((new_pc, 4), False) and not is_full_slot(stage_occupied_dict, new_pc, 4, loop_start_pc, ii):
                bundle_idx = 4
        else:
            raise AssertionError("unknown opcode")

        if bundle_idx == -1:
            # no free slots in this bundle, go for the next one
            print("no free slots!")
            new_pc += 1
    
    # FIXME: i'm kinda ignoring the bubbling problem and calculating stages this way
    set_slot_as_full(stage_occupied_dict, new_pc, bundle_idx, loop_start_pc, ii)
    
    occupied_dict[(new_pc, bundle_idx)] = True
    instr.new_pc = new_pc
    instr.bundle_idx = bundle_idx

    print(f"    saved to {new_pc}, {bundle_idx}")

    return True

def put_instr_in_schedule(
    instr: Instruction, occupied_dict: dict[tuple[int, int], bool], new_pc: int
) -> None:
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
    # [stage, instage_idx (% ii), execution unit (bundle idx)]
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

    if len(bbs) > 2:
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

            ok = put_instr_in_pip_schedule(instr, new_pc, occupied_dict, stage_occupied_dict, loop_start_pc, ii_attempt)
            # Couldn't fit it in.
            if not ok:
                return [], False

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
            # The loop will always fit because it's the only branching instruction
            put_instr_in_schedule(loop_instr, occupied_dict, loop_place)

            # Start of BB2 must be after the end of the stage that the last instruction is in
            highest_stage: int = 0
            for x, _, _ in stage_occupied_dict:
                highest_stage = max(highest_stage, x)
        
            epilog_start: int = loop_start_pc + (highest_stage + 1) * ii_attempt

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

            # We don't check that instructions are after loop, because we make as many stages
            # as we need.

        # Now we check equation 2, i.e. if all inter-loop deps are valid.
        for i in range(len(instructions)):
            for _, depped_instr_idx in dep_table[i].interloop_dep:
                depped_instr: Instruction = instructions[depped_instr_idx]
                if (
                    depped_instr.new_pc + depped_instr.latency
                    > instructions[i].new_pc + ii_attempt
                ):
                    return [], False

    # Okay, we have a working schedule, let's transform it into the appropriate datastructure.
    highest_pc: int = -1
    for instr in instructions:
        highest_pc = max(highest_pc, instr.new_pc)

    print("==== pip schedule decision ====")
    for instr in instructions:
        print("instr: ", instr.to_string(), " @ ", instr.new_pc, instr.bundle_idx)
    print("==== ======================== ====")

    schedule: list[
        tuple[Instruction, Instruction, Instruction, Instruction, Instruction]
    ] = []
    for i in range(highest_pc + 1):
        nop = get_nop()
        nop.new_pc = i

        sched_row = [nop, nop, nop, nop, nop]

        # Iterate over all instr's to see if one fits here
        for instr in instructions:
            if instr.new_pc == i:
                sched_row[instr.bundle_idx] = instr

        schedule.append(tuple(sched_row))  # type: ignore

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
