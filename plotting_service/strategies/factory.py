"""module containing the factory function for strategies"""

from plotting_service.exceptions import MissingStrategyError
from plotting_service.strategies.base import PlotStrategy
from plotting_service.strategies.mari import MariStrategy
from plotting_service.strategies.tosca import ToscaStrategy


def get_strategy_for_instrument(instrument: str) -> PlotStrategy:
    """
    Given an instrument name, return the instruments plotting strategy
    :param instrument: the instrument name
    :return: The plot strategy for the instrument
    """
    match instrument.lower():
        case "mari":
            return MariStrategy()
        case "tosca":
            return ToscaStrategy()
        case _:
            raise MissingStrategyError(f"No strategy implemented for instrument: {instrument}")
