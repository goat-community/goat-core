from typing import List, Optional
from pydantic import BaseModel, validator
from src.resources.enums import ReturnType
from enum import Enum
from uuid import UUID


class CountLimitPerTool(int, Enum):
    oev_gueteklasse = 1000


class AreaLimitPerTool(int, Enum):
    oev_gueteklasse = 50  # in degree


class StationConfig(BaseModel):
    groups: dict
    time_frequency: List[int]
    categories: List[dict]
    classification: dict


class CalculateOevGueteklassenParameters(BaseModel):
    project_id: UUID = None
    start_time: int = 25200
    end_time: int = 32400
    weekday: int = 1
    reference_area: UUID  # UUID of layers
    station_config: StationConfig

    @validator("start_time", "end_time")
    def seconds_validator(cls, v):
        if v < 0 or v > 86400:
            raise ValueError("Should be between or equal to 0 and 86400")
        return v

    @validator("weekday")
    def weekday_validator(cls, v):
        if v < 1 or v > 7:
            raise ValueError("weekday should be between or equal to 1 and 7")
        return v


station_config_example = {
    "groups": {
        "0": "B",  # tram
        "1": "A",  # metro
        "2": "A",  # train
        "3": "A",  # bus
        "100": "A",  # rail
        "101": "A",  # highspeed train
        "102": "A",  # long distance train
        "103": "A",  # interregional train
        "105": "A",  # car sleeper train
        "106": "A",  # regional train
        "109": "A",  # suburban train
        "402": "A",  # underground service
        "700": "C",  # bus service
        "704": "C",  # local bus service
        "715": "C",  # demand and response bus service
        "900": "B",  # tram
    },
    "time_frequency": [0, 4, 10, 19, 39, 60, 119],
    "categories": [
        {
            "A": 1,  # i.e. types of transports in category A are in transport stop category I
            "B": 1,
            "C": 2,
        },
        {"A": 1, "B": 2, "C": 3},
        {"A": 2, "B": 3, "C": 4},
        {"A": 3, "B": 4, "C": 5},
        {"A": 4, "B": 5, "C": 6},
        {"A": 5, "B": 6, "C": 6},
    ],
    "classification": {
        "1": {300: "1", 500: "1", 750: "2", 1000: "3"},
        "2": {300: "1", 500: "2", 750: "3", 1000: "4"},
        "3": {300: "2", 500: "3", 750: "4", 1000: "5"},
        "4": {300: "3", 500: "4", 750: "5", 1000: "6"},
        "5": {300: "4", 500: "5", 750: "6"},
        "6": {300: "5", 500: "6"},
        "7": {300: "6"},
    },
}

oev_gueteklasse_config_example = {
    "start_time": 21600,
    "end_time": 72000,
    "weekday": 1,
    "reference_area": "4640df23-539d-4e5b-9d63-0db494b9a9b5",
    "station_config": station_config_example,
}