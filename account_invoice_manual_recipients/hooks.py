def post_init_hook(cr, registry):
    """Keep invoice email mail.mail records after sending so failed/succeeded
    sends stay visible in Discuss > Correos electrónicos for auditing."""
    from odoo import api

    env = api.Environment(cr, api.SUPERUSER_ID, {})
    template_xmlids = [
        "account.email_template_edi_invoice",
        "invoice_without_detail.email_template_invoice_without_detail",
    ]
    for xmlid in template_xmlids:
        template = env.ref(xmlid, raise_if_not_found=False)
        if template:
            template.auto_delete = False
