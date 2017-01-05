from openerp import models, fields, api, exceptions
from psycopg2 import OperationalError

from openerp import SUPERUSER_ID
import openerp
import openerp.addons.decimal_precision as dp
from openerp.tools import float_compare, float_is_zero
from datetime import datetime, date,time
from openerp.exceptions import ValidationError
from dateutil.relativedelta import *
import calendar
from openerp import tools
import re

class InheritPurchaseRequisition(models.Model):
    _inherit = 'purchase.requisition'

    owner_id = fields.Integer('owner id')

class InheritPurchaseRequest(models.Model):

    _inherit = 'purchase.request'
    _rec_name = 'complete_name'
    _order = 'complete_name desc'

    complete_name =fields.Char("Complete Name", compute="_complete_name", store=True)
    type_purchase = fields.Many2one('purchase.indonesia.type','Purchase Type')
    type_functional = fields.Selection([('agronomy','Agronomy'),
                                     ('technic','Technic'),('general','General')],'Unit Functional')
    department_id = fields.Many2one('hr.department','Department')
    employee_id = fields.Many2one('hr.employee','Employee')
    type_location = fields.Selection([('KOKB','Estate'),
                                     ('KPST','HO'),('KPWK','RO')],'Location Type')
    type_product = fields.Selection([('consu','Capital'),
                                     ('service','Service'),('product','Stockable Product')],'Location Type')
    type_budget = fields.Selection([('available','Budget Available'),('not','Budget Not Available')])
    tracking_approval_ids = fields.One2many('tracking.approval','owner_id','Tracking Approval List')
    state = fields.Selection(
        selection_add=[('done','Done'),('confirm','Confirm'),('approval1', 'Dept Head Approval'),
                       ('approval2', 'Div Head Approval'),
                       ('budget', 'Budget Approval'),
                       ('technic1', 'Technic Dept Head Approval'),
                       ('technic2', 'Technic Div Head Approval'),
                       ('technic3', 'Technic ICT Dept Approval'),
                       ('technic4', 'Technic GM Plantation Dept Approval'),
                       ('technic5', 'Technic EA Dept Approved'),
                       ('approval3','Department Head Finance Approval'),
                       ('approval4','Div Head Finance  Approval'),
                       ('approval5','Director Approval'),('approval6','President Director Approval'),
                       ('reject','Reject')])
    currency_id = fields.Many2one('res.currency', 'Currency', required=True,
        default=lambda self: self.env.user.company_id.currency_id)
    reject_reason = fields.Text('Reject Reason')
    total_estimate_price = fields.Float('Total Estimated Price',compute='_compute_total_estimate_price')
    pta_code =  fields.Char('Additional budget request')


    @api.multi
    def button_rejected(self):
        self.write({'state': 'reject', 'date_request': self.date_start})
        self.write({'description':self.reject_reason})
        return True

    @api.multi
    def action_financial_approval1(self):
        """ Confirms department HeadFinancial Approval.
        """
        price_standard = self.env['purchase.params.setting'].search([('name','=',self._name),('value_params','=',1000000)]).value_params
        total_price_purchase = float(sum(record.total_price for record in self.line_ids))
        if total_price_purchase < float(price_standard):
            self.button_approved()
        elif total_price_purchase > float(price_standard):
            state_data = {'state':'approval4'}
            self.write(state_data)

    @api.multi
    def action_financial_approval2(self):
        """ Confirms Division Head Financial Approval.
        """
        price_standard1 = self.env['purchase.params.setting'].search([('name','=',self._name),('value_params','=',10000000)]).value_params
        total_price_purchase = float(sum(record.total_price for record in self.line_ids))
        if total_price_purchase < float(price_standard1):
                self.button_approved()
        elif total_price_purchase > float(price_standard1):
            state_data = {'state':'approval5'}
            self.write(state_data)

    @api.multi
    def action_financial_approval3(self):
        """ Confirms Director  Financial Approval.
        """
        price_standard2 = self.env['purchase.params.setting'].search([('name','=',self._name),('value_params','=',50000000)]).value_params
        total_price_purchase = float(sum(record.total_price for record in self.line_ids))
        if total_price_purchase < (price_standard2):
                self.button_approved()
        elif total_price_purchase > float(price_standard2):
            state_data = {'state':'approval6'}
            self.write(state_data)
            self.button_approved()

    @api.multi
    def action_financial_approval4(self):
        """ Confirms President Director Approval.
        """
        self.button_approved()

    @api.multi
    def button_approved(self):
        self.tracking_approval()
        self.create_purchase_requisition()
        self.create_quotation_comparison_form()
        super(InheritPurchaseRequest, self).button_approved()
        return True

    @api.multi
    def action_confirm1(self,):
        """ Confirms User request.
        """
        self.check_wkf_product_price()
        return True

    @api.multi
    def action_confirm2(self,):
        """ Confirms Good request.
        """
        price_standard = self.env['purchase.params.setting'].search([('name','=',self._name),('value_params','=',1000000)]).value_params
        total_price_purchase = float(sum(record.total_price for record in self.line_ids))
        if self.type_functional == 'agronomy' and total_price_purchase < price_standard :
            state_data = {'state':'technic4'}
            self.write(state_data)
        elif self.type_functional == 'technic' and total_price_purchase < price_standard:
            state_data = {'state':'technic5'}
            self.write(state_data)
        elif self.type_functional == 'general' and total_price_purchase < price_standard:
            state_data = {'state':'technic3'}
            self.write(state_data)
        elif self.type_functional == 'agronomy' and total_price_purchase > price_standard :
            state_data = {'state':'technic4'}
            self.write(state_data)
        elif self.type_functional == 'technic' and total_price_purchase > price_standard:
            state_data = {'state':'technic5'}
            self.write(state_data)
        elif self.type_functional == 'general' and total_price_purchase > price_standard:
            state_data = {'state':'technic3'}
            self.write(state_data)
        return True

    @api.multi
    def action_budget(self,):
        """ Confirms Budget request.
        """
        self.tracking_approval()
        self.write({'state': 'approval3'})
        if self.type_budget== 'not' and self.pta_code == False:
            raise exceptions.ValidationError('Input Your PTA Number')
        else:
            return True

    @api.multi
    def action_techic(self,):
        """ Confirms Technical request.
        """
        self.tracking_approval()
        self.write({'state': 'budget'})
        return True

    @api.multi
    def check_wkf_requester(self):
        arrJobs = []
        arrJobs2 = []
        user= self.env['res.users'].browse(self.env.uid)
        employee = self.env['hr.employee'].search([('user_id','=',user.id)])
        jobs = self.env['hr.job'].search([('id','=',employee.job_id.id)]).id
        jobs_compare_hr = self.env['hr.job'].search([('name','in',['HR','hr','HR & GA Head Assistant','hr & GA  Head Assistant'])])
        jobs_non_hr = self.env['hr.job'].search([('name','not in',['HR','hr','HR & GA Head Assistant','hr & GA  Head Assistant'])])
        for item in jobs_non_hr:
            arrJobs2.append(item.id)
        for record_job in jobs_compare_hr:
            arrJobs.append(record_job.id)
        if jobs in arrJobs:
            self.tracking_approval()
            self.write({'state':'confirm'})
            state_data = {'state':'approval2'}
            self.write(state_data)
        elif jobs in arrJobs2:
            self.tracking_approval()
            self.write({'state':'confirm'})
            state_data = {'state':'approval1'}
            self.write(state_data)


    @api.multi
    def check_wkf_product_price(self):
       #check total product price in purchase request
       price_standard = self.env['purchase.params.setting'].search([('name','=',self._name),('value_params','=',1000000)]).value_params
       total_price_purchase = float(sum(record.total_price for record in self.line_ids))
       if total_price_purchase >= price_standard:
            self.tracking_approval()
            state_data = {'state':'approval2'}
            self.write(state_data)
       if self.type_functional == 'agronomy' and total_price_purchase < price_standard :
            state_data = {'state':'technic4'}
            self.write(state_data)
       elif self.type_functional == 'technic' and total_price_purchase < price_standard:
            state_data = {'state':'technic5'}
            self.write(state_data)
       elif self.type_functional == 'general' and total_price_purchase < price_standard:
            state_data = {'state':'technic3'}
            self.write(state_data)

    @api.multi
    def check_wkf_product(self):
        #check Workflow Product and availability budget

        price_standard = self.env['purchase.params.setting'].search([('name','=',self._name),('value_params','=',1000000)]).value_params
        total_price_purchase = sum(record.total_price for record in self.line_ids)
        if self.type_functional == 'agronomy' and total_price_purchase < price_standard :
            state_data = {'state':'technic4'}
            self.write(state_data)
        elif self.type_functional == 'technic' and total_price_purchase < price_standard:
            state_data = {'state':'technic5'}
            self.write(state_data)
        elif self.type_functional == 'general' and total_price_purchase < price_standard:
            state_data = {'state':'technic3'}
            self.write(state_data)
        elif total_price_purchase > price_standard:
            state_data = {'state':'technic1'}
            self.write(state_data)
        else :
            state_data = {'state':'technic2'}
            self.write(state_data)

    @api.multi
    def tracking_approval(self):
        user= self.env['res.users'].browse(self.env.uid)
        employee = self.env['hr.employee'].search([('user_id','=',user.id)]).name_related
        current_date=str(datetime.now().today())
        tracking_data = {
            'owner_id': self.id,
            'state' : self.state,
            'name_user' : employee,
            'datetime'  :current_date
        }
        self.env['tracking.approval'].create(tracking_data)


    @api.multi
    def create_purchase_requisition(self):
        # Create Purchase Requisition
        for purchase in self:
            purchase_data = {
                'responsible':purchase.requested_by.id,
                'companys_id' :purchase.company_id.id,
                'type_location' : purchase.type_location,
                'origin': purchase.complete_name,
                'ordering_date' : purchase.date_start,
                'schedule_date': purchase.date_start,
                'owner_id' : purchase.id
            }
            res = self.env['purchase.requisition'].create(purchase_data)

        for purchaseline in self.env['purchase.request.line'].search([('request_id.id','=',self.id)]):
            purchaseline_data = {
                'product_id': purchaseline.product_id.id,
                'product_uom_id': purchaseline.product_uom_id.id,
                'product_qty' : purchaseline.product_qty,
                'schedule_date' : purchaseline.date_start,
                'requisition_id' : res.id
            }
            self.env['purchase.requisition.line'].create(purchaseline_data)

        return True

    @api.multi
    def create_quotation_comparison_form(self):
        purchase_requisition = self.env['purchase.requisition'].search([('origin','like',self.complete_name)])
        purchase_data = {
                'company_id': purchase_requisition.companys_id.id,
                'date_pp': purchase_requisition.schedule_date,
                'requisition_id': purchase_requisition.id,
                'origin' : purchase_requisition.origin,
                'type_location' : purchase_requisition.type_location
            }
        res = self.env['quotation.comparison.form'].create(purchase_data)

    @api.one
    @api.depends('name','date_start','company_id','department_id')
    def _complete_name(self):
        """ Forms complete name of location from parent category to child category.
        """
        fmt = '%Y-%m-%d'

        if self.name and self.date_start and self.company_id.code and self.department_id:
            date = self.date_start
            conv_date = datetime.strptime(str(date), fmt)
            month = conv_date.month
            year = conv_date.year

            #change integer to roman
            if type(month) != type(1):
                raise TypeError, "expected integer, got %s" % type(month)
            if not 0 < month < 4000:
                raise ValueError, "Argument must be between 1 and 3999"
            ints = (1000, 900,  500, 400, 100,  90, 50,  40, 10,  9,   5,  4,   1)
            nums = ('M',  'CM', 'D', 'CD','C', 'XC','L','XL','X','IX','V','IV','I')
            result = ""
            for i in range(len(ints)):
              count = int(month / ints[i])
              result += nums[i] * count
              month -= ints[i] * count
            month = result

            departement_code = ''

            try :
                departement_code = self.department_id.code
            except:
                departement_code = self.department_id.name

            if self.department_id.code == False:
                raise exceptions.ValidationError('Department Code is Null')
            else:
                self.complete_name = self.name + '/' \
                                         + self.company_id.code+'-'\
                                         +'PP'+'/'\
                                         +departement_code+'/'+str(month)+'/'+str(year)
        else:
            self.complete_name = self.name

        return True

    @api.multi
    def print_purchase_request(self):
        return self.env['report'].get_action(self, 'purchase_indonesia.report_purchase_request')

    @api.multi
    @api.depends('line_ids')
    def _compute_total_estimate_price(self):
        self.total_estimate_price = sum(record.total_price for record in self.line_ids)

    @api.multi
    @api.onchange('type_location')
    def _onchange_functional(self):
        if self.type_location == 'KPST':
            self.type_functional = 'general'
        else:
            self.type_functional

    @api.multi
    @api.onchange('type_functional')
    def _onchange_department(self):
        arrDepartment = []
        if self.type_functional == 'agronomy':
            department = self.env['hr.department'].search([('name','in',['agronomi','Agronomi',
                                                                         'Agronomy','agronomy','PR & LA','Pr & La',
                                                                         'PR&LA','pr & la','pr&la'])])
            for department in department:
                arrDepartment.append(department.id)
            return {
                'domain':{
                    'department_id':[('id','in',arrDepartment)]
                }
            }
        if self.type_functional == 'technic':
            department = self.env['hr.department'].search([('name','in',['IE','transport & workshop','Transport & Workshop'])])
            for department in department:
                arrDepartment.append(department.id)
            return {
                'domain':{
                    'department_id':[('id','in',arrDepartment)]
                }
            }
        if self.type_functional == 'general':
            department = self.env['hr.department'].search([('name','in',['HR & GA','HR','GA',
                                                                         'ICT','Finance','Legal','Procurement','GIS','RO'])])
            for department in department:
                arrDepartment.append(department.id)
            return {
                'domain':{
                    'department_id':[('id','in',arrDepartment)]
                }
            }

    @api.multi
    @api.onchange('department_id')
    def _onchange_employee(self):
        #onchange employee by Department
        arrEmployee=[]
        if self.department_id:

            employee = self.env['hr.employee'].search([('department_id.id','=',self.department_id.id)])
            for employeelist in employee:
                arrEmployee.append(employeelist.id)
            return {
                'domain':{
                    'employee_id' :[('id','in',arrEmployee)]
                }
            }

    @api.multi
    @api.onchange('employee_id')
    def _onchange_department_from_employee(self):

        if self.employee_id:
           self.assigned_to = self.employee_id.parent_id.id
           self.department_id = self.employee_id.department_id.id
           self.company_id = self.employee_id.company_id.id
           department1 = self.env['hr.department'].search([('name','in',['agronomi','Agronomi','Agronomy','agronomy','PR & LA','Pr & La','PR&LA','pr & la','pr&la'])])
           department2 = self.env['hr.department'].search([('name','in',['IE','transport & workshop','Transport & Workshop'])])
           department3 = self.env['hr.department'].search([('name','in',['HR & GA','HR','GA','ICT','Finance','Legal','Procurement','GIS','RO'])])
           if department1 :
                self.type_functional = 'agronomy'
           if department2 :
                self.type_functional = 'technic'
           if department3 :
                self.type_functional = 'general'

    @api.multi
    @api.onchange('line_ids')
    def _onchange_budget_type(self):
        arrBudget = []
        for item in self.line_ids:
            if item.budget_available <= 0:
                self.type_budget = 'not'
            if item.budget_available > 0:
                self.type_budget = 'available'


class InheritPurchaseRequestLine(models.Model):

    _inherit = 'purchase.request.line'
    _description = 'Inherit Purchase Request Line'

    price_per_product = fields.Float('Prod Price')
    total_price = fields.Float('Total Price',compute='_compute_total_price')
    budget_available = fields.Float('Budget Available')

    @api.multi
    @api.depends('price_per_product','product_qty')
    def _compute_total_price(self):
        for price in self:
            if price.product_qty and price.price_per_product:
                price.total_price = price.product_qty * price.price_per_product

    @api.multi
    @api.onchange('product_id')
    def _onchange_price_per_product(self):
        arrLisproduct = []
        arrPrice =[]
        if self.product_id:
            product = self.env['product.product'].search([('id','=',self.product_id.id)])
            for product in product:
                arrLisproduct.append(product.product_tmpl_id.id)
            product_temp = self.env['product.price.history'].search([('product_id','in',arrLisproduct)])
            for producttemp in product_temp:
                arrPrice.append(producttemp.cost)
            for price in arrPrice:
                price = float(price)
                self.price_per_product = price

    @api.multi
    @api.onchange('analytic_account_id')
    def _onchange_budget_available(self):
        arrBudget = []
        if self.analytic_account_id:
            budget = self.env['crossovered.budget.lines'].search([('analytic_account_id','=',self.analytic_account_id.id)])
            for budget in budget:
                arrBudget.append(budget.planned_amount)
            for amount in arrBudget:
                amount = float(amount)
                self.budget_available = amount

    @api.multi
    @api.onchange('request_id','product_id')
    def _onchange_product_purchase_request_line(self):
        #use to onchange domain product same as product_category
        if self.request_id.type_functional and self.request_id.department_id:
            arrProductCateg = []
            mappingFuntional = self.env['mapping.department.product'].search([('type_functional','=',self.request_id.type_functional),
                                                                              ('department_id.id','=',self.request_id.department_id.id)])
            for productcateg in mappingFuntional:
                arrProductCateg.append(productcateg.product_category_id.id)
            arrProdCatId = []
            prod_categ = self.env['product.category'].search([('parent_id','in',arrProductCateg)])
            for productcategparent in prod_categ:
                arrProdCatId.append(productcategparent.id)
            if prod_categ:
                return  {
                    'domain':{
                        'product_id':[('categ_id','in',arrProdCatId)]
                         }
                    }
            elif prod_categ != ():
                return  {
                    'domain':{
                        'product_id':[('categ_id','in',arrProductCateg)]
                         }
                    }






