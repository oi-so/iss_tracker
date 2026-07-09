class MountSimulator:

    def __init__(self):

        self.ra = 0.0
        self.dec = 0.0

        self.guide_ra = 0
        self.guide_dec = 0

        self.guide_speed = 0.5  # deg/s

    def connect(self):
        print("Simulator Connected")


    def disconnect(self):
        print("Simulator Disconnected")


    def goto(self, ra, dec):

        self.ra = ra.hours * 15
        self.dec = dec.degrees


    def get_position(self):

        return self.ra, self.dec
    
    def pulse_guide(
        self,
        ra_rate,
        dec_rate,
        duration,
    ):

        self.guide_ra = ra_rate
        self.guide_dec = dec_rate

    def update(self, dt):

        self.ra += self.guide_ra * dt
        self.dec += self.guide_dec * dt