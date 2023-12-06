# This file is part of the faebryk project
# SPDX-License-Identifier: MIT

"""
This file contains a faebryk sample.
Faebryk samples demonstrate the usage by building example systems.
This particular sample creates a netlist with an led and a nand ic
    that creates some logic.
The goal of this sample is to show how to structurize your system design in modules.
Thus this is a netlist sample.
Netlist samples can be run directly.
"""
import logging

import typer
from faebryk.core.core import Module, Parameter
from faebryk.core.util import get_all_nodes
from faebryk.exporters.netlist.graph import attach_nets_and_kicad_info
from faebryk.exporters.netlist.kicad.netlist_kicad import from_faebryk_t2_netlist
from faebryk.exporters.netlist.netlist import make_t2_netlist_from_graph
from faebryk.library.can_attach_to_footprint import can_attach_to_footprint
from faebryk.library.can_attach_to_footprint_via_pinmap import (
    can_attach_to_footprint_via_pinmap,
)
from faebryk.library.Constant import Constant
from faebryk.library.Electrical import Electrical
from faebryk.library.ElectricPower import ElectricPower
from faebryk.library.has_simple_value_representation_defined import (
    has_simple_value_representation_defined,
)
from faebryk.library.KicadFootprint import KicadFootprint
from faebryk.library.LED import LED
from faebryk.library.MOSFET import MOSFET
from faebryk.library.Resistor import Resistor
from faebryk.library.SMDTwoPin import SMDTwoPin
from faebryk.library.Switch import Switch
from faebryk.library.TBD import TBD
from faebryk.libs.experiments.buildutil import export_graph, export_netlist
from faebryk.libs.logging import setup_basic_logging

logger = logging.getLogger(__name__)


class Battery(Module):
    def __init__(self) -> None:
        super().__init__()

        class _IFs(Module.IFS()):
            power = ElectricPower()

        self.IFs = _IFs(self)
        self.voltage: Parameter = TBD()


class LED_Indicator(Module):
    def __init__(self) -> None:
        super().__init__()

        class _IFS(Module.IFS()):
            input_power = ElectricPower()
            input_control = Electrical()

        class _NODES(Module.NODES()):
            led = LED()
            current_limiting_resistor = Resistor(TBD())
            switch = MOSFET(
                MOSFET.ChannelType.N_CHANNEL, MOSFET.SaturationType.ENHANCEMENT
            )

        self.IFs = _IFS(self)
        self.NODEs = _NODES(self)

        # fabric
        self.NODEs.led.IFs.cathode.connect_via(
            self.NODEs.current_limiting_resistor, self.IFs.input_power.NODEs.lv
        )
        self.NODEs.led.IFs.anode.connect(self.NODEs.switch.IFs.drain)

        self.NODEs.switch.IFs.source.connect(self.IFs.input_power.NODEs.hv)
        self.NODEs.switch.IFs.gate.connect(self.IFs.input_control)


class LogicSwitch(Module):
    def __init__(self) -> None:
        super().__init__()

        class _IFS(Module.IFS()):
            input_power = ElectricPower()
            output_control = Electrical()

        class _NODES(Module.NODES()):
            switch = Switch(Electrical)()
            pull_down_resistor = Resistor(TBD())

        self.IFs = _IFS(self)
        self.NODEs = _NODES(self)

        # fabric
        self.IFs.input_power.NODEs.hv.connect_via(
            self.NODEs.switch, self.IFs.output_control
        )
        self.IFs.input_power.NODEs.lv.connect_via(
            self.NODEs.pull_down_resistor, self.IFs.output_control
        )


class App(Module):
    def __init__(self) -> None:
        super().__init__()

        class _IFS(Module.IFS()):
            pass

        class _NODES(Module.NODES()):
            battery = Battery()
            led_ind = LED_Indicator()
            switch = LogicSwitch()

        self.IFs = _IFS(self)
        self.NODEs = _NODES(self)

        # fabric
        power = self.NODEs.battery.IFs.power

        power.connect(self.NODEs.led_ind.IFs.input_power)
        power.connect(self.NODEs.switch.IFs.input_power)
        self.NODEs.switch.IFs.output_control.connect(
            self.NODEs.led_ind.IFs.input_control
        )

        # parametrizing
        for node in get_all_nodes(self, order_types=[Battery, LED, LED_Indicator]):
            if isinstance(node, Battery):
                node.voltage = Constant(5)

            if isinstance(node, LED):
                node.set_forward_parameters(
                    voltage_V=Constant(2.4), current_A=Constant(0.020)
                )

            if isinstance(node, LED_Indicator):
                assert isinstance(self.NODEs.battery.voltage, Constant)
                node.NODEs.current_limiting_resistor.set_resistance(
                    node.NODEs.led.get_trait(
                        LED.has_calculatable_needed_series_resistance
                    ).get_needed_series_resistance_ohm(self.NODEs.battery.voltage.value)
                )

            if isinstance(node, LogicSwitch):
                node.NODEs.pull_down_resistor.set_resistance(Constant(100_000))

        # packaging
        for node in get_all_nodes(self):
            if isinstance(node, Battery):
                node.add_trait(
                    can_attach_to_footprint_via_pinmap(
                        {"1": node.IFs.power.NODEs.hv, "2": node.IFs.power.NODEs.lv}
                    )
                ).attach(
                    KicadFootprint.with_simple_names(
                        "Battery:BatteryHolder_ComfortableElectronic_CH273-2450_1x2450",
                        2,
                    )
                )
                node.add_trait(has_simple_value_representation_defined("B"))

            if isinstance(node, Resistor):
                node.get_trait(can_attach_to_footprint).attach(
                    SMDTwoPin(SMDTwoPin.Type._0805)
                )

            if isinstance(node, Switch(Electrical)):
                node.get_trait(can_attach_to_footprint).attach(
                    KicadFootprint.with_simple_names(
                        "Button_Switch_SMD:Panasonic_EVQPUJ_EVQPUA", 2
                    )
                )

            if isinstance(node, LED):
                node.add_trait(
                    can_attach_to_footprint_via_pinmap(
                        {"1": node.IFs.anode, "2": node.IFs.cathode}
                    )
                ).attach(SMDTwoPin(SMDTwoPin.Type._0805))

            if isinstance(node, MOSFET):
                node.add_trait(
                    can_attach_to_footprint_via_pinmap(
                        {
                            "1": node.IFs.drain,
                            "2": node.IFs.gate,
                            "3": node.IFs.source,
                        }
                    )
                ).attach(
                    KicadFootprint.with_simple_names("Package_TO_SOT_SMD:SOT-23", 3)
                )


def main(make_graph: bool = True):
    logger.info("Building app")
    app = App()

    # make graph
    logger.info("Make graph")
    G = app.get_graph()

    logger.info("Make netlist")
    attach_nets_and_kicad_info(G)
    t2 = make_t2_netlist_from_graph(G)
    netlist = from_faebryk_t2_netlist(t2)

    export_netlist(netlist)

    if make_graph:
        logger.info("Make render")
        export_graph(G.G, show=True)


# Boilerplate -----------------------------------------------------------------
if __name__ == "__main__":
    setup_basic_logging()
    logger.info("Running experiment")

    typer.run(main)
