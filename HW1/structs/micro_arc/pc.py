class Pc():
    def __init__(self):
        
        self.name = "PC"
        self.data = 0
        self.old = 0
        self.shared = list()
        self.input_data = []
    
    def next_many(self, n: int):
        assert n <= 4 and n >= 0, "Can only fetch up to 4 instructions at a time"
        self.data += n
    
    def read(self) -> int:
        return self.data
    
    def exeption(self):
        self.old = self.data
        self.data = 0x10000
    
    def recover_exception(self):
        self.data = self.old
        