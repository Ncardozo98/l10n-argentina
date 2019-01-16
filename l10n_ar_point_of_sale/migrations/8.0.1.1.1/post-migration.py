###############################################################################
#   Copyright (c) 2017-2018 Eynes/E-MIPS (http://www.e-mips.com.ar)
#   Copyright (c) 2014-2018 Aconcagua Team
#   License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).
###############################################################################

import psycopg2
import logging

logger = logging.getLogger(__name__)


def _do_update(cr, installed_version):
    try:
        q = """
            SELECT pos_ar_id, pos_ar_name, shop_id FROM old_denomination
        """
        cr.execute(q)
        res = cr.fetchall()
        for tup in res:
            pos_ar_id, pos_ar_name, shop_id = tup
            cr.execute("SELECT id FROM pos_ar WHERE name ~ %(name)s AND write_date IS NULL", {'name': pos_ar_name})
            if cr.rowcount:
                newid, = cr.fetchone()
                q = """
                    UPDATE old_denomination
                    SET new_pos_ar_id=%(newid)s
                    WHERE pos_ar_id=%(pos_ar_id)s
                """
                q_p = {
                    'newid': newid,
                    'pos_ar_id': pos_ar_id
                }
                cr.execute(q, q_p)
            else:
                q = """
                    INSERT INTO pos_ar
                        (name, priority, shop_id, "desc")
                    VALUES
                        (%(name)s, 0, %(shop_id)s, %(desc)s)
                    RETURNING id
                """
                q_params = {
                    'shop_id': shop_id,
                    'name': pos_ar_name,
                    'desc': pos_ar_name + ': A,B'
                }
                cr.execute(q, q_params)
                newid, = cr.fetchone()
                q = """
                    UPDATE old_denomination
                    SET new_pos_ar_id=%(newid)s
                    WHERE pos_ar_id=%(pos_ar_id)s
                """
                q_p = {
                    'newid': newid,
                    'pos_ar_id': pos_ar_id
                }
                cr.execute(q, q_p)
        # Update invoices with corresponding new pos_ar
        q = """
            WITH q1 AS (
                SELECT ai.id,od.new_pos_ar_id
                FROM account_invoice ai
                    JOIN old_denomination od ON od.pos_ar_id=ai.pos_ar_id
                )
            UPDATE account_invoice ai SET pos_ar_id=q1.new_pos_ar_id FROM q1 WHERE q1.id=ai.id;
        """
        cr.execute(q)
        # Relate new pos_ar & with denominations
        q = """
            WITH qz AS (
                SELECT new_pos_ar_id pos_ar_id, denomination_id
                FROM old_denomination
            ) INSERT INTO posar_denomination_rel (pos_ar_id, denomination_id)
            SELECT pos_ar_id, denomination_id FROM qz;
        """
        cr.execute(q)
        # Deactivate old pos_ar
        cr.execute("UPDATE pos_ar SET active=False WHERE id IN (SELECT pos_ar_id FROM old_denomination)")
    except psycopg2.ProgrammingError as e:
        logger.warning(e)
        cr.rollback()
    except Exception as e:
        logger.warning(e)
        cr.rollback()
    else:
        cr.commit()


def migrate(cr, installed_version):
    return _do_update(cr, installed_version)
