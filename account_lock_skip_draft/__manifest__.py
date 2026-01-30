# -*- coding: utf-8 -*-
# Copyright 2024 Grupo PGK
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

{
    "name": "Account Lock Skip Draft Entries",
    "version": "15.0.1.0.0",
    "category": "Accounting",
    "summary": "Permite bloquear períodos sin validar asientos en borrador",
    "description": """
        Este módulo modifica el comportamiento de bloqueo de períodos fiscales:
        - Elimina la validación que impide bloquear si existen asientos en borrador
        - Mantiene la validación de líneas de extracto bancario no conciliadas
        - Aplica tanto para campos estándar como para los del módulo OCA account_lock_to_date
    """,
    "author": "Grupo PGK",
    "license": "AGPL-3",
    "depends": ["account_lock_to_date"],
    "data": [],
    "installable": True,
    "auto_install": False,
}
