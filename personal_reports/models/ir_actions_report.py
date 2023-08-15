import json
import logging
import time

from odoo import http
from odoo.addons.web.controllers.main import ReportController
from odoo.http import content_disposition, request
from odoo.http import serialize_exception as _serialize_exception
from odoo.tools import html_escape
from odoo.tools.safe_eval import safe_eval
from werkzeug.urls import url_decode

personal_reports = [
    "personal_reports.payment_subledger_report",
    "personal_reports.payment_subledger_report_txt",
    "personal_reports.invoicing_subledger_report",
    "personal_reports.invoicing_subledger_report_txt",
]


class ReportControllerPePa(ReportController):
    @http.route(["/report/download"], type="http", auth="user")
    def report_download(self, data, token, context=None):
        """This function is used by 'action_manager_report.js' in order to trigger the download of
        a pdf/controller report.

        :param data: a javascript array JSON.stringified containg report internal url ([0]) and
        report_type [1]
        :returns: Response with a filetoken cookie and an attachment header
        """
        requestcontent = json.loads(data)
        url, report_type = requestcontent[0], requestcontent[1]
        if report_type not in ["qweb-pdf", "qweb-text"]:
            return
        try:
            extension, reportname, response, data_context, docids = self.get_response(
                context, url, report_type
            )

            report = request.env["ir.actions.report"]._get_report_from_name(reportname)
            filename = "%s.%s" % (report.name, extension)

            # add this:
            if reportname in personal_reports:
                docids = data_context.get("active_id")
                if docids:
                    docids = str(docids)
            # ---------
            if docids:
                ids = [int(x) for x in docids.split(",")]
                obj = request.env[report.model].browse(ids)
                if report.print_report_name and not len(obj) > 1:
                    report_name = safe_eval(report.print_report_name, {"object": obj, "time": time})
                    filename = "%s.%s" % (report_name, extension)

            response.headers.add("Content-Disposition", content_disposition(filename))
            response.set_cookie("fileToken", token)
            return response
        except Exception as e:
            se = _serialize_exception(e)
            error = {"code": 200, "message": "Odoo Server Error", "data": se}
            return request.make_response(html_escape(json.dumps(error)))

    def get_response(self, context, url, report_type):
        converter = "pdf" if report_type == "qweb-pdf" else "text"
        extension = "pdf" if report_type == "qweb-pdf" else "txt"

        pattern = "/report/pdf/" if report_type == "qweb-pdf" else "/report/text/"
        reportname = url.split(pattern)[1].split("?")[0]
        docids = None
        if "/" in reportname:
            reportname, docids = reportname.split("/")
        if docids:
            # Generic report:
            response = self.report_routes(
                reportname, docids=docids, converter=converter, context=context
            )
        else:
            # Particular report:
            data = dict(
                url_decode(url.split("?")[1]).items()
            )  # decoding the args represented in JSON
            if "context" in data:
                context, data_context = json.loads(context or "{}"), json.loads(data.pop("context"))
                context = json.dumps({**context, **data_context})
            response = self.report_routes(reportname, converter=converter, context=context, **data)

        return extension, reportname, response, data_context, docids
