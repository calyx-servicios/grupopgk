/** @odoo-module **/

import CalendarModel from 'calendar.CalendarModel';

const _original = CalendarModel.prototype._calendarEventByAttendee;
CalendarModel.prototype._calendarEventByAttendee = async function (eventsData) {
    const attendeeFilters = this.loadParams.filters.partner_ids;
    if (!attendeeFilters) {
        return eventsData;
    }
    return _original.call(this, eventsData);
};
