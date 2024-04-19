"""Module containing the main plot creation logic"""

from pathlib import Path

from plotting_service.model import Plot
from plotting_service.strategies.base import PlotStrategy


class PlotMaker:
    """
    Plot Maker builds plots based on the given strategy
    """

    def __init__(self, strategy: PlotStrategy) -> None:
        self._strategy = strategy

    def create_plot(self, nexus_filename: Path) -> Plot:
        """
        Given a nexus filename, generate its plot.
        :param nexus_filename: The nexus filename
        :return: The generated plot
        """
        complete_path = find_nexus_file(nexus_filename)
        return self._strategy.generate_plot_data(complete_path)


def find_nexus_file(nexus_filename: Path) -> Path:
    """
    Given a nexus filename, find the complete nexus file path and return it
    :param nexus_filename: The nexus filename
    :return: The complete nexus filepath
    """
