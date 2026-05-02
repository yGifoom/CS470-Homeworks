import sys
import os
import json
import traceback
from copy import deepcopy

import structs.stages as s
from structs.stages.stage import Stage
from cycle_estimator import estimate_cycles_microarchitecture

DEBUG = False

def main():
    
    assert len(sys.argv) == 3, "Usage: python main.py <input_file> <output_file>"
    if DEBUG:
        print("Input file:", sys.argv[1])
        print("Output file:", sys.argv[2])
    
    input_file = sys.argv[1]
    output_file = sys.argv[2]
    
    with open(input_file, "r") as f:
        input_data = json.load(f)

    estimated_cycles = estimate_cycles_microarchitecture(input_data)
    
    
    
    # 0.1 Initialize stages
    fd = s.Fd()
    rd = s.Rd()
    issue = s.Issue()
    alu = s.Alu()
    commit = s.Commit()
    
    # 0.2 Propagate the shared state between relevant components
    # Typed wiring for static analysis-friendly stage access.
    #TODO : no exception handling for now, we will add it later
    # Fetch and decode
    fd.rd = rd
    
    # Rename and dispatch
    rd.fd = fd
    rd.alu = alu
    rd.commit = commit
    
    # Issue
    issue.alu = alu
    issue.rd = rd
    
    # ALU
    alu.issue = issue
    
    # Commit
    commit.fd = fd
    commit.rd = rd
    commit.alu = alu
    
    pipeline: list[Stage] = [fd, rd, issue, alu, commit]
    
    # 0.3 Load the input data into the relevant components
    fd.input_data = input_data
    
    
    # 1. Simulate the microarchitecture
    result = list()
    i = 0
    try:
        # Hard upper bound: simulation must complete within 6x instruction count.
        # Allow lowering via env var, but never allow values above 6.
        requested_cap_factor = int(os.environ.get("MAX_CYCLE_FACTOR", "6"))
        cycle_cap_factor = min(6, max(1, requested_cap_factor))
        max_cycle_count = max(1, cycle_cap_factor * len(input_data))
        # while max cycle is not hit AND
        # while fb and commit are full OR
        # while it's the first cycle (all is empty) OR
        # while there is an exception that has not been fully handled 
        while i < max_cycle_count and (i == 0 or not (fd.done() and commit.done() and not alu.exception_pc.exeption_flag)):
            # 1.1 dump the state of the microarchitecture at the beginning of each cycle and copy state
            if DEBUG: print(f"Cycle {i}:")
            dump_buffer = dict()
            for stage in pipeline:
                stage.cpy() # copy the state of the stage before propagating
                if stage == issue: continue # no need to keep track of alu and issue
                dump_buffer.update(stage.dump())
                
            # 1.2 save state in result list
            result.append(deepcopy(dump_buffer))
        

            # 1.3 propagate the state of the microarchitecture
            for stage in pipeline:
                stage.propagate()
            i += 1
            
        # Exceeding the hard cap indicates a pipeline-progress bug.
        if not (fd.done() and commit.done() and not alu.exception_pc.exeption_flag):
            raise RuntimeError(
                f"Simulation did not quiesce within {max_cycle_count} cycles "
                f"(cap={cycle_cap_factor}x instructions, n={len(input_data)})."
            )

        # dump the final state of the microarchitecture at the end of the simulation
        #alu.exception_pc.clear_exception() # clear exception flag at the end of the simulation to avoid confusion when analyzing the dump
        dump_buffer = dict()
        for stage in pipeline:
                stage.cpy() # copy the state of the stage before propagating
                if stage == issue : continue # no need to keep track of issue
                dump_buffer.update(stage.dump())
        result.append(deepcopy(dump_buffer))
        
            
    
    except Exception as e:
        if DEBUG:
            print(f"An {type(e).__name__} occurred during simulation: {e}")
            traceback.print_exc()
            print("Dumping the state of the microarchitecture at the time of the exception...")
            dump_buffer = dict()
            for stage in pipeline:
                if stage in (alu, issue) : continue
                dump_buffer.update(stage.dump(no_assert = True))
            result.append(deepcopy(dump_buffer))
            print("Dumped state:", dump_buffer)
        raise
    
    # 2. Write the dump buffer to the output json file
    os.makedirs(os.path.dirname(output_file), exist_ok=True)
    with open(output_file, "w") as f:
        json.dump(result, f, indent=4)

    # 3. Write cycle estimate metadata alongside the output for external runners.
    meta = {
        "instruction_count": len(input_data),
        "estimated_cycles": estimated_cycles,
        "actual_cycles": i,
        "delta_cycles": i - estimated_cycles,
        "estimate_model": "idealized 4-wide scoreboard pipeline",
    }
    with open(f"{output_file}.meta.json", "w") as f:
        json.dump(meta, f, indent=4)
    

if __name__ == "__main__": 
    main()