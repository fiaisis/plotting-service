"""
Module containing the mari plot strategy
"""

from pathlib import Path

from plotting_service.model import Plot
from plotting_service.strategies.base import PlotStrategy


class MariStrategy(PlotStrategy):
    """The Mari Plot Strategy"""

    def generate_plot_data(self, nexus_file: Path) -> Plot:
        pass
