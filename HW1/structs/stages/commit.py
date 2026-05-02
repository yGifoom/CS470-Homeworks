from structs.stages.stage import Stage
import structs.micro_arc as m
import structs.stages as s
from typing import Optional, cast

from main import DEBUG

class Commit(Stage):
    copy: Optional["Commit"]
    
    def __init__(self):
        
        self.name = "commit"
        self.data = []
        self.shared = list()
        
        self.active_list = m.Active_list()
        
        self.fd: Optional[s.Fd] = None
        self.rd: Optional[s.Rd] = None
        self.alu: Optional[s.Alu] = None
        
    
    def done(self):
        if self.active_list.data == []:
            return True
        return False

    def _flush_on_exception_entry(self):
        # Stop fetching/decoding and clear speculative work immediately.
        self.fd.decoded_instructions.data = []
        self.fd.data = []
        self.rd.integer_queue.data = []
        self.rd.integer_queue.length = 0
        self.alu.stage1 = []
    
    
    def propagate(self):
        assert self.alu is not None, "Commit should have access to ALU"
        assert self.rd is not None, "Commit should have access to Rd"
        assert self.fd is not None, "Commit should have access to Fd"
        
        
        rd = cast(s.Rd, self.rd.copy)
        alu = cast(s.Alu, self.alu.copy)
        fd = cast(s.Fd, self.fd.copy)
        
        
        assert rd is not None, "Rd snapshot should be available before Commit propagation"
        assert alu is not None, "ALU snapshot should be available before Commit propagation"
        assert fd is not None, "Fd snapshot should be available before Commit propagation"

        ####################################################################################################################
        # are we in exception recover mode?
        if self.alu.exception_pc.exeption_flag:
            self.exception_recover()
            return
        
        
        # First retire up to 4 instructions already marked done from prior cycles.
        committed = 0
        while committed < 4 and self.active_list.length > 0:
            head = self.active_list.data[0]
            if not head.done:
                break
            
            if head.exception:
                # modify objects and not copy
                # set exceptionPC and exceptionFlag
                self.fd.pc.exeption()
                self.alu.exception_pc.exeption(head.pc)
                self._flush_on_exception_entry()
                break
                
            # On retirement, reclaim the previous physical destination register.
            self.rd.free_list.push(head.old_p_dest)
            self.active_list.remove(0)
            committed += 1

        # Then consume ALU completions so they become visible as Done next cycle.
        for op in alu.forwarding_path_read():
            if DEBUG: print(f"LOG: Committing instruction with p_dest {op.p_dest} and res {op.res}")
            self.active_list.done_op(op.p_dest)
            
            if op.exception:
                self.active_list.update_exception(op.p_dest)
    
    def exception_recover(self):
        assert self.alu is not None, "Commit should have access to ALU"
        assert self.rd is not None, "Commit should have access to Rd"
        assert self.fd is not None, "Commit should have access to Fd"
        
        # F&D is halted and Decoded Instruction regisers emptied
        self.fd.decoded_instructions.data = []
        self.fd.data = []
        
        # reset Integer Queue and ALU
        self.rd.integer_queue.data = []
        self.rd.integer_queue.length = 0
        self.alu.stage1 = []
        
        if self.active_list.length == 0:
            self.alu.exception_pc.clear_exception() 
            return
        
        rolled_back = 0
        for op in self.active_list.data[::-1]:
            
            # resets Register Map Table, FreeList, BBT using old Dest
            self.rd.free_list.push(op.p_dest)
            self.rd.busy_table.unbusy(op.p_dest)
            self.rd.reg_map.map(op.v_dest, op.old_p_dest)
            
            # reset active_list
            self.active_list.remove(-1)
            rolled_back += 1
            if rolled_back == 4:
                break
    
    def dump(self, no_assert = False) -> dict:
        dump = {self.active_list.name: self.active_list.data}
        
        active_list_dump = self.active_list.dump_log_data(no_assert = no_assert)
        return {**dump, self.active_list.name: active_list_dump}

    
        