from skyfield.api import load


def get_object_coordinates(name: str, orbit, utc_time):
    """
    指定した天体の現在の赤経・赤緯を返す

    Returns
    -------
    ra_hours
    dec_degrees
    """

    eph = load("de440s.bsp")

    earth = eph["earth"]
    target = eph[name]

    t = orbit.ts.from_datetime(utc_time)

    ra, dec, _ = (
        earth
        .at(t)
        .observe(target)
        .apparent()
        .radec()
    )

    return ra.hours, dec.degrees