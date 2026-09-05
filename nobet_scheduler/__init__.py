"""Hospital emergency department monthly shift-roster scheduler.

Built on Google OR-Tools CP-SAT because doctor shift-count targets are exact
hard constraints (an exact-target assignment problem), not a preference to
approximate.
"""
