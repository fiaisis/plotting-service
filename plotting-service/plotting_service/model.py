from pydantic import BaseModel


class Metadata(BaseModel):
    filename: str
    shape: int
    axes_labels: dict
    x_axis_min: float
    x_axis_max: float
    y_axis_min: float
    y_axis_max: float
