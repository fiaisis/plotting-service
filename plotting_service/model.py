"""
Module containing the plot classes
Every class is based on the client api for the plotly react library.
For a closer look, see https://plotly.com/javascript/react/
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Dict, Any

from pydantic import BaseModel


@dataclass
class PlotData:
    """
    PlotData defines the plotly data
    """

    x: List[float]
    y: List[float]
    type: str
    error_y: Optional[PlotErrors]
    error_x: Optional[PlotErrors]
    additional_configuration: Dict[str, Any]


@dataclass
class PlotErrors:
    """
    PlotErrors defines the error bars for a plot
    """

    type: str
    array: Optional[List[float]]
    value: Optional[float]
    arrayminus: Optional[List[float]]


@dataclass
class AxisLayout:
    """
    AxisLayout defines the numerical layout only of a single plot axis. It is not for render specific layout such as
    pixel width.
    """

    tickmode: str
    tickvals: Optional[List[float]] = None
    ticktext: Optional[List[str]] = None
    tick0: Optional[float] = None
    dtick: Optional[float] = None


@dataclass
class PlotLayout:
    """
    PlotLayout defines the 2 axis layouts for a single plot, but not for render specific layout such as title, width,
    and height.
    """

    xaxis: Optional[AxisLayout] = None
    yaxis: Optional[AxisLayout] = None


class Plot(BaseModel):
    """
    Plot class contains all the numerical data for a single plotly plot
    """

    data: PlotData
    layout: PlotLayout
