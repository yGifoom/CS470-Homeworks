def parse(i: str) -> dict:
    info = i.split()
    info[0] = info[0].strip()

    operands: list[str] = []

    for item in info[1:]:
        item = item.strip()
        if item.endswith(","):
            operands.append(item[:-1].strip())
        else:
            operands.append(item.strip())

    # 1 operand for jump, 2 for mov, load/store 3 for rest
    return {"opcode": info[0].strip(), "operands": operands}


class Instructions:
    def __init__(self, instructions: list[str]) -> None:
        # how many instructions of each type
        self.Ni = {"alu": 0, "mul": 0, "mem": 0, "branch": 0}

        # how many functional units of each type
        self.Ui = {"alu": 2, "mul": 1, "mem": 1, "branch": 1}
        self.bbs = [
            0
        ]  # basic block end pc indices # after init bbs is either [0, final_pc] or [0, loop_jump, loop_pc, final_pc]
        self.instructions = list()

        pc = 0
        for i in instructions:
            if type(i) != str:
                raise ValueError("Instructions must be a list of strings.")

            info = parse(i)  # opcode, operands

            # nop is irrelevant for schedule
            if info["opcode"] == "nop":
                continue

            instr = self.separate_rename_ops(info)
            if instr["type"] == "branch":
                assert instr["branch"] < pc, (
                    "Branch target must be a previous instruction."
                )
                self.bbs.extend([instr["branch"], pc])  # (label, pc)

            self.instructions.append(
                instr
            )  # opcode, type, dest, ops, imm, branch, lc_ec, pred_reg
            pc += 1

        self.bbs.append(pc)

    def separate_rename_ops(self, info: dict) -> dict:

        regs = [int(op[1:]) for op in info["operands"] if op.startswith("x")]

        non_regs = [op for op in info["operands"] if not op.startswith("x")]

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

            return {
                "opcode": info["opcode"],
                "type": "alu",
                "dest": dest,
                "ops": regs[1:],
                "imm": int(imm, 0) if imm is not None else None,
                "branch": None,
                "lc_ec": lc_ec,
                "pred_reg": pred_reg,
            }

        elif info["opcode"] in ("mulu"):
            self.Ni["mul"] += 1

            return {
                "opcode": info["opcode"],
                "type": "mul",
                "dest": regs[0],
                "ops": regs[1:],
                "imm": None,
                "branch": None,
                "lc_ec": None,
                "pred_reg": None,
            }

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

            ops = [mem_reg] if info["opcode"] == "ld" else [mem_reg] + regs
            dest = regs[0] if info["opcode"] == "ld" else None

            return {
                "opcode": info["opcode"],
                "type": "mem",
                "dest": dest,
                "ops": list(map(int, ops)),
                "imm": int(imm, 0) if imm is not None else None,
                "branch": None,
                "lc_ec": None,
                "pred_reg": None,
            }

        elif info["opcode"] in ("loop", "loop.pip"):
            self.Ni["branch"] += 1

            return {
                "opcode": info["opcode"],
                "type": "branch",
                "dest": None,
                "ops": list(),
                "imm": None,
                "branch": int(non_regs[0], 0),
                "lc_ec": None,
                "pred_reg": None,
            }
        else:
            raise ValueError(f"Unsupported opcode: {info['opcode']}")


if __name__ == "__main__":
    import json

    # testing
    with open(
        "/home/ygifoom/epfl/aa/CS470-Homeworks/HW2/given_tests/09/input.json", "r"
    ) as f:
        instrs = Instructions(json.load(f))

    for instr in instrs.instructions:
        print(instr)

    print("number of instr", instrs.bbs)
