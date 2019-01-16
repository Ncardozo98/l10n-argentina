###############################################################################
#   Copyright (c) 2017-2018 Eynes/E-MIPS (http://www.e-mips.com.ar)
#   Copyright (c) 2014-2018 Aconcagua Team
#   License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).
###############################################################################

from odoo import fields, models


class IIBBSituation(models.Model):
    _name = 'iibb.situation'

    name = fields.Char(string='Name', required=True)
