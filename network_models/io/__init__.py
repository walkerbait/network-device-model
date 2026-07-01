"""Opt-in ingestion layer for the authorization package (SCAP/XCCDF, CCI list).

This subpackage is deliberately **not** imported by ``network_models`` or
``network_models.system`` — importing the core stays pydantic-only and free of
any XML dependency. Import from here explicitly when you need ingestion::

    from network_models.io import parse_xccdf_results, parse_cci_list

Install the ``io`` extra (``pip install network-device-model[io]``) to parse
untrusted content with ``defusedxml`` hardening; otherwise the stdlib XML parser
is used as a fallback (XXE-safe but not DoS-hardened — see ``io._xml``).
"""

from network_models.io.cci import *  # noqa: F401,F403
from network_models.io.cci import __all__ as _cci_all
from network_models.io.consistency import *  # noqa: F401,F403
from network_models.io.consistency import __all__ as _consistency_all
from network_models.io.scap import *  # noqa: F401,F403
from network_models.io.scap import __all__ as _scap_all

__all__ = list(_scap_all) + list(_cci_all) + list(_consistency_all)
