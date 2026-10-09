from PyQt5.QtCore import QPointF
from packages.core.models import MapPoint, PointType
from packages.core.pathfinding import build_full_route


def test_shortest_path_single_floor():
    p1 = MapPoint(1, "101", QPointF(0, 0), floor=1, point_type=PointType.ROOM)
    p2 = MapPoint(
        2, "Коридор", QPointF(10, 0), floor=1, point_type=PointType.REGULAR
    )
    p3 = MapPoint(3, "102", QPointF(20, 0), floor=1, point_type=PointType.ROOM)

    points_db = {1: p1, 2: p2, 3: p3}
    corridors = [(1, 2), (2, 3)]

    route, info = build_full_route(points_db, corridors, 1, 3)

    assert route is not None
    assert len(route) == 3
    assert [p.id for p in route] == [1, 2, 3]


if __name__ == "__main__":
    test_shortest_path_single_floor()
    print("Тесты пройдены успешно!")