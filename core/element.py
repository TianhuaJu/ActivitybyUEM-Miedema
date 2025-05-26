# element.py

from core.constants import Constants
from .database_handler import get_miedema_data

class Element:
    """定义 Element 类，负责加载和管理单个元素的属性。"""
    def __init__(self, name):
        self.name = name
        self.phi = 0.0
        self.n_ws = 0.0
        self.v = 0.0
        self.u = 0.0
        self.hybrid_factor = ""
        self.hybrid_value = 0.0
        self.is_trans_group = False
        self.dh_trans = 0.0
        self.m = 0.0
        self.tm = 0.0
        self.tb = 0.0
        self.bkm = 0.0  # Bulk modulus (需要从数据库或常量添加)
        self.shm = 0.0  # Shear modulus (需要从数据库或常量添加)
        self.is_exist = False

        if name in Constants.periodic_table:
            self.is_exist = True
            self._load_miedema_data()

    def _load_miedema_data(self):
        """从数据库加载元素数据。"""
        row = get_miedema_data(self.name)
        if row:
            self.phi, self.n_ws, self.v, self.u, self.hybrid_factor, \
            self.hybrid_value, self.is_trans_group, self.dh_trans, \
            self.m, self.tm, self.tb = row
            self.is_trans_group = bool(self.is_trans_group)
            # 注意: bkm 和 shm 没有在原始代码的数据库查询中，需要确认来源
        else:
            self.is_exist = False