###############################################################################
#   Copyright (C) 2008-2011  Thymbra
#   Copyright (c) 2012-2018 Eynes/E-MIPS (http://www.e-mips.com.ar)
#   Copyright (c) 2014-2018 Aconcagua Team
#   License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).
###############################################################################

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class AccountPaymentOrder(models.Model):
    _name = 'account.payment.order'
    _inherit = 'account.payment.order'

    issued_check_ids = fields.One2many(
        comodel_name='account.issued.check',
        inverse_name='payment_order_id',
        string='Issued Checks',
        readonly=True, required=False,
        states={'draft': [('readonly', False)]})
    third_check_receipt_ids = fields.One2many(
        comodel_name='account.third.check',
        inverse_name='source_payment_order_id',
        string='Third Checks',
        readonly=True, required=False,
        states={'draft': [('readonly', False)]})
    third_check_ids = fields.Many2many(
       comodel_name='account.third.check',
       relation='third_check_voucher_rel',
       column1='dest_payment_order_id',
       column2='third_check_id',
       string='Third Checks', readonly=True,
       states={'draft': [('readonly', False)]})

    @api.multi
    def _amount_checks(self):
        self.ensure_one()
        res = {}
        res['issued_check_amount'] = 0.00
        res['third_check_amount'] = 0.00
        res['third_check_receipt_amount'] = 0.00
        if self.issued_check_ids:
            for issued_check in self.issued_check_ids:
                res['issued_check_amount'] += issued_check.amount
        if self.third_check_ids:
            for third_check in self.third_check_ids:
                res['third_check_amount'] += third_check.amount
        if self.third_check_receipt_ids:
            for third_rec_check in self.third_check_receipt_ids:
                res['third_check_receipt_amount'] += third_rec_check.amount
        return res

    @api.multi
    def _get_issued_checks_amount(self):
        # TODO: testear que este metodo funcione
        # issued_check_obj = self.pool.get('account.issued.check')
        amount = 0.0
        for check in self.issued_check_ids:
            am = check.amount
            if am:
                amount += float(am)

        # for check in self.issued_check_ids:
        #     if check[0] == 4 and check[1] and not check[2]:
        #         # am = issued_check_obj.read(cr, uid, check[1], ['amount'], context=context)['amount']
        #         am = check.amount
        #         if am:
        #             amount += float(am)
        #     if check[2]:
        #         amount += check[2]['amount']
        return amount

    @api.multi
    def _get_third_checks_amount(self):
        # TODO: testear que este metodo funcione
        # third_check_obj = self.pool.get('account.third.check')
        amount = 0.0
        for check in self.third_check_ids:
            am = check.amount
            if am:
                amount += am
        # for check in self.third_check_ids:
        #     if check[0] == 6 and check[2]:
        #         for c in check[2]:
        #             # am = third_check_obj.read(cr, uid, c, ['amount'], context=context)['amount']
        #             am = check.amount
        #             if am:
        #                 amount += float(am)
        return amount

    @api.multi
    def _get_third_checks_receipt_amount(self):
        # TODO: testear que este metodo funcione
        # third_check_obj = self.pool.get('account.third.check')
        amount = 0.0

        for check in self.third_check_receipt_ids:
            am = check.amount
            if am:
                amount += am
        # for check in self.third_check_ids:
        #     if check[0] == 4 and check[1] and not check[2]:
        #         # am = third_check_obj.read(cr, uid, check[1], ['amount'], context=context)['amount']
        #         am = check.amount
        #         if am:
        #             amount += float(am)
        #     if check[2]:
        #         amount += check[2]['amount']

        return amount

    @api.onchange('third_check_receipt_ids')
    def onchange_third_receipt_checks(self):
        amount = self._get_payment_lines_amount()
        amount += self._get_third_checks_receipt_amount()

        self.amount = amount

    @api.onchange('payment_mode_line_ids')
    def onchange_payment_line(self):
        amount = self._get_payment_lines_amount()
        amount += self._get_issued_checks_amount()
        amount += self._get_third_checks_amount()
        amount += self._get_third_checks_receipt_amount()

        self.amount = amount

    @api.onchange('issued_check_ids')
    def onchange_issued_checks(self):
        amount = self._get_payment_lines_amount()
        amount += self._get_issued_checks_amount()
        amount += self._get_third_checks_amount()

        self.amount = amount

    @api.onchange('third_check_ids')
    def onchange_third_checks(self):
        amount = self._get_payment_lines_amount()
        amount += self._get_issued_checks_amount()
        amount += self._get_third_checks_amount()

        self.amount = amount

    @api.multi
    def unlink(self):
        for voucher in self:
            voucher.third_check_ids.unlink()
            voucher.issued_check_ids.unlink()
            super(AccountPaymentOrder, voucher).unlink()

    @api.multi
    def create_move_line_hook(self, move_id, move_lines):
        move_lines = super(AccountPaymentOrder, self).create_move_line_hook(move_id, move_lines)

        if self.type in ('sale', 'receipt'):
            for check in self.third_check_receipt_ids:
                if check.amount == 0.0:
                    continue

                res = check.create_voucher_move_line(self)
                res['move_id'] = move_id
                move_lines.append(res)
                check.to_wallet()

        elif self.type in ('purchase', 'payment'):
            # Cheques recibidos de terceros que los damos a un proveedor
            for check in self.third_check_ids:
                if check.amount == 0.0:
                    continue

                res = check.create_voucher_move_line(self)
                res['move_id'] = move_id
                move_lines.append(res)
                check.check_delivered()

            # Cheques propios que los damos a un proveedor
            for check in self.issued_check_ids:
                if check.amount == 0.0:
                    continue

                res = check.create_voucher_move_line()
                res['move_id'] = move_id
                res['issued_check_id'] = check.id
                move_lines.append(res)

                if check.type == 'postdated':
                    state = 'waiting'
                else:
                    state = 'issued'

                vals = {
                    'state': state,
                    'payment_move_id': move_id,
                    'receiving_partner_id': self.partner_id.id
                }

                if not check.origin:
                    vals['origin'] = self.reference

                if not check.issue_date:
                    vals['issue_date'] = self.date
                check.write(vals)

        return move_lines

#    def add_precreated_check(self, cr, uid, ids, context=None):
#        third_obj = self.pool.get('account.third.check')
#
#        partner_id = self.read(cr, uid, ids[0], ['partner_id'], context)['partner_id'][0]
#        # Buscamos todos los cheques de terceros del partner del voucher
#        # y que esten en estado 'draft'
#        check_ids = third_obj.search(cr, uid, [('source_partner_id','=',partner_id), ('state','=','draft'),('payment_order_id','=',False)], context=context)
#
#        if check_ids:
#            third_obj.write(cr, uid, check_ids, {'payment_order_id': ids[0]}, context)
#
#        return True

    @api.multi
    def cancel_voucher(self):
        res = super(AccountPaymentOrder, self).cancel_voucher()

        for voucher in self:
            # Cancelamos los cheques de tercero en recibos
            third_receipt_checks = voucher.third_check_receipt_ids
            third_receipt_checks.cancel_check()

            # Volvemos a cartera los cheques de tercero en pagos
            third_checks = voucher.third_check_ids
            third_checks.return_wallet()

            # Cancelamos los cheques emitidos
            issued_checks = voucher.issued_check_ids
            for check in issued_checks:
                if check.type == 'postdated' and check.accredited:
                    err = _('Check number %s is postdated and has already been accredited!\nPlease break the conciliation of that check first.') % check.number
                    raise ValidationError(err)

            issued_checks.cancel_check()

        return res

    @api.multi
    def action_cancel_draft(self):
        res = super(AccountPaymentOrder, self).action_cancel_draft()
        for voucher in self:
            # A draft los cheques emitidos
            issued_checks = voucher.issued_check_ids
            issued_checks.write({'state': 'draft'})

            # A draft los cheques de tercero en cobros
            third_checks = voucher.third_check_receipt_ids
            third_checks.write({'state': 'draft'})

        return res
