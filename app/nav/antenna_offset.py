from math import cos, radians

def reference_position(latitude, longitude, heading_deg, offset_x_m, offset_y_m):
    """Derive display reference; +X forward, +Y starboard. Canonical input is untouched."""
    h=radians(heading_deg or 0); north=offset_x_m*cos(h)-offset_y_m*__import__('math').sin(h); east=offset_x_m*__import__('math').sin(h)+offset_y_m*cos(h)
    return latitude+north/111_320, longitude+east/(111_320*cos(radians(latitude)))
