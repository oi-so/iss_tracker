class Predictor:
    def __init__(self, orbit):
        self.orbit = orbit

    def predict(self, duration, interval, base_time=None):
        if base_time is None:
            base_time = self.orbit.ts.now()

        positions = []
        t = 0.0

        while t <= duration:
            positions.append(self.orbit.get_position_after(base_time, t))
            t += interval

        return positions
