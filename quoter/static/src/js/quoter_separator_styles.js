odoo.define("quoter.separator_styles", function (require) {
    "use strict";

    const QUOTER_DISABLE_SEPARATOR_STYLES = false;
    if (QUOTER_DISABLE_SEPARATOR_STYLES) {
        return;
    }

    const ListRenderer = require("web.ListRenderer");

    const COLOR_PALETTE = [
        "#6c757d",
        "#e74c3c",
        "#3498db",
        "#f1c40f",
        "#2ecc71",
        "#9b59b6",
        "#e67e22",
        "#1abc9c",
        "#34495e",
        "#d35400",
        "#16a085",
        "#7f8c8d",
    ];

    function toLocalDataMap(state) {
        const map = {};
        (state.data || []).forEach(function (rec) {
            map[String(rec.id)] = rec.data || {};
        });
        return map;
    }

    function m2oId(value) {
        if (!value) {
            return false;
        }
        if (Array.isArray(value)) {
            return value[0] || false;
        }
        if (typeof value === "object" && value.id) {
            return value.id;
        }
        return value;
    }

    function hexToRgb(hex) {
        const clean = (hex || "").replace("#", "");
        if (clean.length !== 6) {
            return { r: 108, g: 117, b: 125 };
        }
        return {
            r: parseInt(clean.slice(0, 2), 16),
            g: parseInt(clean.slice(2, 4), 16),
            b: parseInt(clean.slice(4, 6), 16),
        };
    }

    function applySeparatorLook($row, mode, colorIndex) {
        const idx = parseInt(colorIndex || 0, 10);
        const color = COLOR_PALETTE[Math.abs(idx) % COLOR_PALETTE.length];
        const rgb = hexToRgb(color);
        $row.addClass("o_quoter_separator_section");
        $row.css("--quoter-separator-color", color);
        $row.css(
            "--quoter-separator-color-rgba",
            "rgba(" + rgb.r + ", " + rgb.g + ", " + rgb.b + ", 0.38)"
        );
        if (mode === "full") {
            $row.addClass("o_quoter_separator_mode_full");
        }
    }

    ListRenderer.include({
        _renderView: function () {
            const res = this._super.apply(this, arguments);
            const self = this;
            function run() {
                self._quoterApplySeparatorStyles();
            }
            if (res && typeof res.then === "function") {
                return res.then(function () {
                    run();
                });
            }
            run();
            return res;
        },

        _quoterApplySeparatorStyles: function () {
            if (!this.state || !this.state.data || !this.el) {
                return;
            }
            const localData = toLocalDataMap(this.state);
            const $rows = $(this.el).find("tbody tr.o_data_row");
            $rows.removeClass(
                "o_quoter_separator_section o_quoter_separator_mode_full o_quoter_separator_group_start"
            );
            $rows.css("--quoter-separator-color", "");
            $rows.css("--quoter-separator-color-rgba", "");

            let lastProductTagId = null;

            $rows.each(function () {
                const $row = $(this);
                const localId = String($row.data("id"));
                const data = localData[localId] || {};

                if (data.display_type === "line_section") {
                    applySeparatorLook(
                        $row,
                        data.quoter_separator_style_mode || "none",
                        data.quoter_separator_color
                    );
                    lastProductTagId = null;
                    return;
                }

                const tagId = m2oId(data.quoter_separator_tag_id);
                if (!tagId) {
                    lastProductTagId = null;
                    return;
                }

                if (tagId !== lastProductTagId) {
                    $row.addClass("o_quoter_separator_group_start");
                    applySeparatorLook(
                        $row,
                        data.quoter_area_separator_visual_mode || "none",
                        data.quoter_product_separator_tag_color
                    );
                    const tagName = Array.isArray(data.quoter_separator_tag_id)
                        ? data.quoter_separator_tag_id[1]
                        : "";
                    if (tagName) {
                        $row.attr("data-quoter-section-title", tagName);
                    }
                }
                lastProductTagId = tagId;
            });
        },
    });
});
