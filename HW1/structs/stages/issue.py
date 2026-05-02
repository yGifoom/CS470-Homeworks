from structs.stages.stage import Stage
from structs.op import Op
import structs.stages as s
from typing import Optional, cast
from copy import deepcopy

from main import DEBUG



class Issue(Stage):
    copy: Optional["Issue"]
    
    def __init__(self):
        
        self.name = "issue"
        self.data = []
        self.shared = list()
        
        # shared stages
        self.alu: Optional[s.Alu] = None
        self.rd: Optional[s.Rd] = None
    
    def propagate(self):
        assert self.alu is not None, "Issue should have access to alu"
        assert self.rd is not None, "Issue should have access to rd"

        # This stage outputs a fresh issue bundle every cycle.
        self.data = []
        
        alu = cast(s.Alu, self.alu.copy)
        rd = cast(s.Rd, self.rd.copy)
        
        assert alu is not None, "ALU snapshot should be available before Issue propagation"
        assert rd is not None, "Rd snapshot should be available before Issue propagation"
        #################################################################################################################
        
        alu_forwarding = [op for op in alu.forwarding_path_read() if not op.exception]

        issued = 0
        # iterate trhough integer data and check if operands are ready, if ready issue to alu
        for i, op in enumerate(rd.integer_queue.data):
            if issued >= 4: break # max of 4 instructions are issued per cycle
            
            # make a copy so that shared state is not modified when we update operands with forwarded values
            my_op = deepcopy(op)
            
            # check if operands are ready, if not check for forwarding
            for tag in ("a", "b"):
                if not my_op.op_ready[tag]: # operand not ready
                    # check for forwarding
                    for x in alu_forwarding:
                        
                        if x.p_dest == my_op.tag[tag]: # forwarding available
                            # update operand with forwarded value
                            my_op.op[tag] = x.res
                            my_op.op_ready[tag] = True
                            if DEBUG: print(f"LOG: Issue is forwarding from PC: {x.pc}, to PC: {my_op.pc} on tag {tag}")
                                
            if all(my_op.op_ready[tag] for tag in ("a", "b")):
                # issue the instruction to alu and remove from integer queue
                issued += 1
                self.data.append(my_op)
                
                # MODYFYING THE REAL, NOT A COPY. Not a problem as rd does not propagate until the end of the pipeline
                if DEBUG: print(f"LOG: Issuing instruction with PC {my_op.pc}, index is {i}")
                self.rd.issue_idx_popped.append(i)
        
        
        # eliminate instructions popped by issue
        self.rd.integer_queue.remove_list(self.rd.issue_idx_popped) # modify it for real
        self.rd.issue_idx_popped = list() # reset for the next cycle
            
    
    def dump(self, no_assert = False) -> dict:
        raise Exception("Issue stage should not be logged in the output file")
        