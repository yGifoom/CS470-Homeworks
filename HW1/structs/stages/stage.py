from copy import deepcopy
from typing import Optional

class Stage():
    
    def __init__(self, name: str, data: list, log = True):
        self.log = True
        self.name = name
        self.data = data
        self.copy: Optional["Stage"] = None
        self.shared = list()
        
    
    def propagate(self):
        raise NotImplementedError
    
    def dump(self, no_assert = False) -> dict:
        raise NotImplementedError
    
    def cpy(self):
        # Avoid deepcopy-ing previous snapshots recursively.
        self.copy = None
        snapshot = deepcopy(self)
        self.copy = snapshot

    def __deepcopy__(self, memo):
        # Snapshot only local state. Stage-to-stage links create a cyclic graph
        # and are not needed in point-in-time snapshots.
        cls = self.__class__
        result = cls.__new__(cls)
        memo[id(self)] = result

        for key, value in self.__dict__.items():
            if key == "copy":
                setattr(result, key, None)
                continue

            if isinstance(value, Stage):
                setattr(result, key, None)
                continue

            setattr(result, key, deepcopy(value, memo))

        return result
    
    
        
        
    
    