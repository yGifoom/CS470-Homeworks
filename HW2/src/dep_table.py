from dataclasses import dataclass
from instructions import InputInstructions
from instructions import Instruction
from pathlib import Path


@dataclass
class DependancyTable:
    instr: int
    dest: int | None
    local_dep: list[tuple[int, int]]
    interloop_dep: list[tuple[int, int]]
    loop_invariant_dep: list[tuple[int, int]]
    post_loop_dep: list[tuple[int, int]]


class DepTable:
    def __init__(self, instructions: InputInstructions):
        self.instructions_list: InputInstructions = instructions
        self.table = self.build_dep_table()

    def build_dep_table(self):
        bbs: list[int] = self.instructions_list.bbs
        inst: list[Instruction] = self.instructions_list.instructions
        table: list[DependancyTable] = []

        producers: dict[
            int, list[int]
        ] = {}  # reg -> list of instr indices that produce it

        # bb end pc index
        # REMINDER: [bbs[0], bbs[1]) is the pre-loop bb, [bbs[1], bbs[2]) is the loop bb, [bbs[2], bbs[3]) is the post-loop bb
        bb = 1

        for i in range(len(inst)):
            inst_dest = inst[i].dest
            if inst_dest is not None:
                if inst_dest in producers:
                    producers[inst_dest] = producers[inst_dest] + [i]
                else:
                    producers[inst_dest] = [i]

        for i in range(bbs[-1]):  # i is instr index
            if i > bbs[bb] - 1:  # if last instruction of the bb, move to next bb
                bb += 1
                if bb >= len(bbs):
                    bb -= 1  # ugly I know, also i do not care!

            # producer consumer same bb, producer before consumer
            local_dep: list[tuple[int, int]] = []
            # consumer in loop, producer in different bb (if same loop bb after consumer becomes loop carried)
            interloop_dep: list[tuple[int, int]] = []
            # producer in pre-loop bb, consumer in loop, post loop bb, no other producer in loop
            loop_invariant_dep: list[tuple[int, int]] = []
            # producer in loop, consumer in post-loop bb
            post_loop_dep: list[tuple[int, int]] = []

            for op in inst[i].ops:
                print(bb, i)
                local_dep.extend(
                    [
                        (op, k)
                        for k in producers.get(op, list())
                        if (k < bbs[bb] and k >= bbs[bb - 1] and k < i)
                    ]
                )

                if bb > 1:
                    latest_producer_of_op = max(
                        [k for k in producers.get(op, list()) if k < bbs[2]]
                    )
                    print("latest producer of op ", op, " is ", latest_producer_of_op)
                    if latest_producer_of_op < bbs[1]:
                        loop_invariant_dep.append((op, latest_producer_of_op))

                if (
                    bb == 2
                ):  # if this is not the first bb, also check for loop-carried deps
                    for k in producers.get(op, list()):
                        if (k >= i and k < bbs[2]) or (k < bbs[1]):
                            if (
                                (op, k) not in loop_invariant_dep
                            ):  # give pecedence to loop invariant deps
                                interloop_dep.append((op, k))

                if (
                    bb == 3
                ):  # if this is not the first two bbs, also check for post-loop deps
                    # pick the latest dependencies
                    latest_dep = max(
                        [k for k in producers.get(op, list()) if k < bbs[2]]
                    )
                    post_loop_dep.append((op, latest_dep))

            table.append(
                DependancyTable(
                    instr=i,
                    dest=inst[i].dest,
                    local_dep=local_dep,
                    interloop_dep=interloop_dep,
                    loop_invariant_dep=loop_invariant_dep,
                    post_loop_dep=post_loop_dep,
                )
            )

        return table


if __name__ == "__main__":
    from instructions import InputInstructions
    import json

    with open(
       Path.home() /  "epfl/aa/CS470-Homeworks/HW2/given_tests/00/input.json", "r"
    ) as f:
        instrs = InputInstructions(json.load(f))

    print("bbs are: ", instrs.bbs)

    dep_table = DepTable(instrs)

    for entry in dep_table.table:
        print(entry)
