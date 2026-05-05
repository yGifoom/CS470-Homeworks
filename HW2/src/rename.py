from .instructions import InputInstructions
from .instructions import Instruction
from .instructions import get_nop
from .dep_table import DependancyTableRow


def rename(
    dep_table: list[DependancyTableRow],
    input_instructions: InputInstructions,
    schedule: list[tuple[Instruction, Instruction, Instruction, Instruction, Instruction]]
) -> list[
    tuple[Instruction, Instruction, Instruction, Instruction, Instruction]
]:
    """
    Performs register renaming on the given schedule.
    """
    # == Section 3.3.1 Register Allocation with the loop Instruction ==
    # step 0: save all old destination and calculate mov instructions addresses
    jump_pc: int = input_instructions.bbs[1]  # pc of loop jump instruction
    mov_instr_pcs: list[tuple[int, int]] = []  # (bb1 producer pc,  bb0 producer pc)
    
    bb0_destinations: dict[int, int] = dict() # reg -> original_pc of instruction producing it in bb0
    for instr_tuple in schedule:
        for instr in instr_tuple:
            if instr.dest is None: continue
            
            if instr.original_pc < jump_pc: 
                bb0_destinations[instr.dest] = instr.original_pc
                
            elif instr.original_pc >= jump_pc and instr.dest in bb0_destinations.keys():
                mov_instr_pcs.append((instr.original_pc, bb0_destinations[instr.dest]))
    
    
    
    # step 1: assign to all destination regs a new value and populate a mov instructions with renamed regs
    used_regs: int = 1  # we start assigning from x1 because x0 is reserved for 0
    pc_to_new_dest: dict[int, int] = dict() # original_pc -> new dest reg
    
    # takes care of anti-dependencies and output dependencies
    for instr_tuple in schedule:
        for instr in instr_tuple:
            if instr.dest is not None:
                
                new_dest = used_regs
                pc_to_new_dest[instr.original_pc] = new_dest
                instr.dest = new_dest
                
                used_regs += 1
    
    #step 1.5: populate mov instructions with renamed regs
    movs = []
    for bb1_producer_pc, bb0_producer_pc in mov_instr_pcs:
        bb0_new_dest = pc_to_new_dest[bb0_producer_pc]
        bb1_new_dest = pc_to_new_dest[bb1_producer_pc]
        mov_instr = Instruction(
            original_pc=-1,
            opcode="mov",
            type="alu",
            dest=bb0_new_dest,
            ops=[bb1_new_dest], 
            imm=None,
            branch=None,
            lc_ec=None,
            pred_reg=None,
            latency=1,
        )
        movs.append(mov_instr)
                    
    
    # step 2 assign to op with dependencies the new value and assign to remaining op unused registers
    for instr_tuple in schedule:
        for instr in instr_tuple:
            if instr.original_pc == -1 or len(instr.ops) == 0:  # nop or no dependencies
                continue
            
            # list of (reg, producer original_pc) for all dependencies of this instruction
            instr_deps = dep_table[instr.original_pc].local_dep + \
                dep_table[instr.original_pc].interloop_dep + \
                dep_table[instr.original_pc].loop_invariant_dep + \
                dep_table[instr.original_pc].post_loop_dep
                
            # If the operand value comes from two different producers, one will be in BB1 and another one in BB0
            # always break tie by picking BB0 producer
            instr_deps = sorted(instr_deps, key=lambda x: x[1])  # sort by producer original_pc
            for i, op in enumerate(instr.ops):
                op_substituted = False # we use this variable in 2.2 to assign unused registers
                
                #2.1 find the first producer (in pc order) of that operand's register and substitute it
                for reg, producer_pc in instr_deps:
                    
                    new_destination = input_instructions.instructions[producer_pc].dest
                    if new_destination is not None: # for static typechecking
                        if reg == op:
                            instr.ops[i] = new_destination
                            op_substituted = True
                            break
                        
                #2.2 if operand is not substituted, assign an unused register to it
                if not op_substituted:
                    instr.ops[i] = used_regs
                    used_regs += 1
            
    # step 3: insert mov instructions for loop invariant values at the beginning of the loop
    if len(input_instructions.bbs) > 2:  # if there is a loop

        for i, instr_tuple in enumerate(schedule):
            if instr_tuple[4].opcode != "nop":
                loop_end = i
                break
        
        n_new_bundles = 0
        for i, mov_instr in enumerate(movs): # movs and mov_instr_pcs have mov operations in same order
            # calculate earliest bundle idx from producer in loop
            bb1_producer_pc = mov_instr_pcs[i][0]
            earliest_bundle  = input_instructions.instructions[bb1_producer_pc].new_pc + input_instructions.instructions[bb1_producer_pc].latency
            
            if earliest_bundle > loop_end + n_new_bundles: # extend the bb1 
                
                schedule.insert(earliest_bundle, (mov_instr, get_nop(), get_nop(), get_nop(), get_nop()))
                n_new_bundles += 1
                
            if earliest_bundle < loop_end + n_new_bundles: # can insert mov in current bb1 size, unless occupancy forces us to insert later
                earliest_bundle = loop_end + n_new_bundles

                print(f"inserting mov {mov_instr.to_string()} at earliest bundle {earliest_bundle}, depends on instr at pc {bb1_producer_pc} with new pc {input_instructions.instructions[bb1_producer_pc].new_pc}")

                if schedule[earliest_bundle][0].opcode == "nop":
                    schedule = insert_instr(earliest_bundle, 0, mov_instr, schedule)
                elif schedule[earliest_bundle][1].opcode == "nop":
                    schedule = insert_instr(earliest_bundle, 1, mov_instr, schedule)
                else: # have to insert new bundle and move loop instruction down
                    schedule.insert(earliest_bundle, (mov_instr, get_nop(), get_nop(), get_nop(), get_nop()))
                    n_new_bundles += 1
    
        # reposition the loop instruction so it is at the end of the last bundle of the loop 
        loop_instr = schedule[loop_end][4]
        schedule = insert_instr(loop_end + n_new_bundles, 4, loop_instr, schedule)
        schedule = insert_instr(loop_end, 4, get_nop(), schedule) # replace old loop instruction with nop
    
    return schedule

def insert_instr(bundle_idx: int, slot_idx: int, instr: Instruction, schedule: list[tuple[Instruction, Instruction, Instruction, Instruction, Instruction]]) -> list[
    tuple[Instruction, Instruction, Instruction, Instruction, Instruction]
]:
    """copies the bundle idx row and inserts at slot_idx the instruction instr

    Args:
        bundle_idx (int): bundle index where we want to insert the instruction
        slot_idx (int): slot in the bundle where we want to insert the instruction
        instr (Instruction): instruction to be inserted
        schedule (list[tuple[Instruction, Instruction, Instruction, Instruction, Instruction]]): _description_

    Returns:
        list[ tuple[Instruction, Instruction, Instruction, Instruction, Instruction] ]: _description_
    """
    new_bundle = list(schedule[bundle_idx])
    new_bundle[slot_idx] = instr
    schedule[bundle_idx] = tuple(new_bundle) #type: ignore
    return schedule

def rename_pip(schedule: list[tuple[Instruction, Instruction, Instruction, Instruction, Instruction]]) -> list[
    tuple[Instruction, Instruction, Instruction, Instruction, Instruction]
]:
    """
    Performs register renaming on the given pip schedule.
    """
    # TODO
    return schedule
