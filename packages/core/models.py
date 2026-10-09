from enum import Enum
from PyQt5.QtCore import QPointF


class PointType(Enum):
    REGULAR = "corridor_node"
    ROOM = "room"
    STAIR = "stair"
    ELEVATOR = "elevator"


class CorridorSegment:
    """Модель отрезка коридора между двумя узлами."""

    def __init__(self, segment_id: int, start_node_id: int, end_node_id: int, floor: int = 1):
        self.id = segment_id
        self.start_node_id = start_node_id
        self.end_node_id = end_node_id
        self.floor = floor


class MapPoint:
    """Модель точки на карте (кабинет, перекресток, лестница, лифт)."""

    def __init__(
            self,
            point_id: int,
            name: str,
            coords: QPointF,
            floor: int = 1,
            point_type: PointType = PointType.REGULAR,
    ):
        self.id = point_id
        self.name = name
        self.alias = ""
        self.coords = coords
        self.floor = floor
        self.point_type = point_type
        self.is_favorite = False
        self.label_offset = QPointF(0.0, 0.0)
        self.font_size = 10

    @classmethod
    def from_dict(cls, data: dict) -> "MapPoint":
        # 1. Определение типа точки
        raw_type = str(data.get("point_type", "")).lower()
        p_type = PointType.REGULAR

        type_mapping = {
            "corridor_node": PointType.REGULAR,
            "обычная": PointType.REGULAR,
            "room": PointType.ROOM,
            "кабинет/дверь": PointType.ROOM,
            "stair": PointType.STAIR,
            "лестница": PointType.STAIR,
            "elevator": PointType.ELEVATOR,
            "лифт": PointType.ELEVATOR,
        }
        p_type = type_mapping.get(raw_type, PointType.REGULAR)

        # 2. Извлечение координат (поддержка списков [x, y] и словарей)
        raw_coords = data.get("coords")
        if isinstance(raw_coords, (list, tuple)) and len(raw_coords) >= 2:
            x_val, y_val = float(raw_coords[0]), float(raw_coords[1])
        else:
            x_val = float(data.get("x", 0.0))
            y_val = float(data.get("y", 0.0))

        pt = cls(
            point_id=int(data["id"]),
            name=str(data.get("name", "")),
            coords=QPointF(x_val, y_val),
            floor=int(data.get("floor", 1)),
            point_type=p_type,
        )
        pt.alias = str(data.get("alias", ""))
        pt.is_favorite = bool(data.get("is_favorite", False))

        # 3. Смещение метки (поддержка списка [x, y] и ключей label_offset_x/y)
        raw_offset = data.get("label_offset")
        if isinstance(raw_offset, (list, tuple)) and len(raw_offset) >= 2:
            pt.label_offset = QPointF(float(raw_offset[0]), float(raw_offset[1]))
        else:
            pt.label_offset = QPointF(
                float(data.get("label_offset_x", 0.0)),
                float(data.get("label_offset_y", 0.0)),
            )

        pt.font_size = int(data.get("font_size", 10))
        return pt