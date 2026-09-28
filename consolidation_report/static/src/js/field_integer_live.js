odoo.define('consolidation_report.FieldIntegerLive', function (require) {
    "use strict";

    const basicFields = require('web.basic_fields');
    const fieldRegistry = require('web.field_registry');

    // Entero que avisa el cambio mientras se escribe
    const FieldIntegerLive = basicFields.FieldInteger.extend({
        DEBOUNCE: 400,
    });

    fieldRegistry.add('integer_live', FieldIntegerLive);

    return FieldIntegerLive;
});
