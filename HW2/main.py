import src.simulator.vliw470 as vl
import argparse
import json
import os

from math import ceil

from src.instructions import InputInstructions
from src.dep_table import DepTable

parser = argparse.ArgumentParser()

parser.add_argument("input", type=argparse.FileType("r"), help="input json file")

parser.add_argument("output", action="store", help="The scheduled intructions.")

parser.add_argument(
    "-d", "--debug", action="store_true", help="print debug information"
)
args = parser.parse_args()

# prepare output file names
output = args.output
output_pip = args.output[: args.output.find(".")] + "_pip" + ".json"

# check if output files path exists
for filename in (output, output_pip):
    if filename.find("/") != -1:
        path = filename[: filename.rfind("/")]
        if not os.path.exists(path):
            os.makedirs(path)
            print(f"Created directory: {path}")


# debug print function
def print_debug(s: str = ""):
    if args.debug:
        print(s)


if __name__ == "__main__":
    # 0 load and parse input instructions
    input_instructions: InputInstructions = InputInstructions(json.load(args.input))

    # 1 make schedule
    schedule = list()
    schedule_pip = list()

    # 1.1 lowerbound II
    II = max(
        [
            ceil(input_instructions.Ni[stage] / input_instructions.Ui[stage])
            for stage in input_instructions.Ni.keys()
        ]
    )

    # 1.2 make dependency table
    dep_table = DepTable(input_instructions)

    # TODO: 1.x3 pip scheduling
    # 1.3 increase II until schedulable

    # 1.4 dispatch to registers

    # TODO: 1.x4 pip dispatch

    # 1.x5 pip loop preparing

    # 2 save schedules to output file
    for filename in (output, output_pip):
        with open(filename, "w") as out:
            json.dump(schedule, out, indent=4)

    pass
