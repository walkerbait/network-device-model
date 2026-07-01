"""Portable, strictly-validated Pydantic models for network device definitions
and deployed systems.

Self-contained: depends only on ``pydantic>=2.5`` and the standard library, so it
can be vendored in this repository or extracted into its own shared package/repo
without change.

The package is organized into two domains, each importable as a subpackage or
directly from the top level:

* ``network_models.device``  — reusable device *type* definitions
  (Nautobot devicetype-library + Cisco NaC aligned).
* ``network_models.system``  — deployed *system* topology (enclaves, components,
  connections), Layer-2 config (VLANs, switchports), and the RMF/OpenRMF
  authorization package (evaluated checklists, 800-53 controls, POA&M, scoring).

Shared building blocks live in ``network_models.base`` (``StrictModel``) and
``network_models._enum`` (the ``_str_enum`` helper). Ingestion helpers (SCAP/XCCDF
and DISA CCI parsers) live in the opt-in ``network_models.io`` layer, which the
core does not import so ``import network_models`` stays pydantic-only.
"""

from network_models.base import StrictModel  # noqa: F401
from network_models.device import *  # noqa: F401,F403
from network_models.device import __all__ as _device_all
from network_models.system import *  # noqa: F401,F403
from network_models.system import __all__ as _system_all
from network_models.stig import *  # noqa: F401,F403
from network_models.stig import __all__ as _stig_all

__all__ = ["StrictModel"] + list(_device_all) + list(_system_all) + list(_stig_all)

__version__ = "0.2.0"
