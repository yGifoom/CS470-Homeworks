from structs.stages.stage import Stage
import structs.micro_arc as m
import structs.stages as s
from structs.op import Op
from typing import Optional, cast


UINT64_MOD = 1 << 64

class Alu(Stage):
    copy: Optional["Alu"]
    
    def __init__(self):
        self.name = "alu"
        
        self.stage1: list[Op] = list()
        self.stage2: list[Op] = list()
        
        self.exception_pc = m.Exception_pc()
        
        # shared stages
        self.issue: Optional[s.Issue] = None
        
        
    def forwarding_path_read(self):
        return self.stage1 # as f&d executes before ALU, the stage 1 will contain what stage 2 would contain in a synchronous pipeline
    
    def push_instructions(self, ops: list[Op]) -> None:
        for op in ops:
            A, B = int(op.op["a"]), int(op.op["b"])
            match op.code: 
                case "add":
                    op.res = A + B
                case "addi":
                    op.res = A + int(op.imm)
                case "sub":
                    op.res = A - B
                case "mulu":
                    if A < 0: A = UINT64_MOD + A
                    if B < 0: B = UINT64_MOD + B
                    op.res = A * B
                case "divu":
                    if A < 0: A = UINT64_MOD + A
                    if B < 0: B = UINT64_MOD + B
                    
                    if B == 0:
                        op.exception = True
                        op.res = 0
                    else:
                        op.res = A // B
                        
                case "remu":
                    if A < 0: A = UINT64_MOD + A
                    if B < 0: B = UINT64_MOD + B
                    
                    if B == 0:
                        op.exception = True
                        op.res = 0
                        
                    else:
                        op.res = A % B

            op.res = int(op.res) % UINT64_MOD

        self.stage2 = self.stage1.copy()
        self.stage1 = ops.copy()
        
        return
        
    def propagate(self):
        assert self.issue is not None, "ALU should have access to issue stage"
        
        issue = cast(s.Issue, self.issue.copy)
        
        assert issue is not None, "Issue snapshot should be available before ALU propagation"
        
        #################################################################################################################
        
        # push instructions through the ALU pipeline
        self.push_instructions(issue.data)
        
    
    def dump(self, no_assert = False) -> dict:
        return self.exception_pc.dump()
    
    