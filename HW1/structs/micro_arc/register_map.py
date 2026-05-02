
class Register_map():
    def __init__(self):
        
        self.name = "RegisterMapTable"
        self.data = [x for x in range(32)]
    
    def map(self, v_reg: int, p_reg: int):
        assert v_reg < 32 and p_reg < 64, "Virtual register index must be less than 32 and physical register index must be less than 64"
        
        self.data[v_reg] = p_reg
        
    def read_map(self, v_reg: int):
        return self.data[v_reg]