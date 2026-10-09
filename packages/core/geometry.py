import math
from typing import Optional, Tuple

Point2D = Tuple[float, float]


def project_point_onto_segment(
    p: Point2D, a: Point2D, b: Point2D
) -> Tuple[Point2D, float]:
    """
    Возвращает ближайшую точку на отрезке AB относительно точки P
    и квадрат расстояния до неё.
    """
    px, py = p
    ax, ay = a
    bx, by = b

    dx = bx - ax
    dy = by - ay

    if dx == 0 and dy == 0:
        dist_sq = (px - ax) ** 2 + (py - ay) ** 2
        return (ax, ay), dist_sq

    # Коэффициент проекции t = (PA · AB) / |AB|^2
    t = ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)

    # Ограничиваем t отрезком [0, 1]
    t = max(0.0, min(1.0, t))

    proj_x = ax + t * dx
    proj_y = ay + t * dy

    dist_sq = (px - proj_x) ** 2 + (py - proj_y) ** 2
    return (proj_x, proj_y), dist_sq


def find_segments_intersection(
    a1: Point2D, a2: Point2D, b1: Point2D, b2: Point2D
) -> Optional[Point2D]:
    """
    Находит точку пересечения двух отрезков A1A2 и B1B2, если они пересекаются.
    """
    x1, y1 = a1
    x2, y2 = a2
    x3, y3 = b1
    x4, y4 = b2

    denom = (x1 - x2) * (y3 - y4) - (y1 - y2) * (x3 - x4)
    if abs(denom) < 1e-9:
        return None  # Параллельны или совпадают

    t = ((x1 - x3) * (y3 - y4) - (y1 - y3) * (x3 - x4)) / denom
    u = -((x1 - x2) * (y1 - y3) - (y1 - y2) * (x1 - x3)) / denom

    if 0.0 <= t <= 1.0 and 0.0 <= u <= 1.0:
        px = x1 + t * (x2 - x1)
        py = y1 + t * (y2 - y1)
        return (px, py)

    return None


def distance(p1: Point2D, p2: Point2D) -> float:
    """Евклидово расстояние между двумя точками."""
    return math.hypot(p1[0] - p2[0], p1[1] - p2[1])