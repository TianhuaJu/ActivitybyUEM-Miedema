# database_handler.py
import os
import sqlite3
import math
import re

HANDLER_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(HANDLER_DIR, '..', 'database', 'data', 'DataBase.db')
DB_PATH = os.path.normpath(DB_PATH)

def get_miedema_data(element_name):
    """从数据库加载元素的 Miedema 参数。"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        query = "SELECT phi, nws, V, u, alpha_beta, hybirdvalue, isTrans, dHtrans, mass, Tm, Tb FROM MiedemaParameter WHERE Symbol = ?"
        cursor.execute(query, (element_name,))
        row = cursor.fetchone()
        conn.close()
        return row
    except Exception as e:
        print(f"加载元素数据时出错 ({element_name}): {e}")
        return None

def query_first_order_wagner_intp_db(solv, solui, soluj):
    """从数据库查询一阶瓦格纳相互作用参数。"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        query1 = "SELECT eji, Rank, sji, T, reference FROM first_order WHERE solv = ? AND solui = ? AND soluj = ?"
        cursor.execute(query1, (solv, solui, soluj))
        row1 = cursor.fetchone()

        if row1:
            conn.close()
            return row1, True # ji_flag = True

        query2 = "SELECT eji, Rank, sji, T, reference FROM first_order WHERE solv = ? AND solui = ? AND soluj = ?"
        cursor.execute(query2, (solv, soluj, solui))
        row2 = cursor.fetchone()

        conn.close()
        return row2, False # ij_flag = True, or None if not found

    except Exception as e:
        print(f"查询一阶瓦格纳相互作用参数时出错: {e}")
        return None, None


def query_ln_yi0_db(solv, solui):
    """从数据库查询无限稀释活度系数。"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        query = "SELECT lnYi0, Yi0, T FROM lnY0 WHERE solv = ? AND solui = ?"
        cursor.execute(query, (solv, solui))
        row = cursor.fetchone()
        conn.close()
        return row
    except Exception as e:
        print(f"查询无限稀释活度系数时出错: {e}")
        return None

class Melt:
    """Melt 类，用于存储和处理来自数据库的熔体组分间活度相互作用系数。"""

    def __init__(self, solv, solui, soluj=None, t=None):
        self.name = solv + solui + (soluj if soluj else "")
        self.solv = solv
        self.solui = solui
        self.soluj = soluj
        self._tem = t

        self.ij_flag = False
        self.ji_flag = False

        self.eji_str = None
        self.sji_str = None
        self.eij_str = None
        self.sij_str = None

        self.str_t = None
        self.rank_firstorder = None

        self.str_ln_yi0 = (None, None)
        self.str_yi0 = (None, None)

        self._eji = float('nan')
        self._eij = float('nan')
        self._ln_yi0 = float('nan')
        self._yi0 = float('nan')
        self._sji = float('nan')
        self._sij = float('nan')
        self._rji = float('nan')
        self._pji = float('nan')

        self.ref = ""

        # Load data from database
        self._load_data_from_db()
        self._process_loaded_data()

    def _load_data_from_db(self):
        """从数据库加载数据。"""
        row_fo, flag = query_first_order_wagner_intp_db(self.solv, self.solui, self.soluj)
        if row_fo:
            if flag: # ji_flag
                self.ji_flag = True
                self.eji_str, self.rank_firstorder, self.sji_str, self.str_t, self.ref = row_fo
                if not self.eji_str: self.eji_str = None
                else: self.sji_str = None
            else: # ij_flag
                self.ij_flag = True
                self.eij_str, self.rank_firstorder, self.sij_str, self.str_t, self.ref = row_fo
                if not self.eij_str: self.eij_str = None
                else: self.sij_str = None

        row_ln_yi0 = query_ln_yi0_db(self.solv, self.solui)
        if row_ln_yi0:
            ln_yi0, yi0, t_str = row_ln_yi0
            if t_str == "T" or (self.str_t and t_str == self.str_t):
                self.str_ln_yi0 = (ln_yi0 if ln_yi0 else "", t_str)
                self.str_yi0 = (yi0 if yi0 else "", t_str)

    def _process_loaded_data(self):
        """处理加载的数据。"""
        from .element import Element # Local import to avoid circular dependency

        if self.ij_flag:
            if self.eij_str:
                self._eij = self._process_temp_data((self.eij_str, self.str_t), self._tem)
                self._sij = self._first_order_w2m(self._eij, Element(self.solui), Element(self.solv))
                self._sji = self._sij
                self._eji = self._first_order_m_to_w(self._sji, Element(self.soluj), Element(self.solv))
            elif self.sij_str:
                self._sij = self._process_temp_data((self.sij_str, self.str_t), self._tem)
                self._eij = self._first_order_m_to_w(self._sij, Element(self.solui), Element(self.solv))
                self._sji = self._sij
                self._eji = self._first_order_m_to_w(self._sji, Element(self.soluj), Element(self.solv))
        elif self.ji_flag:
            if self.eji_str:
                self._eji = self._process_temp_data((self.eji_str, self.str_t), self._tem)
                self._sji = self._first_order_w2m(self._eji, Element(self.soluj), Element(self.solv))
                self._sij = self._sji
                self._eij = self._first_order_m_to_w(self._sij, Element(self.solui), Element(self.solv))
            elif self.sji_str:
                self._sji = self._process_temp_data((self.sji_str, self.str_t), self._tem)
                self._eji = self._first_order_m_to_w(self._sji, Element(self.soluj), Element(self.solv))
                self._sij = self._sji
                self._eij = self._first_order_m_to_w(self._sij, Element(self.solui), Element(self.solv))

        self._yi0 = self._process_temp_data(self.str_yi0, self._tem)
        self._ln_yi0 = self._process_temp_data(self.str_ln_yi0, self._tem)


    def _process_temp_data(self, text_info, t):
        """处理含温度依赖性的数据。"""
        if not t or not text_info or not text_info[0]:
            return float('nan')

        data_str, t_str = text_info

        if t_str == "T":
            pattern = r"^([-]?\d*\.?\d*)([\/])([T])(([\+]|[\-]?)\d*\.?\d*)"
            match = re.match(data_str, pattern)
            if match:
                groups = match.groups()
                a = float(groups[0])
                b = float(groups[3])
                return a / t + b
            else: # Handle simpler forms if needed, e.g., just a number
                try:
                    return float(data_str)
                except ValueError:
                    return float('nan')
        elif t_str and float(t_str) == t:
            try:
                return float(data_str)
            except ValueError:
                return float('nan')

        return float('nan')

    def _ln(self, x):
        """计算自然对数，处理特殊情况。"""
        if x > 0:
            return math.log(x)
        elif x == 0.0:
            return float('-inf')
        else:
            return float('nan')

    def _first_order_m_to_w(self, sji, element_j, matrix):
        """摩尔分数一阶相互作用系数转为质量百分比。"""
        if math.isnan(sji) or not element_j.m or not matrix.m:
            return float('nan')
        return (sji - 1 + element_j.m / matrix.m) * matrix.m / (230 * element_j.m)

    def _first_order_w2m(self, eji, element_j, matrix):
        """质量百分比一阶相互作用系数转为摩尔分数。"""
        if math.isnan(eji) or not element_j.m or not matrix.m:
            return float('nan')
        sij = 230 * eji * element_j.m / matrix.m + (1 - element_j.m / matrix.m)
        return round(sij, 2)

    @property
    def based(self): return self.solv
    @property
    def eji(self): return self._eji
    @property
    def eij(self): return self._eij
    @property
    def sji(self): return self._sji
    @property
    def sij(self): return self._sij
    @property
    def yi0(self): return self._yi0
    @property
    def ln_yi(self):
        return self._ln(self.yi0) if not math.isnan(self.yi0) else self._ln_yi0