from dataclasses import dataclass

@dataclass
class VesselConfig:
    name: str = 'Unnamed Vessel'; length_m: float = 12.0; beam_m: float = 4.0
    antenna_offset_x_m: float = 0.0; antenna_offset_y_m: float = 0.0; shape: str = 'Generic Vessel'
    SHAPES = ('Generic Vessel','Patrol Boat','Workboat','Supply Vessel','Barge')
    def validate(self):
        if self.length_m <= 0 or self.beam_m <= 0: raise ValueError('Vessel length and beam must be positive.')
        if self.shape not in self.SHAPES: raise ValueError('Unsupported vessel shape.')
