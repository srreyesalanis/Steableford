"""
stableford.py — Lógica de puntos Stableford
"""


def course_handicap(handicap_index: float, slope: int, rating: float, par: int) -> int:
    """Course Handicap = HI × (Slope / 113) + (CR - Par)"""
    return round(handicap_index * (slope / 113) + (rating - par))


def strokes_received(course_hcp: int, hole_handicap: int) -> int:
    """
    El jugador recibe golpe en un hoyo si hole_handicap <= course_hcp.
    Ejemplo: HCP 10, hoyo HCP 11 → 0 golpes (11 > 10)
             HCP 10, hoyo HCP 9  → 1 golpe  (9 <= 10)
             HCP 20, hoyo HCP 9  → 2 golpes (vuelta extra)
    """
    if course_hcp <= 0 or hole_handicap > course_hcp:
        return 0
    return 1 + (course_hcp - hole_handicap) // 18


def net_strokes(gross: int, received: int) -> int:
    return max(0, gross - received)


def stableford_points(net: int, par: int) -> int:
    """
    Net vs Par:
      Eagle o mejor (+2): 4 pts
      Birdie (+1):         3 pts
      Par (0):             2 pts
      Bogey (-1):          1 pt
      Double bogey o peor: 0 pts
    """
    diff = net - par
    if diff <= -2:
        return 4
    elif diff == -1:
        return 3
    elif diff == 0:
        return 2
    elif diff == 1:
        return 1
    else:
        return 0


def calc_hole(gross: int, par: int, course_hcp: int, hole_handicap: int) -> dict:
    received = strokes_received(course_hcp, hole_handicap)
    net = net_strokes(gross, received)
    pts = stableford_points(net, par)
    return {
        "gross": gross,
        "received": received,
        "net": net,
        "points": pts,
    }
