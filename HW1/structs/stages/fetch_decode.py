from structs.stages.stage import Stage
from structs.op import Op
import structs.micro_arc as m
import structs.stages as s
from typing import Optional


class Fd(Stage):
    copy: Optional["Fd"]

    def __init__(self):
        
        self.name = "fetch-decode"
        self.data = []
        self.shared: list[Optional["Stage"]] = []
        self.rd: Optional[s.Rd] = None
        
        self.input_data = list()
        self.data = []
        
        self.pc = m.Pc()
        self.decoded_instructions = m.Decoded_instructions()
    
    def done(self):
        if self.pc.read() < len(self.input_data):
            return False
        if self.rd is not None and len(self.rd.pending_decoded) > 0:
            return False
        return len(self.decoded_instructions.data) == 0
    
    # fd budget depends on backpressure from rd, but rd also keeps track of alu forwards when deciding how many vacant spaces  
    @staticmethod
    def _predict_issue_credit(rd: "s.Rd") -> int:
        # Estimate how many IQ entries will be popped this cycle by Issue.
        forwarding_tags = set()
        if rd.alu is not None:
            forwarding_tags = {op.p_dest for op in rd.alu.forwarding_path_read() if not op.exception}

        credit = 0
        for op in rd.integer_queue.data:
            if credit >= 4:
                break

            ready_a = op.op_ready["a"] or op.tag["a"] in forwarding_tags
            ready_b = op.op_ready["b"] or op.tag["b"] in forwarding_tags
            if ready_a and ready_b:
                credit += 1

        return credit

    @staticmethod
    def _predict_commit_credit(rd: "s.Rd") -> int:
        # Estimate how many active-list entries Commit can retire this cycle.
        if rd.commit is None:
            return 0

        credit = 0
        for op in rd.commit.active_list.data:
            if credit >= 4:
                break
            if not op.done or op.exception:
                break
            credit += 1

        return credit
        
    def propagate(self):
        # has access to rd, input data is loaded
        assert self.rd is not None, "Fd should have access to rd"
        assert self.input_data is not None, "Input data should be loaded into Fd before propagation"

        # Backpressure: only fetch what rename/dispatch can realistically absorb.
        # Include same-cycle Issue/Commit release credits to avoid artificial bubbles.
        rd = self.rd
        issue_credit = self._predict_issue_credit(rd)
        commit_credit = self._predict_commit_credit(rd)

        iq_space = max(0, 32 - len(rd.integer_queue.data) + issue_credit)
        al_space = max(0, 32 - len(rd.commit.active_list.data) + commit_credit) if rd.commit is not None else 4
        fl_space = max(0, len(rd.free_list.data) + commit_credit)
        pending_slots = max(0, 4 - len(rd.pending_decoded))

        dispatch_budget = 4
        dispatch_budget = min(dispatch_budget, iq_space)
        dispatch_budget = min(dispatch_budget, fl_space)
        dispatch_budget = min(dispatch_budget, al_space)
        dispatch_budget = min(dispatch_budget, pending_slots)
        dispatch_budget = max(0, dispatch_budget)
        
        if self.pc.read() >= len(self.input_data): # either exception or we're done
            self.decoded_instructions.data = [] # expose empty list to signal no more instructions to fetch
            self.data = [] # reset decoded instructions
            return # no more instructions to fetch
        
        # fetch up to 4 instructions at a time, but not more than the number of remaining instructions
        old_pc = self.pc.read()
        n_inst = min(len(self.input_data) - self.pc.read(), dispatch_budget)
        if n_inst == 0:
            self.decoded_instructions.data = [] # expose empty list to signal no more instructions to fetch
            self.data = [] # reset decoded instructions
            return # no more instructions to fetch
        
        self.pc.next_many(n_inst)
        
        
        # decode the instructions and update the decoded instructions register
        new_ins_idxs = range(old_pc, old_pc + n_inst)
        decoded = [Op.decode(self.input_data[i], i) for i in new_ins_idxs]
        
        
        # expose decoded instructions
        self.decoded_instructions.data = list(new_ins_idxs)
        self.data = decoded
        

    def get_decoded_instructions(self) -> list[Op]:
        return self.data
    
    def dump(self, no_assert = False) -> dict:
        return {self.decoded_instructions.name: self.decoded_instructions.data, self.pc.name: self.pc.data}
        