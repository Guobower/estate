# -*- coding: utf-8 -*-

from openerp import models, fields, api, _
from rule_attendance import *

class UpkeepLabour(models.Model):
    """
    Monitor hr attendance per upkeep labour.
    """
    _inherit = 'estate.upkeep.labour'

    attendance_in = fields.Many2one('hr.attendance', 'Sign In', compute='_compute_attendance')
    attendance_out = fields.Many2one('hr.attendance', 'Sign Out', compute='_compute_attendance')
    is_fingerprint = fields.Char(string="Fingerprint", compute='_compute_fingerprint')

    @api.one
    @api.depends('employee_id', 'upkeep_date')
    def _compute_attendance(self):
        att_obj = self.env['hr.attendance']
        if self.employee_id and self.upkeep_date:
            attendance_in_id = att_obj.get_attendance(self.employee_id, self.upkeep_date, 'sign_in')
            attendance_out_id = att_obj.get_attendance(self.employee_id, self.upkeep_date, 'sign_out')
            if attendance_in_id:
                self.attendance_in = attendance_in_id.id
            if attendance_out_id:
                self.attendance_out = attendance_out_id.id

    @api.multi
    @api.depends('attendance_in', 'attendance_out')
    def _compute_fingerprint(self):
        """ Need to view upkeep labour's fingerprint before HR import fingerprint data."""
        for record in self:
            if record.attendance_in or record.attendance_out:
                record.is_fingerprint = _('Yes')
            else:
                record.is_fingerprint = _('No')

    @api.multi
    def get_worked_days(self, ids):
        """
        Override estate_upkeep from estate payroll module.
        Number of worked days which has attendance required by salary rules
        :param ids: upkeep id
        :return:
        """
        number_of_days = 0
        att_obj = self.env['hr.attendance']

        for record in self.env['estate.upkeep.labour'].search([('id', 'in', ids)]):
            res = UpkeepFingerprint(att_obj.get_attendance(record.employee_id, record.upkeep_date, 'sign_in'),
                                    att_obj.get_attendance(record.employee_id, record.upkeep_date, 'sign_out'),
                                    record.attendance_code_id)

            att_rule = UpkeepFingerprintSpecification().\
                and_specification(SignInSpecification()).\
                and_specification(SignOutSpecification()).\
                and_specification(AttendanceCodeSpecification())

            if att_rule.is_satisfied_by(res):
                number_of_days += record['number_of_day']
        return number_of_days

    @api.multi
    def get_workhour(self, ids):
        """
        Override estate_upkeep from estate payroll module.
        Number of hours might be required by salary rules
        :param ids: upkeep labour
        :return: number of hours
        """
        workhour = 0.00
        att_obj = self.env['hr.attendance']
        att_estate_obj = self.env['estate.hr.attendance']
        for record in self.env['estate.upkeep.labour'].search([('id', 'in', ids)]):
            res = UpkeepFingerprint(att_obj.get_attendance(record.employee_id, record.upkeep_date, 'sign_in'),
                                    att_obj.get_attendance(record.employee_id, record.upkeep_date, 'sign_out'),
                                    record.attendance_code_id)

            att_rule = UpkeepFingerprintSpecification(). \
                and_specification(SignInSpecification()). \
                and_specification(SignOutSpecification()). \
                and_specification(AttendanceCodeSpecification())

            if att_rule.is_satisfied_by(res):
                att_code_id = record['attendance_code_id']['id']
                att_hour = att_estate_obj.search([('id', '=', att_code_id)]).unit_amount
                hour = record['number_of_day'] * att_hour
                workhour += hour
        return workhour

    @api.multi
    def get_wage_overtime(self, ids):
        """
        Override estate_upkeep from estate payroll module.
        Amount of piece rate required by salary rules
        :param ids: upkeep labour
        :return: wage overtime
        """
        amount = 0.00
        att_obj = self.env['hr.attendance']
        for record in self.env['estate.upkeep.labour'].search([('id', 'in', ids)]):
            res = UpkeepFingerprint(att_obj.get_attendance(record.employee_id, record.upkeep_date, 'sign_in'),
                                    att_obj.get_attendance(record.employee_id, record.upkeep_date, 'sign_out'),
                                    record.attendance_code_id)

            att_rule = UpkeepFingerprintSpecification(). \
                and_specification(SignInSpecification()). \
                and_specification(SignOutSpecification()). \
                and_specification(AttendanceCodeSpecification())

            if att_rule.is_satisfied_by(res):
                amount += record['wage_overtime']
        return amount

    @api.multi
    def get_wage_piece_rate(self, ids):
        """
        Override estate_upkeep from estate payroll module.
        Amount of piece rate required by salary rules
        :param ids: upkeep labour
        :return: wage piece rate
        """
        amount = 0.00
        att_obj = self.env['hr.attendance']
        for record in self.env['estate.upkeep.labour'].search([('id', 'in', ids)]):
            res = UpkeepFingerprint(att_obj.get_attendance(record.employee_id, record.upkeep_date, 'sign_in'),
                                    att_obj.get_attendance(record.employee_id, record.upkeep_date, 'sign_out'),
                                    record.attendance_code_id)

            att_rule = UpkeepFingerprintSpecification(). \
                and_specification(SignInSpecification()). \
                and_specification(SignOutSpecification()). \
                and_specification(AttendanceCodeSpecification())

            if att_rule.is_satisfied_by(res):
                amount += record['wage_piece_rate']
        return amount
