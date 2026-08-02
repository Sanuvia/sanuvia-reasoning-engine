"""Adapters — concrete implementations of application ports.

Adapters may depend on the domain and the application's ports; nothing in the
domain or application depends on an adapter. Cloud-specific or framework-specific
code, if any, lives here only. Swapping a deployment target (cloud <-> self-
hosted) is an adapter change with no effect on the reasoning engine.
"""
