from structs.op import Op

class Integer_queue():
    def __init__(self):
        
        self.name = "IntegerQueue"
        self.length = 0
        self.data = []
        
    def add(self, op: Op):
        assert self.length < 32, "Integer queue can only hold up to 32 entries"
        
        self.length += 1
        self.data.append(op)
    
    def update_operand(self, p_dest: int, tag: str, value: float):
        for op in self.data:
            if not op.op_ready[tag] and op.tag[tag] == p_dest:
                op.op[tag] = value
                op.op_ready[tag] = True
        
    def remove_list(self, l_idx: list[int]):
        if self.length == 0:
            return
        
        assert self.length > 0, "Integer queue cannot be empty when trying to remove instructions"
        
        for idx in sorted(l_idx, reverse=True):
            assert idx < self.length, f"Index {idx} out of bounds for integer queue of size {self.length}"
            self.data.pop(idx)
            self.length -= 1
        
    def read(self, idx: int) -> dict:
        assert idx < self.length, f"Index {idx} out of bounds for integer queue of size {self.length}"
        return self.data[idx]
    
    def add_log(self, op: Op, no_assert = False) -> dict:

        if not no_assert:
            assert self.length <= 32, "Integer queue can only hold up to 32 entries"
            
        x = {
            "DestRegister": op.p_dest,
            "OpAIsReady": op.op_ready["a"],
            "OpARegTag": op.tag["a"],
            "OpAValue": op.op["a"],
            "OpBIsReady": op.op_ready["b"],
            "OpBRegTag": op.tag["b"],
            "OpBValue": op.op["b"], # for addi, opB value is the immediate
            "OpCode": op.code if op.code != "addi" else "add", # for addi log add
            "PC": op.pc
        }
        
        return x
        
    def dump_log_data(self, no_assert = False) -> list:
        if self.length == 0:
            return []
        
        log_data = [self.add_log(op, no_assert=no_assert) for op in self.data]
            
        return log_data
        