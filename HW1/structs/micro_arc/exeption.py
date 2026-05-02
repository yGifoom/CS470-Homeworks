
class Exception_pc():
    def __init__(self):
        
        self.name = "ExceptionPC"
        self.data = 0
        self.exeption_flag = False
        
    
    def read(self) -> int:
        return self.data
    
    def exeption(self, exeption_pc: int):
        self.data = exeption_pc
        self.exeption_flag = True
        
    def clear_exception(self):
        self.exeption_flag = False
    
    def dump(self, no_assert = False) -> dict:
        return {self.name: self.data,
                "Exception": self.exeption_flag}
        