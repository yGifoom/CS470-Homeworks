from structs.op import Op

class Active_list():
    def __init__(self):
        
        self.name = "ActiveList"
        self.length = 0
        self.stage1 = list()
        self.stage2 = list()
        self.data = self.stage2
    
    
    def add(self, op: Op):
        assert self.length < 32, "Active list can only hold up to 32 entries"
        self.length += 1
        self.data.append(op)
    
    def remove(self, idx: int):
        self.data.pop(idx)
        self.length -= 1
    
    def done_op(self, p_dest: int):
        for op in self.data:
            if op.p_dest == p_dest:
                op.done = True
                return
            
        raise Exception(f"Operation with physical destination {p_dest} not found in active list")
    
    def update_exception(self, p_dest: int):
        for op in self.data:
            if op.p_dest == p_dest:
                op.exception = True
                return
            
        raise Exception(f"Operation with physical destination {p_dest} not found in active list")
    
    def add_log(self, op: Op, no_assert = False) -> dict:
        
        # maximum n of active registers is 32
        if not no_assert:
            assert self.length <= 32, "Active list can only hold up to 32 entries"
        
        x = {
            "Done": op.done,
            "Exception": op.exception,
            "LogicalDestination": op.v_dest,
            "OldDestination": op.old_p_dest,
            "PC": op.pc,
            }
        
        return x
    
    def dump_log_data(self, no_assert = False) -> list:
        if self.length == 0:
            return []
        
        log_data = [self.add_log(op, no_assert = no_assert) for op in self.data]
            
        return log_data