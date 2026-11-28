"""Synthetic-only consecutive marker gate; not a speech VAD."""
class MarkerGate:
    def __init__(self, required=3):
        if required not in (1,2,3):
            raise ValueError("unsupported confirmation count")
        self.required=required
        self.pending=0
        self.count=0

    def feed(self, marker):
        if marker not in (1,2):
            self.pending=self.count=0
            return False
        self.count=self.count+1 if marker==self.pending else 1
        self.pending=marker
        return self.count==self.required
