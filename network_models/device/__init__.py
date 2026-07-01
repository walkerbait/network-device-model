"""Reusable device *type* definitions (Nautobot devicetype-library + NaC aligned)."""

from network_models.device.vocab import *  # noqa: F401,F403
from network_models.device.vocab import __all__ as _vocab_all
from network_models.device.components import *  # noqa: F401,F403
from network_models.device.components import __all__ as _components_all
from network_models.device.definition import *  # noqa: F401,F403
from network_models.device.definition import __all__ as _definition_all

__all__ = list(_vocab_all) + list(_components_all) + list(_definition_all)
