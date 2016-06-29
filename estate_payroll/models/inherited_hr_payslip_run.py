# -*- coding: utf-8 -*-

from openerp import models, fields, api, exceptions, _
from datetime import datetime
from dateutil import relativedelta
from openerp.tools import DEFAULT_SERVER_DATE_FORMAT as DF

class PayslipRun(models.Model):
    """Estate might process payroll batches by estate or division.
    """
    _inherit = 'hr.payslip.run'

    type = fields.Selection([('employee', 'By Employee'),
                             ('estate', 'By Estate'),
                             ('division', 'By Division')],
                            'Payroll Type', default='employee',
                            help='By Estate/Division create Payslip Batches for Estate.')
    estate_id = fields.Many2one('stock.location', "Estate",
                                domain=[('estate_location', '=', True), ('estate_location_level', '=', '1'),
                                ('estate_location_type', '=', 'planted')])
    division_id = fields.Many2one('stock.location', "Division",
                                  domain=[('estate_location', '=', True), ('estate_location_level', '=', '2')])

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

    @api.one
    @api.onchange('division_id')
    def _onchange_division_id(self):
        """Select estate automatically, Update location domain in upkeep line
        :return: first estate and set to estate_id
        """
        if self.division_id:
            res = self.env['stock.location'].search([('id', '=', self.division_id.location_id.id)])
            if res:
                self.estate_id = res

    @api.multi
    def close_payslip_run(self):
        """
        Update payslip done andd upkeep state payslip
        :return: True
        """
        self.ensure_one()
        upkeep_obj = self.env['estate.upkeep']
        employees = []

        # Close payslip
        self.env['hr.payslip'].search([('payslip_run_id', 'in', self.ids)]).write({'state': 'done'})

        # Close upkeep
        if self.slip_ids:
            for record in self.slip_ids:
                employees.append(record.employee_id.id)
        upkeep_list = upkeep_obj.get_upkeep_by_employee(employees, self.date_start, self.date_end, 'approved')

        # Update upkeep state to payslip  state
        upkeep_obj.payslip_upkeep(upkeep_list)

        # Update fingerprint to approved
        self.env['hr_fingerprint_ams.attendance'].search([('date', '>=', self.date_start),
                                                          ('date', '<=', self.date_end)]).write({'state': 'approved'})

        # Update payslip to done
        self.env['hr.payslip'].search([('payslip_run_id', 'in', self.ids)]).write({'state': 'done'})

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
        self.env['hr_fingerprint_ams.attendance'].search([('date', '>=', self.date_start),
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
        if self.state == 'close':
            error_msg = _('You cannot delete closed Payslip.')
            raise exceptions.ValidationError(error_msg)

        self.env['hr.payslip'].search([('id', 'in', self.slip_ids.ids)]).unlink()
        return super(PayslipRun, self).unlink()

class PayslipRunReport(models.Model):
    """Payslip List Report required to group by Team
    """
    _inherit = 'hr.payslip.run'

    team_ids = fields.Many2one('estate')
