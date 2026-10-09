import json
import os
from typing import Dict, List
from packages.core.models import CorridorSegment, MapPoint


class ProjectData:
    """Контейнер для хранения распарсенных данных проекта."""

    def __init__(self):
        self.floors_list: List[int] = [1]
        self.corridors: List[CorridorSegment] = []
        self.points_db: Dict[int, MapPoint] = {}
        self.floor_image_paths: Dict[int, str] = {}


def load_project_from_json(file_path: str) -> ProjectData:
    """Загрузка конфигурации графа и этажей из JSON файла."""
    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    project = ProjectData()
    project.floors_list = [int(x) for x in data.get("floors_list", [1])]

    for p_dict in data.get("points", []):
        pt = MapPoint.from_dict(p_dict)
        project.points_db[pt.id] = pt

    raw_corridors = data.get("corridors", [])
    for idx, corr in enumerate(raw_corridors):
        if isinstance(corr, dict):
            c_obj = CorridorSegment(
                segment_id=int(corr.get("id", idx)),
                start_node_id=int(corr["start_node_id"]),
                end_node_id=int(corr["end_node_id"]),
                floor=int(corr.get("floor", 1)),
            )
        elif isinstance(corr, (list, tuple)):
            start_id, end_id = int(corr[0]), int(corr[1])
            fl = project.points_db[start_id].floor if start_id in project.points_db else 1
            c_obj = CorridorSegment(
                segment_id=idx,
                start_node_id=start_id,
                end_node_id=end_id,
                floor=fl,
            )
        else:
            continue
        project.corridors.append(c_obj)

    base_dir = os.path.dirname(os.path.abspath(file_path))
    raw_images = data.get("floor_images", {})
    for k, v in raw_images.items():
        if v:
            # Преобразуем обратные слэши из Windows в нормализованные пути
            normalized_rel_path = os.path.normpath(v)
            full_img_path = (
                normalized_rel_path
                if os.path.isabs(normalized_rel_path)
                else os.path.join(base_dir, normalized_rel_path)
            )
            project.floor_image_paths[int(k)] = full_img_path

    return project