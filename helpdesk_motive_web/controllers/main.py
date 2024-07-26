import logging
import base64
import werkzeug
import odoo.http as http
from odoo.http import request
from odoo.tools import plaintext2html

from odoo.addons.helpdesk_mgmt.controllers.main import HelpdeskTicketController
#from odoo.addons.yourmodulename.controllers.yourpythonfilename import warehouse


_logger = logging.getLogger(__name__)

class HelpdeskTicketControllerInherit(HelpdeskTicketController):

    def _prepare_submit_ticket_vals(self, **kw):
        res = super(HelpdeskTicketControllerInherit, self)._prepare_submit_ticket_vals(**kw)
        lista = ['team', 'category', 'subject', 'description', 'attachment']
        for key,value in res.items():
            if key in lista:
                continue
            
            res['description'] += f'{key}: {value}'
            kw.pop(key)
        return res

    @http.route("/new/ticket", type="http", auth="user", website=True)
    def create_new_ticket(self, **kw):
        session_info = http.request.env["ir.http"].session_info()
        company = request.env.company
        category_model = http.request.env["helpdesk.ticket.category"]
        categories = category_model.with_company(company.id).search(
            [("active", "=", True)]
        )
        email = http.request.env.user.email
        name = http.request.env.user.name
        company = request.env.company
        # Obtener line_ids
        line_ids = request.env['helpdesk.ticket.motive.line'].sudo().search([('team_id.show_in_portal', '=', True),('required_field', '=', True)])
        
        return http.request.render(
            "helpdesk_mgmt.portal_create_ticket",
            {
                "categories": categories,
                "teams": self._get_teams(),
                "email": email,
                "name": name,
                "ticket_team_id_required": (
                    company.helpdesk_mgmt_portal_team_id_required
                ),
                "ticket_category_id_required": (
                    company.helpdesk_mgmt_portal_category_id_required
                ),
                "max_upload_size": session_info["max_file_upload_size"],
                "line_ids": line_ids,  # Pasar line_ids al template
            },
        )

