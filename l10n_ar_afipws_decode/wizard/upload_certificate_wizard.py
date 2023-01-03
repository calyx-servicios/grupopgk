from odoo import models
import base64


class L10nArAfipwsUploadCertificate(models.TransientModel):
    _inherit = "afipws.upload_certificate.wizard"
    
    def action_confirm(self):
        self.ensure_one()
        self.certificate_id.write({"crt": base64.decodebytes(self.certificate_file)})
        self.certificate_id.action_confirm()
        return True