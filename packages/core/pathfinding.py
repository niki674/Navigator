import heapq
from typing import Dict, List, Optional, Tuple
from PyQt5.QtCore import QPointF

from packages.core.geometry import (
    distance,
    find_segments_intersection,
    project_point_onto_segment,
)
from packages.core.models import CorridorSegment, MapPoint, PointType


class VirtualGraph:
    """Динамический граф для поиска пути на этаже."""

    def __init__(self):
        self.adj: Dict[Tuple[float, float], List[Tuple[Tuple[float, float], float]]] = {}

    def add_edge(self, p1: Tuple[float, float], p2: Tuple[float, float]):
        dist = distance(p1, p2)
        if dist < 1e-5:
            return
        self.adj.setdefault(p1, []).append((p2, dist))
        self.adj.setdefault(p2, []).append((p1, dist))


def dijkstra_find_path(
    graph: VirtualGraph, start: Tuple[float, float], end: Tuple[float, float]
) -> Optional[List[Tuple[float, float]]]:
    """Поиск кратчайшего пути по координатам в виртуальном графе."""
    distances = {start: 0.0}
    previous = {}
    queue = [(0.0, start)]

    while queue:
        current_dist, current_node = heapq.heappop(queue)

        if current_node == end:
            path = []
            curr = end
            while curr in previous:
                path.append(curr)
                curr = previous[curr]
            path.append(start)
            return path[::-1]

        if current_dist > distances.get(current_node, float("inf")):
            continue

        for neighbor, weight in graph.adj.get(current_node, []):
            new_dist = current_dist + weight
            if new_dist < distances.get(neighbor, float("inf")):
                distances[neighbor] = new_dist
                previous[neighbor] = current_node
                heapq.heappush(queue, (new_dist, neighbor))

    return None


def qpoint_to_tuple(pt: QPointF) -> Tuple[float, float]:
    return (float(pt.x()), float(pt.y()))


def calculate_path_length(path: List[Tuple[float, float]]) -> float:
    """Вычисляет общую длину пути по списку координат."""
    total = 0.0
    for i in range(len(path) - 1):
        total += distance(path[i], path[i + 1])
    return total


def build_floor_graph(
    points_db: Dict[int, MapPoint], corridors: List[CorridorSegment], floor: int
) -> VirtualGraph:
    """Строит граф коридоров и подключений для указанного этажа."""
    v_graph = VirtualGraph()
    floor_corridors = [c for c in corridors if c.floor == floor]
    floor_points = [p for p in points_db.values() if p.floor == floor]

    # 1. Основные ребра коридоров
    for corr in floor_corridors:
        if corr.start_node_id not in points_db or corr.end_node_id not in points_db:
            continue

        a = qpoint_to_tuple(points_db[corr.start_node_id].coords)
        b = qpoint_to_tuple(points_db[corr.end_node_id].coords)

        points_on_segment = [a, b]

        for other in floor_corridors:
            if other.id == corr.id:
                continue
            if other.start_node_id in points_db and other.end_node_id in points_db:
                c_a = qpoint_to_tuple(points_db[other.start_node_id].coords)
                c_b = qpoint_to_tuple(points_db[other.end_node_id].coords)
                intersect = find_segments_intersection(a, b, c_a, c_b)
                if intersect:
                    points_on_segment.append(intersect)

        points_on_segment = list(set(points_on_segment))
        points_on_segment.sort(key=lambda pt: distance(a, pt))

        for i in range(len(points_on_segment) - 1):
            v_graph.add_edge(points_on_segment[i], points_on_segment[i + 1])

    # 2. Подключение точек (кабинетов и лестниц) к коридорам
    for p in floor_points:
        if p.point_type in (PointType.ROOM, PointType.STAIR):
            p_tuple = qpoint_to_tuple(p.coords)

            best_proj = None
            min_dist = float("inf")
            best_segment = None

            for corr in floor_corridors:
                if corr.start_node_id not in points_db or corr.end_node_id not in points_db:
                    continue
                a = qpoint_to_tuple(points_db[corr.start_node_id].coords)
                b = qpoint_to_tuple(points_db[corr.end_node_id].coords)

                proj, dist = project_point_onto_segment(p_tuple, a, b)
                if dist < min_dist:
                    min_dist = dist
                    best_proj = proj
                    best_segment = (a, b)

            if best_proj and best_segment:
                v_graph.add_edge(p_tuple, best_proj)
                v_graph.add_edge(best_segment[0], best_proj)
                v_graph.add_edge(best_proj, best_segment[1])

    return v_graph


def build_full_route(
    points_db: Dict[int, MapPoint],
    corridors: List[CorridorSegment],
    start_id: int,
    end_id: int,
) -> Tuple[List[MapPoint], str]:
    if start_id not in points_db or end_id not in points_db:
        return [], "Одна из выбранных точек не найдена."

    start_pt = points_db[start_id]
    end_pt = points_db[end_id]

    start_tuple = qpoint_to_tuple(start_pt.coords)
    end_tuple = qpoint_to_tuple(end_pt.coords)

    # 1. Одноэтажный маршрут
    if start_pt.floor == end_pt.floor:
        floor = start_pt.floor
        v_graph = build_floor_graph(points_db, corridors, floor)
        coord_path = dijkstra_find_path(v_graph, start_tuple, end_tuple)

        if not coord_path:
            return [], f"Не удалось проложить маршрут по {floor} этажу."

        route_pts = [
            MapPoint(
                point_id=-1,
                name=f"Точка {i}",
                coords=QPointF(coords[0], coords[1]),
                floor=floor,
            )
            for i, coords in enumerate(coord_path)
        ]
        return route_pts, f"Маршрут построен по {floor} этажу."

    # 2. Многоэтажный маршрут
    start_stairs = [
        p for p in points_db.values()
        if p.floor == start_pt.floor and p.point_type == PointType.STAIR
    ]
    end_stairs = [
        p for p in points_db.values()
        if p.floor == end_pt.floor and p.point_type == PointType.STAIR
    ]

    if not start_stairs or not end_stairs:
        return [], "Нет доступных лестниц для перехода между этажами."

    v_graph_start = build_floor_graph(points_db, corridors, start_pt.floor)
    v_graph_end = build_floor_graph(points_db, corridors, end_pt.floor)

    best_total_length = float("inf")
    best_path_start = None
    best_path_end = None
    chosen_stair_name = ""

    # Ищем совпадающие по названию/идентификатору лестницы на обоих этажах
    for st_start in start_stairs:
        # Сопоставляем по имени (например "1", "2" или "Лестница №1")
        st_end = next((s for s in end_stairs if s.name.strip() == st_start.name.strip()), None)
        if not st_end:
            continue

        st_start_tuple = qpoint_to_tuple(st_start.coords)
        st_end_tuple = qpoint_to_tuple(st_end.coords)

        # Строим пути до выбранной парной лестницы на обоих этажах
        p1 = dijkstra_find_path(v_graph_start, start_tuple, st_start_tuple)
        p2 = dijkstra_find_path(v_graph_end, st_end_tuple, end_tuple)

        if p1 and p2:
            total_len = calculate_path_length(p1) + calculate_path_length(p2)
            if total_len < best_total_length:
                best_total_length = total_len
                best_path_start = p1
                best_path_end = p2
                chosen_stair_name = st_start.name

    if not best_path_start or not best_path_end:
        return [], "Не удалось построить связный маршрут между этажами по имеющимся лестницам."

    route1 = [
        MapPoint(-1, "Маршрут 1", QPointF(c[0], c[1]), start_pt.floor)
        for c in best_path_start
    ]
    route2 = [
        MapPoint(-1, "Маршрут 2", QPointF(c[0], c[1]), end_pt.floor)
        for c in best_path_end
    ]

    info = f"Переход с {start_pt.floor} этажа на {end_pt.floor} этаж через лестницу '{chosen_stair_name}'."
    return route1 + route2, info