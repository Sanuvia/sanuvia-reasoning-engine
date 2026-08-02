"""Sanuvia application layer.

Use cases and capabilities expressed only against *ports* (interfaces). This
layer knows *what* must happen; it never knows *where* state lives or *which*
foundation model is used. All infrastructure is injected as an implementation of
a port defined in ``sanuvia.application.ports``.

In this increment the ports are defined; the reasoning logic that orchestrates
them (the Core Loop, the Model Revision engine) is a later increment.
"""
