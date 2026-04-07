import base64
import io
import re
import unicodedata
from datetime import date, datetime

from odoo import api, fields, models, _
from odoo.exceptions import UserError

try:
    import openpyxl
    from openpyxl.utils.datetime import from_excel
except ImportError:
    openpyxl = None
    from_excel = None


class RecouvrementFactureImportWizard(models.TransientModel):
    _name = 'recouvrement.facture.import.wizard'
    _description = 'Importer des factures depuis Excel'

    file = fields.Binary(string='Fichier Excel', required=True)
    file_name = fields.Char(string='Nom du fichier')
    sheet_name = fields.Char(string='Feuille (optionnel)')
    imported_count = fields.Integer(string='Nouvelles factures', readonly=True)
    updated_count = fields.Integer(string='Factures mises à jour', readonly=True)
    note = fields.Text(string='Résumé', readonly=True)

    def _normalize_header(self, header):
        if header is None:
            return ''
        value = str(header).strip().lower().replace('\r', ' ').replace('\n', ' ')
        value = value.replace('n°', 'numero ').replace('nº', 'numero ').replace("l'ordre", 'ordre')
        value = unicodedata.normalize('NFKD', value).encode('ascii', 'ignore').decode('ascii')
        value = re.sub(r'\s+', ' ', value)
        return value.strip(' :')

    def _get_field_mapping(self, header):
        mapping = {
            'reference facture': 'name',
            'numero facture': 'name',
            'numero de la facture': 'name',
            'facture': 'name',
            'code affaire': 'code_affaire',
            'affaire': 'code_affaire',
            'type de facture': 'facture_type',
            'type facture': 'facture_type',
            'facture type': 'facture_type',
            'client': 'client_id',
            'date de reception de lordre de facturation (1)': 'date_reception_ordre',
            'date de reception de lordre de facturation': 'date_reception_ordre',
            'chez laila': 'chez_laila',
            'chez bennis': 'chez_bennis',
            'date de la facture': 'date_facture',
            'date facture': 'date_facture',
            'la date de signature de la facture': 'date_signature',
            'date de signature': 'date_signature',
            'date signature': 'date_signature',
            'date de depot de la facture chez le client (3)': 'date_depot_client',
            'date de depot de la facture chez le client': 'date_depot_client',
            'date de depot client': 'date_depot_client',
            'date de depot client (3)': 'date_depot_client',
            'date depot': 'date_depot_client',
            'montant facture en ttc': 'montant_ttc',
            'montant ttc': 'montant_ttc',
            'montant ht': 'montant_ht',
            'reference justificatif': 'reference_justificatif',
            'nature': 'nature',
            'division': 'division_id',
            'pole': 'pole_id',
            'numero enreg': 'numero_enreg',
            'ice': 'ice',
            'numero marche': 'numero_marche',
            'devise': 'currency_id',
        }
        return mapping.get(header, None)

    def _extract_date_from_text(self, value, default_year=None):
        if value in [None, '']:
            return False

        text = str(value).strip()
        if not text:
            return False

        normalized = unicodedata.normalize('NFKD', text).encode('ascii', 'ignore').decode('ascii').lower()
        normalized = normalized.replace('.', '/').replace('-', '/')
        month_map = {
            'janvier': '01', 'janv': '01',
            'fevrier': '02', 'fevr': '02', 'fev': '02',
            'mars': '03',
            'avril': '04', 'avr': '04',
            'mai': '05',
            'juin': '06',
            'juillet': '07', 'juil': '07',
            'aout': '08',
            'septembre': '09', 'sept': '09',
            'octobre': '10', 'oct': '10',
            'novembre': '11', 'nov': '11',
            'decembre': '12', 'dec': '12',
        }
        for label, month in month_map.items():
            normalized = re.sub(rf'\b{label}\b', f'/{month}/', normalized)

        normalized = re.sub(r'\s+', ' ', normalized)
        match = re.search(r'(?P<day>\d{1,2})\s*/\s*(?P<month>\d{1,2})\s*/\s*(?P<year>\d{2,4})', normalized)
        if not match:
            match = re.search(r'(?P<day>\d{1,2})\s*/\s*(?P<month>\d{1,2})(?!\s*/)', normalized)
        if not match:
            return False

        day = int(match.group('day'))
        month = int(match.group('month'))
        year_text = match.groupdict().get('year')
        year = default_year or fields.Date.today().year
        if year_text:
            year = int(year_text)
            if year < 100:
                year += 2000

        try:
            return date(year, month, day)
        except ValueError:
            return False

    def _normalize_type(self, value):
        if not value:
            return False
        value = self._normalize_header(value)
        if 'pro forma' in value or 'pro-forma' in value or 'proforma' in value:
            return 'proforma'
        if 'groupement' in value:
            return 'groupement'
        if 'avance' in value:
            return 'avance'
        if 'suivi de facturation' in value or '2eme envoi' in value or 'standard' in value:
            return 'standard'
        return 'autre'

    def _find_or_create_client(self, name):
        if not name:
            return False
        partner = self.env['res.partner'].search([('name', '=ilike', name)], limit=1)
        if partner:
            return partner
        return self.env['res.partner'].create({'name': name})

    def _find_or_create_division(self, name):
        if not name:
            return False
        division = self.env['hr.department'].search([('name', '=ilike', name)], limit=1)
        if division:
            return division
        return self.env['hr.department'].create({'name': name})

    def _find_or_create_pole(self, name):
        if not name:
            return False
        pole = self.env['hr.department'].search([('name', '=ilike', name)], limit=1)
        if pole:
            return pole
        return self.env['hr.department'].create({'name': name})

    def _convert_value(self, field_name, value):
        if value in [None, '']:
            return False

        if field_name in ['name', 'numero_enreg']:
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                return str(int(value)).zfill(3)
            return str(value).strip()

        if field_name in ['code_affaire', 'ice', 'numero_marche', 'chez_laila', 'chez_bennis', 'nature', 'reference_justificatif']:
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                return str(int(value))
            return str(value).strip()

        if field_name in ['date_reception_ordre', 'date_facture', 'date_signature', 'date_depot_client']:
            if isinstance(value, datetime):
                return value.date()
            if isinstance(value, date):
                return value
            if isinstance(value, (int, float)) and not isinstance(value, bool) and from_excel:
                try:
                    converted = from_excel(value)
                    return converted.date() if hasattr(converted, 'date') else converted
                except Exception:
                    pass
            text = str(value).strip()
            for fmt in (
                '%m/%d/%Y', '%m/%d/%y', '%d/%m/%Y', '%d/%m/%y',
                '%Y-%m-%d', '%Y-%m-%d %H:%M:%S', '%m/%d/%Y %H:%M:%S', '%d/%m/%Y %H:%M:%S'
            ):
                try:
                    return datetime.strptime(text, fmt).date()
                except ValueError:
                    continue
            extracted_date = self._extract_date_from_text(text)
            if extracted_date:
                return extracted_date
            return False

        if field_name in ['montant_ttc', 'montant_ht']:
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                return float(value)
            text = str(value).strip().replace('\xa0', '').replace(' ', '')
            if text.count(',') == 1:
                text = text.replace('.', '').replace(',', '.')
            try:
                return float(text)
            except (TypeError, ValueError):
                return False

        return value

    def action_import(self):
        self.ensure_one()
        if openpyxl is None:
            raise UserError(_('La bibliothèque Python openpyxl est requise pour importer les fichiers Excel.'))

        try:
            content = base64.b64decode(self.file)
        except Exception:
            raise UserError(_('Impossible de décoder le fichier Excel.'))

        workbook = openpyxl.load_workbook(io.BytesIO(content), data_only=True, read_only=True)
        sheet_names = [self.sheet_name] if self.sheet_name else workbook.sheetnames
        facture_obj = self.env['recouvrement.facture']
        created = 0
        updated = 0
        errors = []

        for sheet_name in sheet_names:
            if not sheet_name:
                continue
            if sheet_name not in workbook.sheetnames:
                errors.append(_('Feuille introuvable: %s') % sheet_name)
                continue
            worksheet = workbook[sheet_name]
            row_iterator = worksheet.iter_rows(values_only=True)

            headers = None
            header_row_index = 0
            for probe_index, probe_row in enumerate(row_iterator, start=1):
                normalized_headers = [self._normalize_header(cell) for cell in probe_row]
                mapped_fields = [self._get_field_mapping(header) for header in normalized_headers if self._get_field_mapping(header)]
                if mapped_fields and ('name' in mapped_fields or len(mapped_fields) >= 4):
                    headers = normalized_headers
                    header_row_index = probe_index
                    break
                if probe_index >= 20:
                    break

            if not headers:
                errors.append(_('Aucune ligne d’en-tête reconnue dans la feuille %s.') % sheet_name)
                continue

            for row_index, row in enumerate(row_iterator, start=header_row_index + 1):
                if not any([cell is not None and str(cell).strip() for cell in row]):
                    continue
                values = {}
                for header, cell in zip(headers, row):
                    field_name = self._get_field_mapping(header)
                    if not field_name:
                        continue
                    if field_name == 'client_id':
                        client = self._find_or_create_client(cell)
                        if client:
                            values['client_id'] = client.id
                        continue
                    if field_name == 'division_id':
                        division = self._find_or_create_division(cell)
                        if division:
                            values['division_id'] = division.id
                        continue
                    if field_name == 'pole_id':
                        pole = self._find_or_create_pole(cell)
                        if pole:
                            values['pole_id'] = pole.id
                        continue
                    if field_name == 'currency_id' and cell:
                        currency = self.env['res.currency'].search([('name', '=ilike', str(cell).strip())], limit=1)
                        if currency:
                            values['currency_id'] = currency.id
                        continue
                    if field_name == 'facture_type':
                        type_value = self._normalize_type(cell)
                        if type_value:
                            values['facture_type'] = type_value
                        continue
                    converted_value = self._convert_value(field_name, cell)
                    if field_name == 'date_depot_client' and cell not in [None, '']:
                        cell_text = str(cell).strip()
                        if cell_text:
                            values['depot_comment'] = cell_text
                        if converted_value:
                            values['date_depot_client'] = converted_value
                        continue
                    values[field_name] = converted_value

                reference_value = str(values.get('name') or '').strip()
                if not reference_value or reference_value.lower() in ['vide', 'nan', 'none', '-', 'n/a']:
                    continue
                values['name'] = reference_value

                if not values.get('client_id'):
                    errors.append(_('Ligne %s de la feuille %s ignorée: le client est manquant.') % (row_index, sheet_name))
                    continue

                facture_type_from_sheet = self._normalize_type(sheet_name)
                if facture_type_from_sheet and not values.get('facture_type'):
                    values['facture_type'] = facture_type_from_sheet
                values['source_sheet'] = sheet_name

                if 'code_affaire' in values and not values.get('code_affaire'):
                    values.pop('code_affaire')

                try:
                    search_domain = [('name', '=', values['name'])]
                    if values.get('code_affaire'):
                        search_domain.append(('code_affaire', '=', values['code_affaire']))
                    facture = facture_obj.search(search_domain, limit=1)
                    if facture:
                        update_vals = {k: v for k, v in values.items() if v not in [None, '', False]}
                        if update_vals:
                            facture.with_context(recouvrement_import=True).write(update_vals)
                            updated += 1
                    else:
                        defaults = {
                            'state': 'imported',
                            'currency_id': self.env.company.currency_id.id,
                        }
                        defaults.update({k: v for k, v in values.items() if v not in [None, '', False]})
                        facture_obj.create(defaults)
                        created += 1
                except Exception as exc:
                    errors.append(_('Ligne %s de la feuille %s ignorée: %s') % (row_index, sheet_name, str(exc)))
                    continue

        note_lines = [_('Import terminé.')] if not errors else []
        note_lines.append(_('Nouvelles factures: %s') % created)
        note_lines.append(_('Factures mises à jour: %s') % updated)
        note_lines.extend(errors)
        self.imported_count = created
        self.updated_count = updated
        self.note = '\n'.join(note_lines)
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'recouvrement.facture.import.wizard',
            'view_mode': 'form',
            'res_id': self.id,
            'target': 'new',
        }
