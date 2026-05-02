
class Op():
    def __init__(self, opcode: str, 
                 opA: float, opB: float, 
                 tagA: int, tagB: int, 
                 p_dest: int, v_dest: int,
                 old_p_dest: int,
                 imm: int, pc: int,
                 exception: bool = False):
        
        assert p_dest < 64 and v_dest < 32, "p_dest must be less than 64 and v_dest must be less than 32"
        
        self.code = opcode
        self.op = {"a": opA, "b": imm if opcode == "addi" else opB} # for addi, opB is always the immediate (including 0)
        self.tag = {"a": tagA, "b": tagB}
        self.imm = imm
        
        self.op_ready = {"a": False, "b": True if opcode == "addi" else False} # addi operand B is immediate and thus always ready
        
        
        self.p_dest = p_dest
        self.v_dest = v_dest
        self.old_p_dest = old_p_dest
        
        self.exception = exception
        
        self.pc = pc

        self.done = False
        self.res = 0.0
    
    @staticmethod    
    def decode(inst: str, pc: int) -> "Op":
        #TODO : add exception handling for invalid instructions
        parts = inst.replace(",", "").replace("x", "").split()
        opcode = parts[0]
        
        
        v_dest = int(parts[1])
        tagA = int(parts[2])  
        
        if opcode in ("add", "sub", "mulu", "divu", "remu"):
            tagB = int(parts[3])
            imm = 0
        elif opcode == "addi":
            tagB = 0
            imm = int(parts[3])
        else:
            raise ValueError(f"Invalid opcode: {opcode}")
        
        # we do not initialize op fields and physical destination field here, as they will be set during the rd stage
        return Op(opcode, 0, 0, tagA, tagB, 0, v_dest, 0, imm, pc, False)