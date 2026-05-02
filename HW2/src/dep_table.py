

class Dep_table():
    def __init__(self, instructions):
        self.instructions_list = instructions
        self.table = self.build_dep_table()
    
    def build_dep_table(self):
        bbs = self.instructions_list.bbs
        inst = self.instructions_list.instructions
        table = list()
        
        producers = dict() # reg -> list of instr indices that produce it        
        
        
        
        bb = 1 # bb end pc index # REMINDER: [bbs[0], bbs[1]) is the pre-loop bb, [bbs[1], bbs[2]) is the loop bb, [bbs[2], bbs[3]) is the post-loop bb
        
        for i in range(len(inst)):
            producers[inst[i]["dest"]] = producers.get(inst[i]["dest"], list()) + [i]
            
        for i in range(bbs[-1]): # i is instr index
            if i > bbs[bb] - 1: # if last instruction of the bb, move to next bb
                bb += 1
                if bb >= len(bbs): bb-=1 # ugly I know, also i do not care!
            
            local_dep = list() # producer consumer same bb, producer before consumer
            interloop_dep = list() # consumer in loop, producer in different bb (if same loop bb after consumer becomes loop carried)
            loop_invariant_dep = list() # producer in pre-loop bb, consumer in loop, post loop bb, no other producer in loop
            post_loop_dep = list() # producer in loop, consumer in post-loop bb
                        
            for op in inst[i]["ops"]:
                print(bb, i)
                local_dep.extend([(op, k) for k in producers.get(op, list()) if (k < bbs[bb] and k >= bbs[bb - 1] and k < i)]) 
                
                if bb > 1:

                    latest_producer_of_op = max([k for k in producers.get(op, list()) if k < bbs[2]])
                    print("latest producer of op ", op, " is ", latest_producer_of_op)
                    if latest_producer_of_op < bbs[1]:
                        loop_invariant_dep.append((op, latest_producer_of_op))
                        
                if bb == 2: # if this is not the first bb, also check for loop-carried deps
                    
                    for k in producers.get(op, list()):
                        if (k >= i and k < bbs[2]) or (k < bbs[1]):
                            if (op, k) not in loop_invariant_dep: # give pecedence to loop invariant deps
                                interloop_dep.append((op, k))
                        
                
                if bb == 3: # if this is not the first two bbs, also check for post-loop deps                    
                    
                    # pick the latest dependencies
                    latest_dep = max([k for k in producers.get(op, list()) if k < bbs[2]])
                    post_loop_dep.append((op, latest_dep))
                                                    
            table.append({
                "instr": i,
                "dest": inst[i]["dest"],
                "local_dep": local_dep,
                "interloop_dep": interloop_dep,
                "loop_invariant_dep": loop_invariant_dep,
                "post_loop_dep": post_loop_dep,
            })
            

        return table


if __name__ == "__main__":
    from instructions import Instructions
    import json
    
    with open("/home/ygifoom/epfl/aa/CS470-Homeworks/HW2/given_tests/00/input.json", "r") as f:
        instrs = Instructions(json.load(f))
        
    print("bbs are: ", instrs.bbs)
        
    dep_table = Dep_table(instrs)
    
    for entry in dep_table.table:
        print(entry)
        
                