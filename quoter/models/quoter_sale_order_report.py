# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl-3.0.html)

from odoo import _, api, models
from odoo.tools import html_escape
from odoo.tools.misc import formatLang

QUOTER_REPORT_EMPTY = "-"


class SaleOrderQuoterReport(models.Model):
    _inherit = "sale.order"

    @api.model
    def _quoter_report_layout_company(self):
        """Compañía cuyo logo/membrete usa el PDF interno (Paludi PGK por defecto)."""
        icp = self.env["ir.config_parameter"].sudo()
        raw_id = icp.get_param("quoter.report_company_id")
        Company = self.env["res.company"].sudo()
        if raw_id:
            try:
                company = Company.browse(int(raw_id)).exists()
            except (TypeError, ValueError):
                company = Company.browse()
            if company:
                return company
        company = Company.search(
            [("name", "ilike", "Paludi Gonzalez")],
            order="id",
            limit=1,
        )
        if company:
            return company
        return Company.search([], order="id", limit=1)

    def _quoter_report_matrix_areas(self):
        """Áreas incluidas en la cotización (máx. 5), ordenadas por secuencia."""
        self.ensure_one()
        return self.quoter_area_ids.sorted(key=lambda a: (a.sequence, a.id))[:5]

    def _quoter_report_block_for_area(self, area):
        self.ensure_one()
        return self.quoter_area_block_ids.filtered(lambda b, a=area: b.area_id == a)[:1]

    def _quoter_report_area_matrix_characteristics(self, area):
        """Filas de características del área en la matriz PDF (puede haber más de una)."""
        if not area:
            return []
        items = []
        if area.is_auditoria_area:
            items.append({"key": "complexity", "label": _("Nivel de riesgo")})
        elif area.is_tax_area or area.is_payroll_area:
            items.append({"key": "complexity", "label": _("Nivel de complejidad")})
        elif not area.is_finanzas_area and area.hour_matrix_mode not in (
            "formula",
            "regular_manual",
        ):
            custom = (area.complexity_level_custom_label or "").strip()
            if custom:
                items.append({"key": "complexity", "label": custom})
            elif area.hour_matrix_mode in ("regular", "combined"):
                items.append({"key": "complexity", "label": _("Nivel de complejidad")})
        if area.hour_matrix_mode == "formula_chain":
            items.append({"key": "employees", "label": _("Cantidad de empleados")})
        return items

    def _quoter_report_matrix_characteristic_value(self, area, block, item_key):
        if item_key == "employees":
            if block:
                return str(block.chain_employee_count or 0)
            return QUOTER_REPORT_EMPTY
        if item_key == "complexity":
            if block and block.complexity_level_id:
                return block.complexity_level_id.display_name
            return QUOTER_REPORT_EMPTY
        return QUOTER_REPORT_EMPTY

    def _quoter_report_matrix_rows(self):
        self.ensure_one()
        areas = self._quoter_report_matrix_areas()
        rows = [
            {
                "label": _("Gerente a cargo"),
                "cells": (
                    [
                        self._quoter_report_block_for_area(area).manager_id.display_name
                        or QUOTER_REPORT_EMPTY
                        for area in areas
                    ]
                    if areas
                    else [QUOTER_REPORT_EMPTY]
                ),
            }
        ]
        char_rows = []
        seen_labels = set()
        for area in areas:
            for item in self._quoter_report_area_matrix_characteristics(area):
                if item["label"] not in seen_labels:
                    seen_labels.add(item["label"])
                    char_rows.append(item)
        char_rows.sort(key=lambda item: item["label"].lower())
        for char_item in char_rows:
            char_label = char_item["label"]
            cells = []
            for area in areas:
                block = self._quoter_report_block_for_area(area)
                area_chars = {
                    i["label"]: i["key"]
                    for i in self._quoter_report_area_matrix_characteristics(area)
                }
                if char_label in area_chars:
                    cells.append(
                        self._quoter_report_matrix_characteristic_value(
                            area, block, area_chars[char_label]
                        )
                    )
                else:
                    cells.append(QUOTER_REPORT_EMPTY)
            rows.append({"label": char_label, "cells": cells})
        branch_row = False
        for area in areas:
            if area.use_branching:
                branch_row = True
                break
        if branch_row:
            cells = []
            for area in areas:
                block = self._quoter_report_block_for_area(area)
                if area.use_branching and block and block.branch_id:
                    cells.append(block.branch_id.display_name)
                else:
                    cells.append(QUOTER_REPORT_EMPTY)
            rows.append({"label": _("Tipo de empresa"), "cells": cells})
        return {"areas": areas, "rows": rows}

    def _quoter_report_strategic_questions(self):
        self.ensure_one()
        Attachment = self.env["ir.attachment"]
        field_names = (
            "quoter_q_competitors",
            "quoter_q_budget",
            "quoter_q_current_payment",
            "quoter_q_notes",
        )
        result = []
        for idx, fname in enumerate(field_names, start=1):
            label = self._fields[fname].string
            answer = getattr(self, fname) or ""
            attachments = Attachment.search(
                [
                    ("res_model", "=", self._name),
                    ("res_id", "=", self.id),
                    ("name", "ilike", "quoter_q_%s" % idx),
                ]
            )
            attach_note = ""
            if attachments:
                attach_note = _(
                    "Archivos adjuntos: %s"
                ) % ", ".join(attachments.mapped("name"))
            result.append(
                {
                    "number": idx,
                    "label": label,
                    "answer": answer.strip() or QUOTER_REPORT_EMPTY,
                    "attachments": attach_note,
                }
            )
        return result

    def _quoter_report_budget_blocks(self):
        self.ensure_one()
        blocks = []
        for block in self._quoter_area_blocks_ordered():
            area = block.area_id
            if not area:
                continue
            ranges = area.area_range_ids.sorted(key=lambda r: (r.sequence, r.id))
            limit = max(len(ranges), 1)
            base_h, adj_h = self._quoter_slot_hours_base_and_adjustment(area, limit=limit)
            rates, ranges = self._quoter_slot_range_rates(area, limit=limit)
            disc_pct, sur_pct = self._quoter_block_adjustment_amounts(block)
            rate_factor = 1.0 - (disc_pct / 100.0) + (sur_pct / 100.0)
            tot_h = [base_h[i] + adj_h[i] for i in range(limit)]
            adj_rates = [max(0.0, rates[i] * rate_factor) for i in range(limit)]
            final_vals = [tot_h[i] * adj_rates[i] for i in range(limit)]

            lines = []
            olines = self.order_line.filtered(
                lambda l, a=area: not l.display_type
                and l.quoter_tab_area_id == a
                and not l.quoter_is_area_discount_total_line
            )
            for line in olines.filtered(lambda l: not l.quoter_is_adjustment_line):
                row_hours = []
                by_range = {
                    h.area_range_id.id: float(h.hours or 0.0)
                    for h in line.quoter_range_hour_ids
                    if h.area_range_id
                }
                for range_rec in ranges:
                    row_hours.append(by_range.get(range_rec.id, 0.0))
                lines.append(
                    {
                        "name": line.name or line.product_id.display_name,
                        "hours": row_hours,
                        "total_hours": sum(row_hours),
                    }
                )
            adj_lines = olines.filtered("quoter_is_adjustment_line")
            if adj_lines:
                adj_hours = [0.0] * limit
                for line in adj_lines:
                    by_range = {
                        h.area_range_id.id: float(h.hours or 0.0)
                        for h in line.quoter_range_hour_ids
                        if h.area_range_id
                    }
                    for idx, range_rec in enumerate(ranges):
                        adj_hours[idx] += by_range.get(range_rec.id, 0.0)
                lines.append(
                    {
                        "name": _("Ajuste"),
                        "hours": adj_hours,
                        "total_hours": sum(adj_hours),
                        "is_adjustment": True,
                    }
                )

            base_vals = [base_h[i] * rates[i] for i in range(limit)]
            base_total = sum(base_vals)
            blocks.append(
                {
                    "area_name": area.display_name,
                    "range_labels": [r.name for r in ranges] or [QUOTER_REPORT_EMPTY],
                    "lines": lines,
                    "totals_hours": tot_h,
                    "rates": rates,
                    "base_values": base_vals,
                    "final_values": final_vals,
                    "grand_total": base_total,
                    "adjusted_total": sum(final_vals),
                    "discount_pct": disc_pct,
                    "surcharge_pct": sur_pct,
                    "adjustment_pct_cells": self._quoter_report_adjustment_pct_cells(
                        disc_pct, sur_pct, limit
                    ),
                    "has_adjustment_lines": any(
                        line.get("is_adjustment") for line in lines
                    ),
                    "total_hours_sum": sum(tot_h),
                    "col_count": limit + 1,
                }
            )
        return blocks

    def _quoter_report_adjustment_pct_cells(self, discount_pct, surcharge_pct, limit):
        """Porcentaje neto descuento/recargo por columna de rol (mismo % en todas)."""
        net = float(surcharge_pct or 0.0) - float(discount_pct or 0.0)
        if abs(net) < 0.0001:
            text = "0,00%"
            css = ""
        elif net > 0:
            text = "+%s%%" % self._quoter_format_number_es(net, decimals=2)
            css = "o_q_pct_pos"
        else:
            text = "-%s%%" % self._quoter_format_number_es(abs(net), decimals=2)
            css = "o_q_pct"
        return [{"text": text, "css_class": css}] * max(limit, 1)

    def _quoter_report_format_money(self, amount):
        self.ensure_one()
        return formatLang(
            self.env,
            amount or 0.0,
            currency_obj=self.currency_id,
        )

    def _quoter_report_summary_totals(self):
        """Recuadro final Anual/Mensual (mismos totales que la pestaña Resumen general)."""
        self.ensure_one()
        annual_amount, monthly_amount, monthly_proportion, total_monthly_quota = (
            self._quoter_order_summary_amounts()
        )
        return {
            "annual": self._quoter_report_format_money(annual_amount),
            "monthly": self._quoter_report_format_money(monthly_amount),
            "proportion": self._quoter_report_format_money(monthly_proportion),
            "total": self._quoter_report_format_money(total_monthly_quota),
        }

    def _quoter_report_format_number(self, value, decimals=2):
        return self._quoter_format_number_es(value, decimals=decimals)

    def _quoter_report_html_escape(self, value):
        return html_escape(value or "")
