import json
import sys

from math import ceil

from src.instructions import InputInstructions
from src.instructions import Instruction
from src.dep_table import build_dep_table
from src.dep_table import DependancyTableRow
from src.schedule import normal_schedule
from src.schedule_pip import pip_schedule
from src.rename import rename


def main() -> None:
    input_filename: str = sys.argv[1]
    output_filename: str = sys.argv[2]
    output_filename_pip: str = sys.argv[3]

    print(f"\n\n <========= TEST CASE {input_filename} =============>\n\n")
    
    with open(input_filename) as infile:
        input_data = infile.read()

    # Terminology:
    #   Bundle - one row in the schedule

    # 0 load and parse input instructions
    input_instructions: InputInstructions = InputInstructions(json.loads(input_data))

    # 1.1 lowerbound II
    II = max(max(
        [
            ceil(input_instructions.Ni[stage] / input_instructions.Ui[stage])
            for stage in input_instructions.Ni.keys()
        ]
    ) - 1, 1)

    # 1.2 make dependency table
    dep_table: list[DependancyTableRow] = build_dep_table(input_instructions)

    # == Section 3.2. & 3.2.1 Scheduling with the loop Instruction ==
    # Essentially we assume that we will solve WAR and WAW dependencies after this stage,
    # and only care about RAW dependencies.
    # We perform the scheduling simply now, knowing that register renaming will save us later.
    schedule: list[
        tuple[Instruction, Instruction, Instruction, Instruction, Instruction]
    ] = normal_schedule(input_instructions, dep_table, II)

    # == Section 3.2.2 Scheduling With loop.pip ==
    # TODO
    schedule_pip: list[
        tuple[Instruction, Instruction, Instruction, Instruction, Instruction]
    ] = pip_schedule(input_instructions, dep_table, II)

    # 3.3 Register Allocation
    # == Section 3.3.1 Register Allocation with the loop Instruction ==


    # TODO: 1.x3 pip scheduling
    # 1.3 increase II until schedulable

    # 1.4 dispatch to registers
    schedule = rename(dep_table, input_instructions, schedule)

    # TODO: 1.x4 pip dispatch

    # TODO: 1.x5 pip loop preparing

    # Save schedules to output file
    with open(output_filename, "w") as out:
        sched_str: list[tuple[str, str, str, str, str]] = []
        for row in schedule:
            sched_str.append((row[0].to_string(), row[1].to_string(), row[2].to_string(), row[3].to_string(), row[4].to_string()))
        json.dump(sched_str, out, indent=4)

    with open(output_filename_pip, "w") as out_pip:
        sched_str: list[tuple[str, str, str, str, str]] = []
        for row in schedule_pip:
            sched_str.append((row[0].to_string(), row[1].to_string(), row[2].to_string(), row[3].to_string(), row[4].to_string()))
        json.dump(sched_str, out_pip, indent=4)


if __name__ == "__main__":
    main()
