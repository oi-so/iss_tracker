from skyfield.api import load

SKYFIELD_NAMES = {
    "sun": "sun",
    "moon": "moon",
    "mercury": "mercury",
    "venus": "venus",
    "mars": "mars barycenter",
    "jupiter": "jupiter barycenter",
    "saturn": "saturn barycenter",
    "uranus": "uranus barycenter",
    "neptune": "neptune barycenter",
}


def get_object_coordinates(name: str, orbit, utc_time):
    eph = load("de440s.bsp")

    earth = eph["earth"]
    target = eph[SKYFIELD_NAMES[name]]

    t = orbit.ts.from_datetime(utc_time)

    ra, dec, _ = (
        earth
        .at(t)
        .observe(target)
        .apparent()
        .radec()
    )

    return ra.hours, dec.degrees