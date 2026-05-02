from structs.stages.stage import Stage
from structs.op import Op
import structs.micro_arc as m
import structs.stages as s
from typing import Optional

class Rd(Stage):
    copy: Optional["Rd"]

    def __init__(self):
        
        self.name = "rename-dispatch"
        self.data = []
        self.shared = list()
        
        # 
        self.issue_idx_popped = list() # list of indices popped from the issue queue in the current cycle, used to update integer queue
        self.pending_decoded: list[Op] = []
        
        # shared stages
        self.fd: Optional[s.Fd] = None
        self.alu: Optional[s.Alu] = None
        self.commit: Optional[s.Commit] = None
        
        self.free_list = m.Free_list()
        self.reg_map = m.Register_map()
        self.busy_table = m.Busy_bit_table()
        self.p_reg = m.P_register_file()
        self.integer_queue = m.Integer_queue()
    
    def propagate(self):
        # has access to fd, integer queue, commit, alu, input data is loaded
        assert self.fd is not None, "Rd should have access to fd"
        assert self.integer_queue is not None, "Rd should have access to integer queue"
        assert self.alu is not None, "Rd should have access to alu"
        assert self.commit is not None, "Rd should have access to commit"

        fd = self.fd.copy
        alu = self.alu.copy
        commit = self.commit.copy

        assert fd is not None, "Fd snapshot should be available before Rd propagation"
        assert alu is not None, "ALU snapshot should be available before Rd propagation"
        assert commit is not None, "Commit snapshot should be available before Rd propagation"
        ##############################################################################################################
        
        # add decoded instruction buffer to apply backpressure
        decoded_instructions = self.pending_decoded + fd.get_decoded_instructions()
        forwarded_ops = alu.forwarding_path_read()

        dispatch_budget = 4
        dispatch_budget = min(dispatch_budget, 32 - len(self.integer_queue.data))
        dispatch_budget = min(dispatch_budget, 32 - len(self.commit.active_list.data))
        dispatch_budget = min(dispatch_budget, len(self.free_list.data))
        dispatch_budget = max(0, dispatch_budget)

        to_dispatch = decoded_instructions[:dispatch_budget]
        self.pending_decoded = decoded_instructions[dispatch_budget:]
        
        # eliminate instructions popped by issue
        #self.integer_queue.remove_list(self.issue_idx_popped)
        #self.issue_idx_popped = list() # reset for the next cycle
        
        # update bbt and physical registers based on forwarded alu and active list results
        for op in forwarded_ops:
            if not op.exception:
                self.busy_table.unbusy(op.p_dest)
                self.p_reg.write(op.p_dest, op.res)
                for tag in ("a", "b"):
                    self.integer_queue.update_operand(op.p_dest, tag, op.res) # update operands waiting for this value in the integer queue
        
        for op in to_dispatch:
            
            # fill in the values looking at p_regs and busy bit table, if not ready update tags with what p_reg will produce the value 
            for tag in ("a", "b"):
                if op.code == "addi" and tag == "b": 
                    op.tag["b"] = 0
                    op.op_ready["b"] = True
                    continue # immediate operand
                
                # map tag
                op.tag[tag] = self.reg_map.read_map(op.tag[tag])
                
                # value ready, update operand
                if not self.busy_table.is_busy(op.tag[tag]): 
                    op.op[tag] = self.p_reg.read(op.tag[tag])
                    op.op_ready[tag] = True
            
            # keep track of old dest for rollback
            op.old_p_dest = self.reg_map.read_map(op.v_dest)
            
            # take free p-addr for destination register and update state
            op.p_dest = self.free_list.pop()
            self.reg_map.map(op.v_dest, op.p_dest)
            self.busy_table.busy(op.p_dest)
            
            # add to forward steps
            self.commit.active_list.add(op) # MODYFYING THE REAL COMMIT ACTIVE LIST, NOT A COPY
            self.integer_queue.add(op)
                
            
    
    def dump(self, no_assert = False) -> dict:
        dump = {self.free_list.name: self.free_list.data,
               self.reg_map.name: self.reg_map.data,
               self.busy_table.name: self.busy_table.data,
               self.p_reg.name: self.p_reg.data}
        integer_queue_dump = self.integer_queue.dump_log_data(no_assert = no_assert)
        
        return {**dump, self.integer_queue.name: integer_queue_dump}
        