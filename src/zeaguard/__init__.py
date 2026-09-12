"""ZeaGuard dry lab helpers.

Importing this package must not pull in third-party dependencies. The
reproducibility gate (:mod:`zeaguard.repro`) needs to load and run inside a
broken environment in order to diagnose it.
"""

__all__ = ["nb01_identity", "nb01_inputs", "repro"]
__version__ = "0.0.1"
