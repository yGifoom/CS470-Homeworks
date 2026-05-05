from dataclasses import dataclass


def parse(i: str) -> dict:
    info = i.split()
    opcode = info[0].strip()

    operands: list[str] = []

    for item in info[1:]:
        item = item.strip()
        if item.endswith(","):
            operands.append(item[:-1].strip())
        else:
            operands.append(item.strip())

    # 1 operand for jump, 2 for mov, load/store 3 for rest
    return {"opcode": opcode, "operands": operands}


@dataclass
class Instruction:
    original_pc: int
    opcode: str
    type: str
    dest: int | None
    ops: list[int]
    imm: None | int
    branch: None | int
    lc_ec: None | str
    pred_reg: None | str
    # If this instruction starts executing on pc `n`, it's result will
    # be available on `n + latency`
    latency: int
    # The position in the new schedule
    new_pc: int = -1
    # in which execution unit are we
    bundle_idx: int = -1

    def to_string(self) -> str:
        """The instrucion string in the new schedule (the output)"""
        if  self.opcode == "nop":
            return " " + "nop"
        
        elif self.opcode in ("add", "sub", "mulu"):
            return " " + self.opcode + " x" + str(self.dest) + ", " + ", ".join(
                ["x" + str(op) for op in self.ops]
            )
            
        elif self.opcode in ("addi"):
            if self.imm is not None:
                return " " + self.opcode + " x" + str(self.dest) + ", x" + str(self.ops[0]) + ", " + str(self.imm)
            raise ValueError("Immediate value must be provided for addi instructions.")
        
        elif self.opcode in ("mov"):
            if self.imm is not None and self.pred_reg is not None:
                return " " + self.opcode + " " + self.pred_reg + ", " + str(self.imm)
            
            elif self.imm is not None and self.lc_ec is not None:
                return " " + self.opcode + " " + self.lc_ec + ", " + str(self.imm)
            
            elif self.dest is not None and len(self.ops) == 1:
                return " " + self.opcode + " x" + str(self.dest) + ", x" + str(self.ops[0])
            
            elif self.dest is not None and self.imm is not None:
                return " " + self.opcode + " x" + str(self.dest) + ", " + str(self.imm)
            
            raise ValueError("Invalid mov instruction format.")
        
        elif self.opcode in ("ld"):
            if self.imm is not None:
                mem_str = str(self.imm) + "(x" + str(self.ops[0]) + ")"
                return " " + self.opcode + " x" + str(self.dest) + ", " + mem_str
            raise ValueError("Invalid load instruction format.")
            
        elif self.opcode in ("st"):
            if self.imm is not None:
                mem_str = str(self.imm) + "(x" + str(self.ops[1]) + ")"
                return " " + self.opcode + " x" + str(self.ops[0]) + ", " + mem_str
            raise ValueError("Invalid store instruction format.")
        
        elif self.opcode in ("loop", "loop.pip"):
            if self.branch is not None:
                return " " + self.opcode + " " + str(self.branch)
            raise ValueError("Branch target must be provided for loop instructions.")
        else:
            raise ValueError("Unknown opcode.")
        

def get_nop() -> Instruction:
    return Instruction(
        original_pc=-1,
        opcode="nop",
        type="??",
        dest=None,
        ops=[],
        imm=None,
        branch=None,
        lc_ec=None,
        pred_reg=None,
        latency=1,
    )

class InputInstructions:
    def __init__(self, instructions: list[str]) -> None:
        # how many instructions of each type
        self.Ni = {"alu": 0, "mul": 0, "mem": 0, "branch": 0}

        # how many functional units of each type
        self.Ui = {"alu": 2, "mul": 1, "mem": 1, "branch": 1}
        # basic block end pc indices
        # after init bbs is either [0, final_pc] or [0, loop_jump, loop_pc, final_pc]
        self.bbs: list[int] = [0]
        self.instructions: list[Instruction] = []

        pc: int = 0
        for i in instructions:
            if not isinstance(i, str):
                raise ValueError("Instructions must be a list of strings.")

            info = parse(i)  # opcode, operands

            # nop is irrelevant for schedule
            if info["opcode"] == "nop":
                continue

            instr: Instruction = self.separate_rename_ops(info, pc=pc)
            if instr.type == "branch":
                assert instr.branch is not None
                assert instr.branch < pc, (
                    "Branch target must be a previous instruction."
                )
                self.bbs.extend([instr.branch, pc])  # (label, pc)

            self.instructions.append(
                instr
            )  # opcode, type, dest, ops, imm, branch, lc_ec, pred_reg
            pc += 1

        self.bbs.append(pc)

    def separate_rename_ops(self, info: dict, pc: int) -> Instruction:
        regs: list[int] = [int(op[1:]) for op in info["operands"] if op.startswith("x")]

        non_regs: list[str] = [op for op in info["operands"] if not op.startswith("x")]

        if info["opcode"] in ("add", "addi", "sub", "mov"):
            self.Ni["alu"] += 1

            if len(non_regs) == 2:  # instruction is mov LC/EC, imm or predicate setting
                if non_regs[0].startswith("p"):  # instruction is pred
                    imm = non_regs[1]
                    dest = None
                    lc_ec = None
                    pred_reg = non_regs[0]
                else:
                    imm = non_regs[1]
                    dest = None
                    lc_ec = non_regs[0]
                    pred_reg = None

            elif len(non_regs) == 1:  # instruction is addi, dest is first reg
                imm = non_regs[0]
                dest = regs[0]
                lc_ec = None
                pred_reg = None

            else:
                imm = None
                dest = regs[0]
                lc_ec = None
                pred_reg = None

            return Instruction(
                original_pc=pc,
                opcode=info["opcode"],
                type="alu",
                dest=dest,
                ops=regs[1:],
                imm=int(imm, 0) if imm is not None else None,
                branch=None,
                lc_ec=lc_ec,
                pred_reg=pred_reg,
                latency=1,
            )

        elif info["opcode"] in ("mulu"):
            self.Ni["mul"] += 1

            return Instruction(
                original_pc=pc,
                opcode=info["opcode"],
                type="mul",
                dest=regs[0],
                ops=regs[1:],
                imm=None,
                branch=None,
                lc_ec=None,
                pred_reg=None,
                # The only exception!
                latency=3,
            )

        elif info["opcode"] in ("ld", "st"):
            self.Ni["mem"] += 1

            # mem instructions are: mem reg, imm(reg)
            imm, mem_reg = (
                (non_regs[0].split("(")[0], non_regs[0].split("(")[1][:-1][1:])
                if "(" in non_regs[0]
                else (None, None)
            )

            assert imm is not None, (
                "Memory address must be provided for load/store instructions."
            )
            assert mem_reg is not None, (
                "Memory address must be provided for load/store instructions."
            )

            ops = [mem_reg] if info["opcode"] == "ld" else regs + [int(mem_reg)]
            dest = regs[0] if info["opcode"] == "ld" else None

            return Instruction(
                original_pc=pc,
                opcode=info["opcode"],
                type="mem",
                dest=dest,
                ops=list(map(int, ops)),
                imm=int(imm, 0) if imm is not None else None,
                branch=None,
                lc_ec=None,
                pred_reg=None,
                latency=1,
            )

        elif info["opcode"] in ("loop", "loop.pip"):
            self.Ni["branch"] += 1

            return Instruction(
                original_pc=pc,
                opcode=info["opcode"],
                type="branch",
                dest=None,
                ops=list(),
                imm=None,
                branch=int(non_regs[0], 0),
                lc_ec=None,
                pred_reg=None,
                latency=1
            )

        else:
            raise ValueError(f"Unsupported opcode: {info['opcode']}")


if __name__ == "__main__":
    import json

    # testing
    with open(
        "/home/ygifoom/epfl/aa/CS470-Homeworks/HW2/given_tests/09/input.json", "r"
    ) as f:
        instrs = InputInstructions(json.load(f))

    for instr in instrs.instructions:
        print(instr)

    print("number of instr", instrs.bbs)
