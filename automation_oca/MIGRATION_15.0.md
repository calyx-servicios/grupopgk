# automation_oca migration notes (16.0 -> 15.0)

## Scope

This module was downgraded to Odoo 15 Community from the OCA 16.0 codebase,
prioritizing backend feature parity and operational stability.

## Functional differences

1. Visual workflow editor (custom kanban cards, hierarchy lines, graph widget)
was replaced by native tree/form one2many views.
2. Kanban drag-and-drop upload/import (custom `js_class`) was replaced by a
standard import wizard available from the configuration form.

## Why these changes were required

- Odoo 15 web client in this repository does not provide the OWL/web APIs used
  by the 16.0 frontend implementation (`useOpenX2ManyRecord`, `useX2ManyCrud`,
  custom view registration).
- Keeping those assets would break backend rendering and JS initialization.

## Alternative provided

- Import/export is still supported:
  - Export: existing `Export` button.
  - Import: new `Import` button opening a wizard to upload exported JSON.
- Automation execution logic, triggers, cron behavior, tracking and security
  remain on server-side models.

## Additional technical compatibility adaptations

- Replaced translation export helper calls unavailable in Odoo 15
  (`_get_stored_translations`) with explicit per-language reads.
- Updated manifest version to `15.0.1.0.0` and removed incompatible frontend
  assets from backend bundle declaration.
