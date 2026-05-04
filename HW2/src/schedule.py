from .instructions import InputInstructions
from .instructions import Instruction
from .instructions import get_nop
from .dep_table import DependancyTableRow


def attempt_normal_schedule(
    input_instructions: InputInstructions,
    dep_table: list[DependancyTableRow],
    ii_attempt: int,
) -> tuple[
    list[tuple[Instruction, Instruction, Instruction, Instruction, Instruction]], bool
]:
    """
    Returns (schedule, True) if we managed to make a schedule with the given II.
    """
    instructions: list[Instruction] = input_instructions.instructions

    # if in the schedule (pc, executinon unit index) is occupied
    occupied_dict: dict[tuple[int, int], bool] = {}

    for i in range(len(instructions)):
        instr: Instruction = instructions[i]
        deps: DependancyTableRow = dep_table[i]
        assert deps.instr == i

        print(f"processing instr {i}, {instr.to_string()}")

        new_pc: int = 0

        for _, depped_instr_idx in deps.local_dep:
            # `instr` uses operand `_`, which is produced by instruction at index `depped_instr_idx`
            depped_instr: Instruction = instructions[depped_instr_idx]
            new_pc = max(new_pc, depped_instr.new_pc + depped_instr.latency)

        for _, depped_instr_idx in deps.loop_invariant_dep:
            depped_instr: Instruction = instructions[depped_instr_idx]
            new_pc = max(new_pc, depped_instr.new_pc + depped_instr.latency)

        for _, depped_instr_idx in deps.post_loop_dep:
            depped_instr: Instruction = instructions[depped_instr_idx]
            new_pc = max(new_pc, depped_instr.new_pc + depped_instr.latency)

        for _, depped_instr_idx in deps.interloop_dep:
            # This is kinda confusing to me, but let's just try to do what the doc says directly
            depped_instr: Instruction = instructions[depped_instr_idx]
            if depped_instr.new_pc + depped_instr.latency > new_pc + ii_attempt:
                return [], False

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
                print("no free slost!")
                new_pc += 1
            
        occupied_dict[(new_pc, bundle_idx)] = True
        instr.new_pc = new_pc
        instr.bundle_idx = bundle_idx

    # There is the "Loop with Bubble." section, but I think we automatically handle this with our
    # representation.

    # Fix loop targets
    for instr in instructions:
        if instr.branch is not None:
            # Set the branch target to the new location of the instruction we were targetting b4
            instr.branch = instructions[instr.branch].new_pc

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


def normal_schedule(
    input_instructions: InputInstructions,
    dep_table: list[DependancyTableRow],
    initial_ii: int,
) -> list[tuple[Instruction, Instruction, Instruction, Instruction, Instruction]]:
    # == Section 3.2. & 3.2.1 Scheduling with the loop Instruction ==

    ok: bool = False
    schedule = []
    ii: int = initial_ii
    while not ok:
        schedule, ok = attempt_normal_schedule(input_instructions, dep_table, ii)
        ii += 1

    return schedule


def pip_schedule(
    input_instructions: InputInstructions,
    dep_table: list[DependancyTableRow],
    initial_ii: int,
) -> list[tuple[Instruction, Instruction, Instruction, Instruction, Instruction]]:
    return []
