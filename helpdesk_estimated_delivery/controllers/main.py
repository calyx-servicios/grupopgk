from odoo import _

from odoo.addons.helpdesk_mgmt.controllers.myaccount import CustomerPortalHelpdesk


class CustomerPortalHelpdeskEstimated(CustomerPortalHelpdesk):
    """Extiende el controlador del portal para agregar ordenamiento por fecha estimada."""

    def _ticket_get_searchbar_sortings(self):
        """Añade opción de ordenamiento 'Próximo a entregar'."""
        sortings = super()._ticket_get_searchbar_sortings()
        sortings["estimated_delivery"] = {
            "label": _("Próximo a entregar"),
            "order": "estimated_delivery_date asc, create_date desc",
            "sequence": 5,
        }
        return sortings
