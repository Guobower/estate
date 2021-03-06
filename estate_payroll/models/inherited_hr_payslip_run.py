# -*- coding: utf-8 -*-

import logging
from openerp import models, fields, api, exceptions, _
from datetime import datetime
from dateutil import relativedelta
from openerp.tools import DEFAULT_SERVER_DATE_FORMAT as DF
from openerp.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class PayslipRun(models.Model):
    """Estate might process payroll batches by estate or division.
    """
    _inherit = 'hr.payslip.run'

    type = fields.Selection([('employee', 'By Employee'),
                             ('estate', 'By Estate'),
                             ('division', 'By Division')],
                            'Payroll Type', default='employee',
                            help='By Estate/Division create Payslip Batches for Estate.')
    company_id = fields.Many2one('res.company', 'Company', help='Limit payroll based on employee company.')
    estate_id = fields.Many2one('stock.location', "Estate",
                                domain=[('estate_location', '=', True), ('estate_location_level', '=', '1'),
                                ('estate_location_type', '=', 'planted')])
    division_id = fields.Many2one('stock.location', "Division",
                                  domain=[('estate_location', '=', True), ('estate_location_level', '=', '2')])
    team_ids = fields.Many2one('estate.hr.team')
    active = fields.Boolean('Active', default=True)

    @api.multi
    @api.onchange('date_start')
    def _onchange_date_start(self):
        """Payroll processed by month.
        """
        start = datetime.strptime(self.date_start, DF).replace(day=1)
        if start:
            to = (start + relativedelta.relativedelta(months=+1, days=-1))
            self.date_end = to.strftime(DF)

        #if date_conv:
        #    self.date_to = datetime.date(date_conv) + relativedelta(months=+1, day=1, days=-1))
        # lambda *a: str(datetime.now() + relativedelta.relativedelta(months=+1, day=1, days=-1))[:10]

    @api.multi
    @api.onchange('date_start', 'date_end')
    def _onchange_payslip(self):
        """ Sync with payslip batch's date from and to. Create Automated Action for update workline and input line."""
        if self.slip_ids:
            payslip_ids = self.env['hr.payslip'].browse(self.slip_ids.ids)
            payslip_ids.write({'date_from': self.date_start, 'date_to': self.date_end})

    @api.one
    @api.onchange('division_id')
    def _onchange_division_id(self):
        """Select estate automatically, Update location domain in upkeep line
        :return: first estate and set to estate_id
        """
        if self.division_id:
            res = self.estate_id = self.env['stock.location'].get_estate(self.division_id.id)
            if res:
                self.estate_id = res

    @api.multi
    def close_payslip_run(self):
        """
        Update payslip done and upkeep state payslip
        :return: True
        """

        # No payslip, no closing
        if not self.slip_ids:
            err_msg = _('You have not any payslip to close.')
            raise ValidationError(err_msg)

        upkeep_obj = self.env['estate.upkeep']
        employees = []

        # Check payslip
        summary = []
        for record in self.slip_ids:
            summary.append(record.check_payslip())
            team = []
            company = []

            for x in summary:
                if x['team']:
                    team.append(x['team']['khl'])
                if x['company']:
                    company.append(x['company']['khl'])

            if len(team) or len(company):
                err_msg = _('There are problem with our payslip.\n\n'
                            'Labour without team: %s\n '
                            'Difference at company: %s' % (', '.join(team),
                                                           ', '.join(company)))
                raise ValidationError(err_msg)

        # Make sure all upkeep has been closed
        for record in self.slip_ids:
            employees.append(record.employee_id.id)
        if upkeep_obj.get_upkeep_by_employee(employees, self.date_start, self.date_end, 'confirmed'):
            err_msg = _('Some upkeep labor did not approved yet.')
            raise ValidationError(err_msg)

        # Close payslip
        self.env['hr.payslip'].search([('payslip_run_id', 'in', self.ids)]).write({'state': 'done'})

        upkeep_list = upkeep_obj.get_upkeep_by_employee(employees, self.date_start, self.date_end, 'approved')

        # Update upkeep state to payslip  state
        upkeep_obj.payslip_upkeep(upkeep_list)

        # Update fingerprint to approved
        for employee_id in self.slip_ids.mapped('employee_id'):
            self.env['hr_fingerprint_ams.attendance'].search([('employee_name', '=', employee_id.name),
                                                              ('date', '>=', self.date_start),
                                                              ('date', '<=', self.date_end)]).write({'state': 'payslip'})

        # self.env['hr.payslip'].search([('payslip_run_id', 'in', self.ids)]).write({'state': 'done'})

        return super(PayslipRun, self).close_payslip_run()

    @api.multi
    def draft_payslip_run(self):
        """
        Update upkeep state back into approved
        :return: True
        """
        self.ensure_one()
        upkeep_obj = self.env['estate.upkeep']
        employees = []

        # Open payslip
        self.env['hr.payslip'].search([('payslip_run_id', 'in', self.ids)]).write({'state': 'draft'})

        # Open upkeep
        if self.slip_ids:
            for record in self.slip_ids:
                employees.append(record.employee_id.id)
        upkeep_list = upkeep_obj.get_upkeep_by_employee(employees, self.date_start, self.date_end, 'payslip')

        # Update upkeep state to approved state
        upkeep_obj.approved_upkeep(upkeep_list)

        # Update fingerprint to draft (case: no separate fingerprint approval)
        for employee_id in self.slip_ids.mapped('employee_id'):
            self.env['hr_fingerprint_ams.attendance'].search([('employee_name', '=', employee_id.name),
                                                              ('date', '>=', self.date_start),
                                                              ('date', '<=', self.date_end)]).write({'state': 'draft'})

        # Update payslip to draft
        self.env['hr.payslip'].search([('payslip_run_id', 'in', self.ids)]).write({'state': 'draft'})

        return super(PayslipRun, self).draft_payslip_run()

    @api.multi
    def unlink(self):
        """
        No payslip should exists after its parent deleted
        :return:
        """
        for record in self:
            if record.state == 'close':
                error_msg = _('You cannot delete closed Payslip.')
                raise exceptions.ValidationError(error_msg)

            self.env['hr.payslip'].search([('id', 'in', record.slip_ids.ids)]).unlink()
            return super(PayslipRun, record).unlink()

    def get_qrcode(self):
        """ Printed report required to traceback to systetm """
        print_datetime = datetime.today()
        current_user = self.env.user
        report_name = 'Payroll'

        # Log to validate qr
        _logger.info(_('System print-out Payroll report: %s;%s;%s;%s' % (print_datetime, current_user.name, report_name,self.name)))

        # Return value to report
        return '%s;%s;%s;%s' % (print_datetime, current_user.name, report_name, self.name)

    @api.multi
    def toggle_active(self):
        """ Make sure its payslip and payslip line follow payslip batch's state"""

        super(PayslipRun, self).toggle_active()

        # Toggling false to active required domain with active param
        payslip_ids = self.env['hr.payslip'].search([('payslip_run_id', 'in', self.ids),
                                                     ('active', '=', not self.active)])
        payslip_ids.write({'active': self.active})

        payslip_line_ids = self.env['hr.payslip.line'].search([('slip_id', 'in', payslip_ids.ids),
                                                               ('active', '=', not self.active)])
        payslip_line_ids.write({'active': self.active})
