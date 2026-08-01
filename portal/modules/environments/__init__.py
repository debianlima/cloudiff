"""environments module: Operações de produção: janela de mudança, alertas e ciclo de incidentes.

Register via portal.wiring only after the permission table (A2) and service
tests (A5) pass. Removing the register call returns these routes to the legacy
adapter with no redeploy (A8).
"""
from portal.modules.environments.routes import endpoints

__all__ = ["endpoints"]
