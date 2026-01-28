DMS Employee Auto Classification
=================================

Extends dms_auto_classification to automatically rename files based on employee legajo and classification date.

Features:
- Adds classification_date field to wizard
- Extracts employee legajo from PDF filename
- Renames files to: EMPLOYEE_NAME_DATE.pdf format
- Shows employee and new filename in detail view

Example:
- Original file: 450.pdf
- Employee with legajo 450: Juan Perez
- Classification date: 27/01/2026
- Result: Juan_Perez_27-01-2026.pdf
