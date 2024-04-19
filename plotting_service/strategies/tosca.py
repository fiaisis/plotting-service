"""
Module for tosca plotting strategy
"""

from pathlib import Path

from plotting_service.model import Plot
from plotting_service.strategies.base import PlotStrategy


class ToscaStrategy(PlotStrategy):
    """
    Tosca Plot Strategy
    """

    def generate_plot_data(self, nexus_file: Path) -> Plot:
        pass
