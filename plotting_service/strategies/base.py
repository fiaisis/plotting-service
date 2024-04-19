"""
The Base Strategy to be implemented per instrument.
"""

from abc import ABC, abstractmethod
from pathlib import Path

from plotting_service.model import Plot


class PlotStrategy(ABC):
    """
    Abstract Plot Strategy to be implemented per instrument, defining the plot building strategy.
    """

    @abstractmethod
    def generate_plot_data(self, nexus_file: Path) -> Plot:
        """
        Generate the plot data for the given nexus file
        :return:
        """
