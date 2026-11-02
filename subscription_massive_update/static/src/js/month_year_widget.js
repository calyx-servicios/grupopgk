odoo.define('subscription_massive_update.month_year_widget', function (require) {
"use strict";

var core = require('web.core');
var basicFields = require('web.basic_fields');
var datepicker = require('web.datepicker');
var fieldRegistry = require('web.field_registry');
var field_utils = require('web.field_utils');

var _t = core._t;

var MONTH_YEAR_FORMAT = 'MM/YYYY';

function formatMonthYear(value) {
    return value ? value.format(MONTH_YEAR_FORMAT) : '';
}

function parseMonthYear(value) {
    if (!value) {
        return false;
    }
    var date = moment.utc(value, [MONTH_YEAR_FORMAT, 'M/YYYY'], true);
    if (!date.isValid()) {
        throw new Error(_.str.sprintf(_t("'%s' is not a correct date"), value));
    }
    return field_utils.parse.date(date.format('YYYY-MM-DD'), null, {isUTC: true});
}

datepicker.DateWidget.include({
    start: function () {
        var res = this._super.apply(this, arguments);
        this._minViewMode = $.fn.datetimepicker.Constructor.MinViewModeNumber;
        return res;
    },
    _onInputClicked: function () {
        if ($.fn.datetimepicker.Constructor.MinViewModeNumber !== this._minViewMode) {
            var inputValue = this.$input.val();
            this.__libInput++;
            this.$el.datetimepicker('format', this.options.format);
            this.__libInput--;
            this.$input.val(inputValue);
        }
        return this._super.apply(this, arguments);
    },
});

var MonthYearWidget = datepicker.DateWidget.extend({
    init: function (parent, options) {
        this._super(parent, _.extend({}, options, {format: MONTH_YEAR_FORMAT}));
    },
    _formatClient: formatMonthYear,
    _parseClient: parseMonthYear,
});

var FieldMonthYear = basicFields.FieldDate.extend({
    _formatValue: formatMonthYear,
    _parseValue: parseMonthYear,
    _makeDatePicker: function () {
        return new MonthYearWidget(this, this.datepickerOptions);
    },
});

fieldRegistry.add('month_year', FieldMonthYear);

return {
    MonthYearWidget: MonthYearWidget,
    FieldMonthYear: FieldMonthYear,
};
});
