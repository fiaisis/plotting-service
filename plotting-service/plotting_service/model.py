from pydantic import BaseModel


class Metadata(BaseModel):
    filename: str
    shape: int
    x_axis_label: str
    x_axis_min: float
    x_axis_max: float
    y_axis_label: str
    y_axis_min: float
    y_axis_max: float