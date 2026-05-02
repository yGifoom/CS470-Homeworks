
class Decoded_instructions():
    def __init__(self):
        
        self.name = "DecodedPCs"
        self.length = 0
        self.data = []
        
        
    
    def add(self, new_inst: list):
        assert all([el not in self.data for el in new_inst]), "Decoded instructions must be unique"
        
        self.data.extend(new_inst)
        