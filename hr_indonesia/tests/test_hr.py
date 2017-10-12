# -*- coding: utf-8 -*-

from openerp import api
from openerp.tests import TransactionCase
from openerp.exceptions import ValidationError, AccessError


class TestMasterActivity(TransactionCase):
    def setUp(self):
        super(TestMasterActivity, self).setUp()
        # self.Employee = self.env['hr.employee']

        User = self.env['res.users'].with_context({'no_reset_password': True})
        self.Employee = self.env['hr.employee']

        # hr user
        group_user = self.ref('base.group_user')
        group_officer = self.ref('base.group_hr_user')
        group_hr_manager = self.ref('base.group_hr_manager')

        self.hr_employee = User.create({
            'name': 'Welsing', 'login': 'welsing', 'alias_name': 'welsing', 'email': 'welsing@welsing.com',
            'groups_id': [(6, 0, [group_user])]})
        self.hr_officer = User.create({
            'name': 'Meiske', 'login': 'meiske', 'alias_name': 'meiske', 'email': 'meiske@meiske.com',
            'groups_id': [(6, 0, [group_officer])]})
        self.hr_manager = User.create({
            'name': 'mertha', 'login': 'mertha', 'alias_name': 'mertha', 'email': 'mertha@mertha.com',
            'groups_id': [(6, 0, [group_hr_manager])]})

    def test_00_employee_check_employee(self):
        """Employee should have unique NIK and Identification"""

        person_cindy = {'name': 'Cindy', 'nik_number': '', 'identification_id': ''}
        person_crawford = {'name': 'Crawford', 'nik_number': '', 'identification_id': ''}
        person_jack = {'name': 'Jack', 'nik_number': '22', 'identification_id': '33'}
        person_pieter = {'name': 'Pieter', 'nik_number': '22', 'identification_id': ''}
        person_parker = {'name': 'Pieter', 'nik_number': '', 'identification_id': '33'}

        # I create an employee without NIK or Identification
        self.assertTrue(self.Employee.create(person_cindy))

        # I create second employee without NIK or Identification
        self.assertTrue(self.Employee.create(person_crawford))

        # I create an employee with NIK and Identification
        self.assertTrue(self.Employee.create(person_jack))

        # I create an employee with double NIK
        with self.assertRaises(ValidationError):
            self.assertTrue(self.Employee.create(person_pieter))

        # I create an employee with double Identification
        with self.assertRaises(ValidationError):
            self.assertTrue(self.Employee.create(person_parker))

    def test_01_create_department(self):
        """ Create department. Limit create access to officer only."""
        department_obj = self.env['hr.department']
        vals = {
            'name': 'Department'
        }

        # HR able to create department
        self.assertTrue(department_obj.sudo(self.hr_officer).create(vals))
        self.assertTrue(department_obj.sudo(self.hr_manager).create(vals))

        # Employee try to create department
        with self.assertRaises(AccessError):
            department_obj.sudo(self.hr_employee).create(vals)
    
    def test_01_create_job(self):
        """ Create job. Limit create access to officer only."""
        job_obj = self.env['hr.job']
        vals = {
            'name': 'Job'
        }

        # HR able to create job
        self.assertTrue(job_obj.sudo(self.hr_officer).create(vals))
        self.assertTrue(job_obj.sudo(self.hr_manager).create(vals))

        # Employee try to create job
        with self.assertRaises(AccessError):
            job_obj.sudo(self.hr_employee).create(vals)
