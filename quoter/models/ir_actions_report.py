# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl-3.0.html)

from odoo import models

QUOTER_QUOTATION_REPORT_NAME = "quoter.report_quoter_quotation_document"
_QUOTER_UTF8_META = b'<meta http-equiv="Content-Type" content="text/html; charset=utf-8"/>'
_QUOTER_UTF8_META_STR = _QUOTER_UTF8_META.decode("ascii")


class IrActionsReport(models.Model):
    _inherit = "ir.actions.report"

    def _build_wkhtmltopdf_args(
        self,
        paperformat_id,
        landscape,
        specific_paperformat_args=None,
        set_viewport_size=False,
    ):
        """wkhtmltopdf asume Latin-1 si no se indica codificación; rompe tildes en PDF."""
        command_args = super()._build_wkhtmltopdf_args(
            paperformat_id,
            landscape,
            specific_paperformat_args=specific_paperformat_args,
            set_viewport_size=set_viewport_size,
        )
        if "--encoding" not in command_args:
            command_args.extend(["--encoding", "utf-8"])
        return command_args

    def _render_qweb_html(self, res_ids, data=None):
        html, report_type = super()._render_qweb_html(res_ids, data=data)
        if self.report_name == QUOTER_QUOTATION_REPORT_NAME:
            html = self._quoter_inject_utf8_charset(html)
        return html, report_type

    def _quoter_inject_utf8_charset(self, html):
        if not html:
            return html
        if isinstance(html, bytes):
            sample = html[:4096].lower()
            if b"charset=utf-8" in sample:
                return html
            if b"<head>" in html:
                return html.replace(b"<head>", b"<head>" + _QUOTER_UTF8_META, 1)
            return _QUOTER_UTF8_META + html
        text = html
        if "charset=utf-8" in text[:4096].lower():
            return text
        if "<head>" in text:
            return text.replace("<head>", "<head>%s" % _QUOTER_UTF8_META_STR, 1)
        return "%s%s" % (_QUOTER_UTF8_META_STR, text)
