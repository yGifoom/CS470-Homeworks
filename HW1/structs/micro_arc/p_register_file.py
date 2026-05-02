
class P_register_file():
    def __init__(self):
        
        self.name = "PhysicalRegisterFile"
        self.length = 64
        self.data = [0 for _ in range(self.length)]
    
    def write(self, idx: int, value: int):
        self.data[idx] = int(value)
    
    def read(self, idx: int) -> int:
        assert idx < self.length, "Physical register index must be less than 64"
        return self.data[idx]