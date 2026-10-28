def is_point_in_rect(point, rect):
    """
    Checks if point (cx, cy) is inside rectangle [x1, y1, x2, y2].
    """
    px, py = point
    x1, y1, x2, y2 = rect
    return (x1 <= px <= x2) and (y1 <= py <= y2)

def is_point_in_polygon(point, polygon_pts):
    """
    Ray-casting algorithm for checking if point (cx, cy) is inside arbitrary polygon [(x, y), ...].
    """
    px, py = point
    inside = False
    n = len(polygon_pts)
    if n < 3:
        return False

    p1x, p1y = polygon_pts[0]
    for i in range(1, n + 1):
        p2x, p2y = polygon_pts[i % n]
        if py > min(p1y, p2y):
            if py <= max(p1y, p2y):
                if px <= max(p1x, p2x):
                    if p1y != p2y:
                        xinters = (py - p1y) * (p2x - p1x) / (p2y - p1y) + p1x
                    if p1x == p2x or px <= xinters:
                        inside = not inside
        p1x, p1y = p2x, p2y

    return inside
