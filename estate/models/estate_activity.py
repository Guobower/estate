# -*- coding: utf-8 -*-

from openerp import models, fields, api, osv, _
from openerp.exceptions import ValidationError
import openerp.addons.decimal_precision as dp

class Activity(models.Model):
    _name = 'estate.activity'
    _description = 'Estate Activity'
    _parent_store = True
    _parent_name = 'parent_id'
    _order = 'complete_name'
    _rec_name = 'code_name'  # complete_name too long for upkeep entry
    _inherit = 'mail.thread'

    # Default methods
    def _default_user_company_id(self):
        ''' general account/analytic account required to limit based on users company_id or company_ids'''
        return self.env.user.company_id

    name = fields.Char("Name", required=True, help="Create unique activity name.")
    code = fields.Char("Activity Code", help='Choose your transaction code')
    complete_name = fields.Char("Complete Name", compute="_complete_name", store=True)
    code_name = fields.Char("Activity Name", compute="_complete_name", store=True, help='Use at entry')
    type = fields.Selection([('view', "View"),
                             ('normal', "Normal")], "Type",
                            required=True,
                            help="Select View to create group of activities.")
    # todo move to estate_account module
    # activity_income_id = fields.Many2one('account.account', "Income Account",
    #                                     help="This account will be used for invoices to value sales.")
    # activity_expense_id = fields.Many2one('account.account', "Expense Account",
    #                                     help="This account will be used for invoices to value expenses")
    comment = fields.Text("Additional Information")
    sequence = fields.Integer("Sequence", help="Keep activity in order as plantation stages.") # todo set as parent_left at create
    parent_id = fields.Many2one('estate.activity', "Parent Category", ondelete='restrict')
    parent_left = fields.Integer("Parent Left",	index=True)
    parent_right = fields.Integer("Parent Right", index=True)
    child_ids = fields.One2many('estate.activity', 'parent_id', "Child Activities")
    uom_id = fields.Many2one('product.uom', string="Basic Unit of Measurements")
    account_id = fields.Many2one('account.analytic.account', 'Analytic Account',
                                 domain=[('use_estate', '=', True), ('account_type', '=', 'normal')], # v9 use account_type
                                 help='Set as default analytic account at Upkeep.', track_visibility="onchange")
    general_account_id = fields.Many2one('account.account', 'General Account',
                                         help='Set as default general account. \n'\
                                              'Use company general account of current user.', track_visibility="onchange")
    qty_base = fields.Float(string="Standard Work Result/Day", digits=dp.get_precision('Estate'),
                            help="Set as default work's result.", track_visibility="onchange")
    qty_base_min = fields.Float(string="Minimum Work Result/Day", digits=dp.get_precision('Estate'),
                            help="It will be used when Activity Norm defined. Set as minimum work's result.")
    qty_base_max = fields.Float(string="Maximum Work Result/Day", digits=dp.get_precision('Estate'),
                            help="It will be used when Activity Norm defined. Set as maximum work's result.")
    ratio_min = fields.Float(compute='_compute_ratio', string="Minimum Work Result Ratio",
                             digits=dp.get_precision('Estate'), store=True,
                             help="Used to compute work day(s) per unit of measurement.")
    ratio_max = fields.Float(compute='_compute_ratio', string="Maximum Work Result Ratio",
                             digits=dp.get_precision('Estate'), store=True,
                             help="Used to compute work day(s) per unit of measurement.")
    parameter_weight_ids = fields.One2many(comodel_name='estate.parameter.weight', inverse_name='activity_id',
                                         string="Parameter Weight")
    activity_norm_ids = fields.One2many(comodel_name='estate.activity.norm', inverse_name='activity_id',
                                        string="Activity Norm")
    material_norm_ids = fields.One2many(comodel_name='estate.material.norm', inverse_name='activity_id',
                                        string="Standard Material")
    standard_price = fields.Float('Standard Price', digits=dp.get_precision('Standard Price'), track_visibility="onchange")
    piece_rate_price = fields.Float('Piece Rate Price', digits=dp.get_precision('Standard Price'),
                                    help='Empty value use standard price instead', track_visibility="onchange")
    activity_type = fields.Selection([('estate', 'Estate Activity'),
                                      ('vehicle', 'Vehicle activity'),
                                      ('general', 'General Affair Activity')],
                                     'Activity Type')
    wage_method = fields.Selection([('standard', 'Quantity Based'),
                                    ('attendance', 'Time Based')], 'Wage Method',
                                   default='standard', track_visibility="onchange",
                                   help='* Quantity Based, wage calculated by quantity and standard productivity/day.\n'
                                        '* Time Based, wage calculated by attendance code.')
    contract = fields.Boolean('Ignore standard productivity/day', default=False, track_visibility="onchange",
                              help='Calculate wage based on piece rate productivity.\n'
                                   'Use only if wage method set to Quantity Based.')
    user_company_id = fields.Many2one('res.company', 'Login User', help='Help to domain account based on user',
                                      default=_default_user_company_id)
    active = fields.Boolean('Active', default=True, track_visibility="onchange")
    location_type = fields.Selection([('nursery', 'Nursery'),
                                      ('planted', 'Planted'),
                                      ('emplacement', 'Emplacement')], 'Location Type',
                                     default='planted', track_visibility="onchange",
                                     help='It will be used to filter activity against location.')

    @api.one
    @api.depends('name', 'parent_id')
    def _complete_name(self):
        """ Forms complete name of location from parent category to child category.
        Help user entry using code.
        """
        if self.parent_id:
            self.complete_name = self.parent_id.complete_name + ' / ' + self.name
        else:
            self.complete_name = self.name

        if self.code:
            self.code_name = self.code + ' - ' + self.name
        else:
            self.code_name = self.name

        return True

    @api.one
    @api.depends('qty_base_min', 'qty_base_max')
    def _compute_ratio(self):
        """Ratio is another side of Quantity
        """
        if self.qty_base_min:
            self.ratio_min = 1/self.qty_base_min

        if self.qty_base_max:
            self.ratio_max = 1/self.qty_base_max

        return True

    @api.one
    @api.constrains('qty_base_min', 'qty_base_max', 'qty_base')
    def _check_qty_base_val(self):
        """Keep base quantity, min and max.
        """
        if self.qty_base_min or self.qty_base_max:
            if self.qty_base_min > self.qty_base_max:
                error_msg = _("Minimum should less than maximum.")
                raise ValidationError(error_msg)
            if self.qty_base < self.qty_base_min or self.qty_base > self.qty_base_max:
                error_msg = _("Base quantity must be in between of minimum and maximum quantity.")
                raise ValidationError(error_msg)

        return True

    @api.one
    @api.constrains('activity_norm_ids')
    def _check_parameter_value(self):
        """Keep activity norm unique per parameter and value
        """
        param_value = {}
        param_name_value = {}

        if self.parameter_weight_ids:
            for rec_param_value in self.parameter_weight_ids:
                param_name_value[rec_param_value.id] = rec_param_value.parameter_id.name

        if self.activity_norm_ids:
            for rec_value in self.activity_norm_ids:
                param_value_name = rec_value.parameter_value_id.name
                param_parent_name = rec_value.parameter_id.name
                if param_value_name in param_value.values():
                    error_msg = _("Parameter value \"%s\" is set more than once" % param_value_name)
                    raise ValidationError(error_msg)
                param_value[rec_value.id] = param_value_name
                if param_parent_name not in param_name_value.values():
                    # Empty parameter raise exceptions
                    error_msg = _("Norm's Parameter \"%s\" is not registered at Parameter Weight" % param_parent_name)
                    raise ValidationError(error_msg)
            return param_value

    @api.one
    @api.constrains('parameter_weight_ids')
    def _check_weight(self):
        """Total weight should be equal to 1 (standard work result and ratio)
        """
        total_weight = 0.00
        if self.parameter_weight_ids:
            for rec in self.parameter_weight_ids:
                total_weight += rec.weight
            if total_weight > 1.00:
                error_msg = _("Total Activity Parameter Weight should be less than or equal to 1")
                raise ValidationError(error_msg)
            return True

    @api.multi
    @api.constrains('contract', 'wage_method')
    def _check_contract_wage_method(self):
        """ Attendance based wage method should not be contractable."""
        for record in self:
            if record.wage_method == 'attendance' and record.contract:
                error_msg = _("Contract only allowed for standard based wage method.")
                raise ValidationError(error_msg)
            return True

    @api.multi
    @api.constrains('wage_method', 'contract', 'qty_base')
    def _check_qty_base(self):
        """ Standard quantity wage method should have standard work result/day to calculate quantity."""
        for record in self:
            if record.type == 'view':
                return True

            if record.wage_method == 'standard' and not record.qty_base:
                error_msg = _("You should set standard work result/day if attendance code is standard quantity/contract based.")
                raise ValidationError(error_msg)
            return True


    @api.one
    def get_qty(self):
        """Encapsulated selection algorithm
        :return: floating number
        """
        return self.qty_base

    @api.one
    def get_ratio(self):
        """Encapsulated selection algorithm
        :return: floating number
        """
        return self.ratio_min

    @api.multi
    def get_material_ids(self):
        """
        Get option of material according to available quantity or daily planning request
        :return: list of material object
        """
        material_obj = self.env['estate.material.norm']

        for record in self:
            material_ids = material_obj.search([('activity_id', 'in', record.ids),
                                                ('option', '=', True)], order='option asc, product_id.name asc')
            return material_ids


class ParameterWeight(models.Model):
    """Provide weighted prorate for multi activity parameter
    """
    _name = 'estate.parameter.weight'
    _description = 'Estate Parameter Weight'
    _order = 'parameter_id'

    activity_id = fields.Many2one('estate.activity')
    parameter_id = fields.Many2one('estate.parameter', string="Parameter")
    weight = fields.Float(string="Weight", digits=(3, 2),
                          help="Set weight value between 0 ... 1.")

    @api.one
    @api.constrains('weight')
    def _check_weight(self):
        if not 1 >= self.weight >= 0:
            error_msg = _("Weight value should between 0 and 1")
            raise ValidationError(error_msg)
        return True

class ActivityNorm(models.Model):
    """Set work's result based on estate parameter value
    """
    _name = 'estate.activity.norm'
    _description = 'Estate Activity Norm'
    _order = 'parameter_id, parameter_value_id'

    activity_id = fields.Many2one('estate.activity', string='Activity')
    parameter_id = fields.Many2one('estate.parameter', string="Parameter")
    parameter_value_id = fields.Many2one('estate.parameter.value', string="Parameter Value",
                                         domain="[('parameter_id', '=', parameter_id)]")
    coefficient = fields.Float(string="Coefficient", help="Set value between 0 ... 1.")
    qty_base = fields.Float(compute='_compute_qty_ratio', digits=(12, 6), store=True,
                            string="Work Result/Day")
    ratio_base = fields.Float(compute='_compute_qty_ratio', digits=(12, 6), store=True,
                              string="Work Result Ratio")
    activity_qty_base = fields.Float(related='activity_id.qty_base', store=True, readonly=True)
    activity_qty_base_min = fields.Float(related='activity_id.qty_base_min', store=True, readonly=True)
    activity_qty_base_max = fields.Float(related='activity_id.qty_base_max', store=True, readonly=True)
    activity_ratio_min = fields.Float(related='activity_id.ratio_min', store=True, readonly=True)
    activity_ratio_max = fields.Float(related='activity_id.ratio_max',  store=True, readonly=True)

    @api.multi
    @api.depends('coefficient', 'activity_qty_base', 'activity_qty_base_min', 'activity_qty_base_max', 'activity_ratio_min', 'activity_ratio_max')
    def _compute_qty_ratio(self):
        """
        Activity Norm should recompute
        :return:
        """
        for rec in self:
            # New line create blank related line
            if not (rec.activity_qty_base or rec.activity_qty_base_min or rec.activity_qty_base_max
                    or rec.activity_ratio_min or rec.activity_ratio_max):
                rec.activity_qty_base = rec.activity_id.qty_base
                rec.activity_qty_base_min = rec.activity_id.qty_base_min
                rec.activity_qty_base_max = rec.activity_id.qty_base_max
                rec.activity_ratio_min = rec.activity_id.ratio_min
                rec.activity_ratio_max = rec.activity_id.ratio_max

            # Get parameter weight based on parameter
            weight = 1.00 # put to prevent compute_norm return 0
            for param in rec.activity_id.parameter_weight_ids:
                if rec.parameter_id == param.parameter_id:
                    weight = param.weight

            if rec.parameter_id and rec.parameter_value_id:
                rec.qty_base = rec.compute_norm(rec.coefficient, weight, 1)
                rec.ratio_base = rec.compute_norm(rec.coefficient, weight, 2)
                return True
            else:
                return False

    @api.multi
    def compute_norm(self, coefficient, weight, type):
        """
        Get base quantity and ratio based on activity parameter value's coefficient.
        :param coefficient: activity norm coefficient
        :param weight: parameter weight
        :param type: [1] quantity base [2] ratio base
        :return: float
        """
        for rec in self:
            if rec.activity_qty_base_min and rec.activity_qty_base_max:
                if type == 1:
                    min = rec.activity_qty_base_min
                    max = rec.activity_qty_base_max
                    return (min + (coefficient * abs(max-min))) * weight
                if type == 2:
                    # min = rec.activity_ratio_min
                    # max = rec.activity_ratio_max
                    try:
                        return 1/rec.qty_base
                    except ZeroDivisionError:
                        return 0
            else:
                return False

    @api.multi
    @api.constrains('coefficient')
    def _check_coefficient(self):
        for rec in self:
            if not 1 >= rec.coefficient >= 0:
                error_msg = _("Coefficient should in between 0 and 1")
                raise ValidationError(error_msg)


class MaterialNorm(models.Model):
    _name = 'estate.material.norm'
    _description = 'Estate Material Norm'
    _order = 'option asc'

    activity_id = fields.Many2one('estate.activity', 'Activity')
    option = fields.Integer('Option Group', help='Set 1, 2, 3, ... to be material option. Lowest number process first.'\
                                                 'One or more material could share same option number.'\
                                                 'Only first option will be used as reference')  # check stock, move next option if empty
    product_id = fields.Many2one('product.product', 'Material', domain=[('categ_id.estate_product', '=', True)])
    product_uom_id = fields.Many2one('product.uom', 'Material Unit of Measure', related='product_id.uom_id',
                                      readonly=True)
    standard_price = fields.Float('Standard Price', related='product_id.standard_price', digits=dp.get_precision('Account'))
    unit_amount = fields.Float('Required Unit Amount', digits=dp.get_precision('Estate'),
                               help="Define unit amount of material product UoM per activity UoM.")
    qty_available = fields.Float('Quantity on Hand', related='product_id.qty_available',
                                 digits=dp.get_precision('Product Unit of Measure'))  # todo use at daily planning purpose
    comment = fields.Text('Additional Information', help='Notes for material mixing/usage.')


class Operation(models.Model):
    """Record daily field operation
    """
    _name = 'estate.operation'

    state = fields.Selection([('0', 'Draft'),
                              ('1', 'Confirmed'),
                              ('2', 'Approved')],
                             "State")