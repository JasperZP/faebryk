import logging
from abc import abstractmethod
from faebryk.core.core import Module, ModuleTrait, Parameter
from dataclasses import dataclass, field
from faebryk.libs.units import m
from faebryk.library.Constant import Constant
from faebryk.library.TBD import TBD
from faebryk.library.has_datasheet_defined import has_datasheet_defined
from faebryk.library.ElectricPower import ElectricPower
from faebryk.library.has_esphome_config import has_esphome_config, is_esphome_bus
from faebryk.library.has_single_electric_reference import has_single_electric_reference
from faebryk.library.UART_Base import UART_Base
from faebryk.core.graph import Graph
from faebryk.core.util import get_all_nodes_graph
from typing import Callable, Any
import yaml

logger = logging.getLogger(__name__)


# TODO move to util
def dict_map_values(d: dict, function: Callable[[Any], Any]) -> dict:
    """recursively map all values in a dict"""

    result = {}
    for key, value in d.items():
        if isinstance(value, dict):
            result[key] = dict_map_values(value, function)
        elif isinstance(value, list):
            result[key] = [dict_map_values(v, function) for v in value]
        else:
            result[key] = function(value)
    return result


def merge_dicts(*dicts: dict) -> dict:
    """merge a list of dicts into a single dict,
    if same key is present and value is list, lists are merged
    if same key is dict, dicts are merged recursively
    """
    result = {}
    for d in dicts:
        for k, v in d.items():
            if k in result:
                if isinstance(v, list):
                    assert isinstance(result[k], list)
                    result[k] += v
                elif isinstance(v, dict):
                    assert isinstance(result[k], dict)
                    result[k] = merge_dicts(result[k], v)
                else:
                    result[k] = v
            else:
                result[k] = v
    return result


def make_esphome_config(G: Graph) -> dict:
    esphome_components = {
        n for n in get_all_nodes_graph(G.G) if n.has_trait(has_esphome_config)
    }

    esphome_config = merge_dicts(
        *[
            comp.get_trait(has_esphome_config).get_config()
            for comp in esphome_components
        ]
    )

    def instantiate_param(param: Parameter | Any):
        if not isinstance(param, Parameter):
            return param

        if not isinstance(param, Constant):
            raise Exception(
                f"Parameter {param} is not a Constant, but {type(param)}"
                f"Config: {esphome_config}"
            )
        return param.value

    instantiated = dict_map_values(esphome_config, instantiate_param)

    return instantiated


def dump_esphome_config(config: dict) -> str:
    return yaml.dump(config)