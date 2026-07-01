"""Device component models (Nautobot devicetype-library compatible).

Each component (interface, console/power port, bay, etc.) is a physical building
block of a :class:`~network_models.device.definition.DeviceDefinition`.
"""

from __future__ import annotations

import re
from typing import Optional

from pydantic import Field, StrictBool, StrictInt, field_validator, model_validator

from network_models.base import StrictModel
from network_models.device.vocab import (
    ConsolePortType,
    ConsoleServerPortType,
    FeedLeg,
    InterfaceType,
    PassthroughPortType,
    PoEMode,
    PoEType,
    PowerOutletType,
    PowerPortType,
)


class Interface(StrictModel):
    name: str = Field(..., min_length=1)
    type: InterfaceType
    label: Optional[str] = None
    description: Optional[str] = None
    mgmt_only: StrictBool = False
    poe_mode: Optional[PoEMode] = None
    poe_type: Optional[PoEType] = None

    @model_validator(mode="after")
    def _poe_type_requires_pse(self) -> "Interface":
        if self.poe_type is not None and self.poe_mode is None:
            raise ValueError("poe_type requires poe_mode to be set")
        return self


class ConsolePort(StrictModel):
    name: str = Field(..., min_length=1)
    type: ConsolePortType
    label: Optional[str] = None
    description: Optional[str] = None
    poe: StrictBool = False


class ConsoleServerPort(StrictModel):
    name: str = Field(..., min_length=1)
    type: ConsoleServerPortType
    label: Optional[str] = None
    description: Optional[str] = None


class PowerPort(StrictModel):
    name: str = Field(..., min_length=1)
    type: PowerPortType
    label: Optional[str] = None
    description: Optional[str] = None
    maximum_draw: Optional[StrictInt] = Field(None, gt=0, description="Maximum draw (watts)")
    allocated_draw: Optional[StrictInt] = Field(None, gt=0, description="Allocated draw (watts)")

    @model_validator(mode="after")
    def _allocated_le_maximum(self) -> "PowerPort":
        if (
            self.maximum_draw is not None
            and self.allocated_draw is not None
            and self.allocated_draw > self.maximum_draw
        ):
            raise ValueError("allocated_draw cannot exceed maximum_draw")
        return self


class PowerOutlet(StrictModel):
    name: str = Field(..., min_length=1)
    type: PowerOutletType
    label: Optional[str] = None
    description: Optional[str] = None
    power_port: Optional[str] = Field(None, description="Name of the feeding power_port")
    feed_leg: Optional[FeedLeg] = None


class FrontPort(StrictModel):
    name: str = Field(..., min_length=1)
    type: PassthroughPortType
    label: Optional[str] = None
    description: Optional[str] = None
    color: Optional[str] = Field(None, description="6-digit hex RGB, no '#'")
    rear_port: str = Field(..., description="Name of the mapped rear_port")
    rear_port_position: StrictInt = Field(1, ge=1)

    @field_validator("color")
    @classmethod
    def _valid_hex_color(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and not re.fullmatch(r"[0-9a-fA-F]{6}", v):
            raise ValueError("color must be a 6-digit hex RGB value (e.g. 'aa1409')")
        return v.lower() if v else v


class RearPort(StrictModel):
    name: str = Field(..., min_length=1)
    type: PassthroughPortType
    label: Optional[str] = None
    description: Optional[str] = None
    color: Optional[str] = Field(None, description="6-digit hex RGB, no '#'")
    positions: StrictInt = Field(1, ge=1)
    poe: StrictBool = False

    @field_validator("color")
    @classmethod
    def _valid_hex_color(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and not re.fullmatch(r"[0-9a-fA-F]{6}", v):
            raise ValueError("color must be a 6-digit hex RGB value (e.g. 'aa1409')")
        return v.lower() if v else v


class DeviceBay(StrictModel):
    name: str = Field(..., min_length=1)
    label: Optional[str] = None
    description: Optional[str] = None


class ModuleBay(StrictModel):
    name: str = Field(..., min_length=1)
    label: Optional[str] = None
    description: Optional[str] = None
    position: Optional[str] = None


class InventoryItem(StrictModel):
    name: str = Field(..., min_length=1)
    label: Optional[str] = None
    description: Optional[str] = None
    manufacturer: Optional[str] = None
    part_id: Optional[str] = None


__all__ = [
    "Interface", "ConsolePort", "ConsoleServerPort", "PowerPort",
    "PowerOutlet", "FrontPort", "RearPort", "DeviceBay", "ModuleBay",
    "InventoryItem",
]
