
class Busy_bit_table():
    def __init__(self):
        
        self.name = "BusyBitTable"
        self.data = [False for _ in range(64)]
    
    def busy(self, p_reg: int):
        assert p_reg < 64, "Physical register index must be less than 64"
        
        self.data[p_reg] = True
        
    def unbusy(self, p_reg: int):
        assert p_reg < 64, "Physical register index must be less than 64"
        
        self.data[p_reg] = False
        
    def is_busy(self, p_reg: int) -> bool:
        assert p_reg < 64, "Physical register index must be less than 64"
        
        return self.data[p_reg]