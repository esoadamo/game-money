from typing import TypedDict, List, Optional


class Good(TypedDict):
    name: str
    color: Optional[str]
    value: float


class LocalPlayer(TypedDict):
    name: str
    infinite: bool
    goods: List[Good]


class GameStatus(TypedDict):
    name: str
    players: List[LocalPlayer]
