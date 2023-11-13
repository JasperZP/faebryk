# This file is part of the faebryk project
# SPDX-License-Identifier: MIT

from faebryk.core.core import ModuleInterface, Parameter
from faebryk.library.TBD import TBD
from faebryk.library.Constant import Constant
from faebryk.library.ElectricLogic import ElectricLogic
from faebryk.library.has_single_electric_reference_defined import (
    has_single_electric_reference_defined,
)


class UART_Base(ModuleInterface):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)

        class NODES(ModuleInterface.NODES()):
            rx = ElectricLogic()
            tx = ElectricLogic()

        self.NODEs = NODES(self)

        ref = ElectricLogic.connect_all_module_references(self)
        self.add_trait(has_single_electric_reference_defined(ref))

        self.baud = TBD()

    def set_baud(self, baud: Parameter):
        self.baud = baud

    def connect(self, other: "UART_Base"):
        super().connect(other)

        baud = self.baud.resolve(other.baud)
        other.set_baud(baud)
        self.set_baud(baud)
