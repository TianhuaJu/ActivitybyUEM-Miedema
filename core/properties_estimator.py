import numpy as np
from scipy.optimize import brentq
from core.tdb_parser import get_tdb_parser


class PropertiesEstimator:
	"""
	基于 TDB 数据库自动估算纯元素的物理性质（熔点、熔化熵）。
	"""
	_instance = None
	
	def __new__ (cls):
		if cls._instance is None:
			cls._instance = super(PropertiesEstimator, cls).__new__(cls)
			cls._instance.tdb_parser = get_tdb_parser()
			cls._instance._cache = {}  # 缓存计算结果
		return cls._instance
	
	def get_element_properties (self, element: str) -> dict:
		"""
		获取元素的热力学属性。优先查缓存，没有则计算。
		返回: {'Tm': float, 'Sf': float}
		"""
		if element in self._cache:
			return self._cache[element]
		
		props = self._calculate_properties(element)
		self._cache[element] = props
		return props
	
	def _calculate_properties (self, element: str) -> dict:
		"""
		核心计算逻辑：通过数值方法寻找固液平衡温度。
		"""
		# 1. 确定参考固相 (在低温下稳定的固相)
		# 我们取 298.15 K 下的稳定相，排除 LIQUID 和 GAS
		stable_phase = self.tdb_parser.get_stable_phase(element, 298.15)
		
		# 如果低温下就是液体（如Hg）或找不到稳定固相
		if not stable_phase or stable_phase == 'LIQUID':
			# 尝试常见的固相名称作为兜底
			for p in ['BCC_A2', 'FCC_A1', 'HCP_A3', 'GRAPHITE', 'DIAMOND_A4']:
				if p in self.tdb_parser.get_element_phases(element):
					stable_phase = p
					break
		
		# 如果还是找不到固相，返回默认值
		if not stable_phase or stable_phase == 'LIQUID':
			return {'Tm': 2000.0, 'Sf': 10.0}
		
		# 2. 定义目标函数：Delta G(T) = G_liq(T) - G_solid(T)
		def delta_gibbs (T):
			g_liq = self.tdb_parser.get_gibbs_energy(element, 'LIQUID', T)
			g_sol = self.tdb_parser.get_gibbs_energy(element, stable_phase, T)
			
			# 如果超出TDB定义范围（返回None），用大数值强行引导
			if g_liq is None or g_sol is None:
				return -1000.0 if T > 3000 else 1000.0
			
			return g_sol - g_liq  # 当 sol - liq = 0 时即为熔点
		
		# 3. 寻找根 (熔点)
		# 搜索范围 200K 到 6000K
		Tm = 2000.0
		try:
			# 检查两端符号是否相反（存在根）
			f_low = delta_gibbs(300.0)
			f_high = delta_gibbs(6000.0)
			
			if f_low * f_high < 0:
				Tm = brentq(delta_gibbs, 300.0, 6000.0)
			else:
				# 可能是升华（如C）或一直固态/液态，取个合理的默认值或最高值
				Tm = 4000.0 if f_low > 0 else 300.0
		except:
			Tm = 2000.0  # 计算失败兜底
		
		# 4. 计算熔化熵 Sf = (H_liq - H_sol) / Tm
		# 注意：tdb_parser 需要有 get_enthalpy 方法。
		# 如果没有，可以用 (G + TS)/T 计算 H，或者利用 G_liq=G_sol 时 S = (H_liq - H_sol)/Tm 的关系
		# 我们用数值微分计算 S = -dG/dT
		
		dt = 1e-4
		g_liq_m = self.tdb_parser.get_gibbs_energy(element, 'LIQUID', Tm - dt)
		g_liq_p = self.tdb_parser.get_gibbs_energy(element, 'LIQUID', Tm + dt)
		S_liq = -(g_liq_p - g_liq_m) / (2 * dt)
		
		g_sol_m = self.tdb_parser.get_gibbs_energy(element, stable_phase, Tm - dt)
		g_sol_p = self.tdb_parser.get_gibbs_energy(element, stable_phase, Tm + dt)
		S_sol = -(g_sol_p - g_sol_m) / (2 * dt)
		
		Sf = S_liq - S_sol
		
		# 保护：防止计算出负熵或极小值
		if Sf < 3.0: Sf = 10.0
		
		return {'Tm': Tm, 'Sf': Sf}


# 导出单例获取函数
def get_properties_estimator ():
	return PropertiesEstimator()