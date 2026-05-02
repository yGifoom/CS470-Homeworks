
class Free_list():
    def __init__(self):
        
        self.name = "FreeList"
        self.data = [x for x in range(32, 64)]
        
    def how_many_free(self) -> int:
        return len(self.data)
        
    
    def pop(self) -> int:
        if len(self.data) == 0:
            return -1
        
        return self.data.pop(0)
        
    def push(self, p_reg: int):
        assert p_reg < 64 and p_reg not in self.data, "Physical register index must be less than 64 and not already in the free list"
        
        self.data.append(p_reg)