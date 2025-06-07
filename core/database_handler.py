# database_handler.py
import os
import sys
import sqlite3
import math
import re

import models.extrapolation_models


def get_database_path ():
	"""获取数据库路径，适配开发环境和PyInstaller打包环境"""
	try:
		# PyInstaller创建的临时文件夹路径
		base_path = sys._MEIPASS
	except AttributeError:
		# 开发环境中的路径
		# 从当前文件位置向上找到项目根目录
		current_file = os.path.abspath(__file__)
		
		# 如果当前文件在core目录下，需要向上两级到项目根目录
		if 'core' in current_file:
			# 当前路径类似: .../项目根目录/core/database_handler.py
			project_root = os.path.dirname(os.path.dirname(current_file))
		else:
			# 直接在项目根目录
			project_root = os.path.dirname(current_file)
		
		base_path = project_root
	
	db_path = os.path.join(base_path, 'database', 'data', 'DataBase.db')
	return db_path


def get_database_connection ():
	"""获取数据库连接"""
	try:
		db_path = get_database_path()
		# 以只读模式连接数据库（推荐用于只读数据库）
		conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
		return conn
	except Exception as e:
		print(f"数据库连接失败: {e}")
		print(f"尝试连接的数据库路径: {get_database_path()}")
		# 如果只读模式失败，尝试普通模式
		try:
			db_path = get_database_path()
			conn = sqlite3.connect(db_path)
			return conn
		except Exception as e2:
			print(f"普通模式连接也失败: {e2}")
			return None


def get_miedema_data (element_name):
	"""从数据库加载元素的 Miedema 参数。"""
	try:
		# 使用新的连接方式
		conn = get_database_connection()
		if conn is None:
			return None
		
		cursor = conn.cursor()
		query = "SELECT phi, nws, V, u, alpha_beta, hybirdvalue, isTrans, dHtrans, mass, Tm, Tb FROM MiedemaParameter WHERE Symbol = ?"
		cursor.execute(query, (element_name,))
		row = cursor.fetchone()
		conn.close()
		return row
	except Exception as e:
		print(f"加载元素数据时出错 ({element_name}): {e}")
		return None


def query_first_order_wagner_intp_db (solv, solui, soluj):
	"""从数据库查询一阶瓦格纳相互作用参数。"""
	conn = None  # 初始化连接变量
	try:
		# 使用新的连接方式
		conn = get_database_connection()
		if conn is None:
			return None, None
		
		cursor = conn.cursor()
		
		# 第一次查询 - 查找 solv-solui-soluj 的组合
		query1 = "SELECT eji, Rank, sji, T, reference FROM first_order WHERE solv = ? AND solui = ? AND soluj = ?"
		cursor.execute(query1, (solv, solui, soluj))
		row1 = cursor.fetchone()
		
		if row1:
			return row1, True  # ji_flag = True
		else:
			print("查询1无结果")
		
		# 第二次查询 - 交换solui和soluj查找
		query2 = "SELECT eji, Rank, sji, T, reference FROM first_order WHERE solv = ? AND solui = ? AND soluj = ?"
		cursor.execute(query2, (solv, soluj, solui))  # 交换solui和soluj
		row2 = cursor.fetchone()
		
		if row2:
			return row2, False  # ji_flag = False (交换了顺序)
		else:
			print("查询2无结果")
		
		return None, None
	
	except Exception as e:
		print(f"查询一阶瓦格纳相互作用参数时出错: {e}")
		print(f"查询参数: solv={solv}, solui={solui}, soluj={soluj}")
		return None, None
	
	finally:
		# 确保连接被关闭
		if conn:
			conn.close()


def query_ln_yi0_db (solv, solui):
	"""从数据库查询无限稀释活度系数。"""
	conn = None
	try:
		# 使用新的连接方式
		conn = get_database_connection()
		if conn is None:
			return None
		
		cursor = conn.cursor()
		query = "SELECT lnYi0, Yi0, T FROM lnY0 WHERE solv = ? AND solui = ?"
		cursor.execute(query, (solv, solui))
		row = cursor.fetchone()
		return row
	except Exception as e:
		print(f"查询无限稀释活度系数时出错: {e}")
		return None
	finally:
		if conn:
			conn.close()


# 查询二阶活度相互作用系数
def query_second_order_interaction_db (solv, solui, soluj, soluk=None):
	"""
	从数据库查询二阶活度相互作用系数

	参数:
	solv: 基体元素 (如 'Fe')
	solui: 溶质元素i (如 'C') - 被影响的元素
	soluj: 溶质元素j (如 'Co') - 影响元素1
	soluk: 溶质元素k (如 'Cr', 可选) - 影响元素2

	字段含义:
	- ri_ij: i,j对i的质量分数表示二阶活度相互作用系数
	- pi_ij: i,j对i的摩尔分数表示二阶活度相互作用系数
	- ri_jk: j,k对i的质量分数表示二阶活度相互作用系数
	- pi_jk: j,k对i的摩尔分数表示二阶活度相互作用系数

	返回:
	(row_data, interaction_type):
	- row_data: 查询结果元组 (ri_ij, pi_ij, ri_jk, pi_jk, T, Rank, reference)
	"""
	conn = None
	try:
		conn = get_database_connection()
		if conn is None:
			return None, None
		
		cursor = conn.cursor()
		
		if soluk is None:
			# 查找i,j对i的影响 (ri_ij, pi_ij)
			query = """
			SELECT ri_ij, pi_ij, ri_jk, pi_jk, T, Rank, reference
			FROM second_order
			WHERE solv = ? AND solui = ? AND soluj = ?
			"""
			cursor.execute(query, (solv, solui, soluj))  # 只传递3个参数
			row1 = cursor.fetchone()
			if row1:
				return row1, "ij"
		else:
			# 查找j,k对i的影响 (ri_jk, pi_jk)
			query1 = """
			SELECT ri_ij, pi_ij, ri_jk, pi_jk, T, Rank, reference
			FROM second_order
			WHERE solv = ? AND solui = ? AND soluj = ? AND soluk = ?
			"""
			cursor.execute(query1, (solv, solui, soluj, soluk))
			row2 = cursor.fetchone()
			
			if row2:
				return row2, "jk"
		
		return None, None
	
	except Exception as e:
		print(f"查询二阶相互作用系数时出错: {e}")
		return None, None
	
	finally:
		if conn:
			conn.close()


class Melt:
	"""Melt 类，用于存储和处理来自数据库的熔体组分间活度相互作用系数。"""
	
	def __init__ (self, solv, solui, soluj=None, soluk=None, t=None):
		self.name = solv + solui + (soluj if soluj else "")
		self.solv = solv
		self.solui = solui
		self.soluj = soluj
		self.soluk = soluk
		self._tem = t
		
		self.ij_flag = False
		self.ji_flag = False
		
		self.eji_str = None
		self.sji_str = None
		self.eij_str = None
		self.sij_str = None
		self.ejk_str = None
		self.sjk_str = None
		self.ekj_str = None
		self.skj_str = None
		
		self.ri_ij_str = None
		self.ri_jk_str = None
		self.pi_ij_str = None
		self.pi_jk_str = None
		
		self.first_order_str_t = None
		self.second_order_str_t = None
		self.lny0_str_t = None
		self.rank_firstorder = None
		
		self.str_ln_yi0 = (None, None)
		self.str_yi0 = (None, None)
		
		self._eji = float('nan')
		self._eij = float('nan')
		self._ln_yi0 = float('nan')
		self._yi0 = float('nan')
		self._sji = float('nan')
		self._sij = float('nan')
		self._ejk = float('nan')
		self._sjk = float('nan')
		self._ekj = float('nan')
		self._skj = float('nan')
		self._ri_ij = float('nan')
		self._ri_jk = float('nan')
		self._pi_ij = float('nan')
		self._pi_jk = float('nan')
		
		self.ref = ""
		
		# Load data from database
		self._load_data_from_db()
		self._process_loaded_data()
	
	def _load_data_from_db (self):
		"""从数据库加载数据。"""
		
		# 处理二阶活度相互作用系数
		row_second_order, query_type = query_second_order_interaction_db(self.solv, self.solui, self.soluj, self.soluk)
		if row_second_order:
			ri_ij_val, pi_ij_val, ri_jk_val, pi_jk_val, T_val, Rank_val, ref_val = row_second_order
			
			# 将获取的数据赋值给实例变量
			self.ri_ij_str = ri_ij_val if ri_ij_val is not None and str(ri_ij_val).strip() != '' else None
			self.pi_ij_str = pi_ij_val if pi_ij_val is not None and str(pi_ij_val).strip() != '' else None
			self.ri_jk_str = ri_jk_val if ri_jk_val is not None and str(ri_jk_val).strip() != '' else None
			self.pi_jk_str = pi_jk_val if pi_jk_val is not None and str(pi_jk_val).strip() != '' else None
			self.second_order_str_t = T_val if T_val is not None and str(T_val).strip() != '' else None
		
		# 处理无限稀活度系数
		row_ln_yi0 = query_ln_yi0_db(self.solv, self.solui)
		if row_ln_yi0:
			ln_yi0, yi0, t_str = row_ln_yi0
			self.str_ln_yi0 = ln_yi0 if ln_yi0 is not None and str(ln_yi0).strip() != '' else None
			self.str_yi0 = yi0 if yi0 is not None and str(yi0).strip() != '' else None
			self.lny0_str_t = t_str if t_str is not None and str(t_str).strip() != '' else None
		else:
			print("未找到Yi0相关数据")
	
	def _process_loaded_data (self):
		"""处理加载的数据。"""
		self._eji, self._sji, self._eij, self._sij = self._get_first_order_activity_interaction_coefficient(self.solui,
		                                                                                                    self.soluj,
		                                                                                                    self.solv)
		
		# 处理二阶系数
		if self.ri_ij_str is not None:
			self._ri_ij = self._process_temp_data((self.ri_ij_str, self.second_order_str_t), self._tem)
			self._pi_ij = self._second_order_w2m(self._ri_ij,self.solui,self.soluj,self.solui,self.solv)
		if self.pi_ij_str is not None:
			self._pi_ij = self._process_temp_data((self.pi_ij_str, self.second_order_str_t), self._tem)
			
		if self.ri_jk_str is not None:
			self._ri_jk = self._process_temp_data((self.ri_jk_str, self.second_order_str_t), self._tem)
			self._pi_jk = self._second_order_w2m(self._ri_jk,self.solui,self.soluj,self.soluk,self.solv)
		if self.pi_jk_str is not None:
			self._pi_jk = self._process_temp_data((self.pi_jk_str, self.second_order_str_t), self._tem)
		
		print(self._pi_ij)
		# 处理无限稀释活度系数
		self._yi0 = self._process_temp_data((self.str_yi0, self.lny0_str_t), self._tem)
		self._ln_yi0 = self._process_temp_data((self.str_ln_yi0, self.lny0_str_t), self._tem)
	
	def _get_first_order_activity_interaction_coefficient (self, element_i, element_j, solvent):
		'''get the first order activity interaction coefficient j to i in solvent,including eji、eij、sji、sij
		return:
		-results: eji、sji、eij、sij
		'''
		from .element import Element  # 延迟导入避免循环依赖
		
		row_fo, flag = query_first_order_wagner_intp_db(solvent, element_i, element_j)
		if row_fo:
			eji_val, rank_val, sji_val, t_val, ref_val = row_fo
			
			# 处理NULL值和空字符串（在SQLite中NULL会被返回为None，空字符串返回为''）
			eji_str = eji_val if eji_val is not None and str(eji_val).strip() != '' else None
			sji_str = sji_val if sji_val is not None and str(sji_val).strip() != '' else None
			first_order_str_t = t_val if t_val is not None and str(t_val).strip() != '' else None
			ref = ref_val if ref_val is not None else ""
			rank_firstorder = rank_val
			_eji, _sji, _eij, _sij = float('nan'), float('nan'), float('nan'), float('nan')
			
			if flag:  # ji_flag - 查询顺序是 solv-solui-soluj
				if sji_str is not None:
					_sji = self._process_temp_data((sji_str, first_order_str_t), self._tem)
					if not self._safe_isnan(_sji):
						# 从sji计算eji
						_eji = self._first_order_m_to_w(_sji, Element(element_j), Element(solvent))
						# 根据Wagner formalism，在稀溶液中 εᵢⱼ ≈ εⱼᵢ
						_sij = _sji
						_eij = self._first_order_m_to_w(_sij, Element(element_i), Element(solvent))
				elif eji_str is not None:
					_eji = self._process_temp_data((eji_str, first_order_str_t), self._tem)
					if not self._safe_isnan(_eji):
						# 从eji计算sji
						_sji = self._first_order_w2m(_eji, Element(element_j), Element(solvent))
						# 根据Wagner formalism，在稀溶液中 εᵢⱼ ≈ εⱼᵢ
						_sij = _sji
						_eij = self._first_order_m_to_w(_sij, Element(element_i), Element(solvent))
				else:
					print(f"  警告：既没有sji数据也没有eji数据")
			else:  # ij_flag - 查询顺序是 solv-soluj-solui (交换了溶质顺序)
				sij_str = sji_str
				eij_str = eji_str
				if sij_str is not None:
					_sij = self._process_temp_data((sij_str, first_order_str_t), self._tem)
					if not self._safe_isnan(_sij):
						# 从sij计算eij
						_eij = self._first_order_m_to_w(_sij, Element(element_i), Element(solvent))
						# 根据Wagner formalism，在稀溶液中 εᵢⱼ ≈ εⱼᵢ
						_sji = _sij
						_eji = self._first_order_m_to_w(_sji, Element(element_j), Element(solvent))
				elif eij_str is not None:
					_eij = self._process_temp_data((eij_str, first_order_str_t), self._tem)
					if not self._safe_isnan(_eij):
						# 从eij计算sij
						_sij = self._first_order_w2m(_eij, Element(element_i), Element(solvent))
						# 根据Wagner formalism，在稀溶液中 εᵢⱼ ≈ εⱼᵢ
						_sji = _sij
						_eji = self._first_order_m_to_w(_sji, Element(element_j), Element(solvent))
			return _eji, _sji, _eij, _sij
		else:
			print("未找到相互作用参数数据")
			# 修复：返回 float('nan') 而不是 None，避免后续处理错误
			return float('nan'), float('nan'), float('nan'), float('nan')
	
	def _process_temp_data (self, text_info, t):
		"""处理含温度依赖性的数据。"""
		if not t or not text_info or not text_info[0]:
			return float('nan')
		
		data_str, t_str = text_info
		
		# 确保 data_str 不是 None 或空值
		if data_str is None or str(data_str).strip() == '':
			return float('nan')
		
		if t_str == "T":
			# 处理温度相关公式，如 "-126300/T+39.0" 或 "744.06/T-0.33"
			try:
				# 修复：使用更严格的正则表达式模式，确保至少匹配一个数字
				pattern1 = r"^([-]?\d+\.?\d*)/T([\+\-]\d+\.?\d*)$"
				match1 = re.match(pattern1, str(data_str))
				if match1:
					a = float(match1.group(1))
					b = float(match1.group(2))
					result = a / t + b
					return result
				
				# 匹配纯数字
				try:
					result = float(data_str)
					return result
				except (ValueError, TypeError):
					return float('nan')
			
			except Exception as e:
				print(f"处理温度相关数据时出错: {e}, data_str: {data_str}")
				return float('nan')
		
		elif t_str and str(t_str).strip():
			# 固定温度的数据
			try:
				if float(t_str) == t:
					result = float(data_str)
					return result
				else:
					return float('nan')
			except (ValueError, TypeError):
				return float('nan')
		
		return float('nan')
	
	def _safe_isnan (self, value):
		"""安全地检查是否为 NaN，避免类型错误"""
		try:
			if value is None:
				return True
			if isinstance(value, str):
				if value.strip() == '' or value.lower() in ['nan', 'none', 'null']:
					return True
				try:
					float_val = float(value)
					return math.isnan(float_val)
				except (ValueError, TypeError):
					return True
			if isinstance(value, (int, float)):
				return math.isnan(float(value))
			return True  # 其他类型视为无效值
		except:
			return True
	
	def _ln (self, x):
		"""计算自然对数，处理特殊情况。"""
		try:
			if self._safe_isnan(x):
				return float('nan')
			x_float = float(x)
			if x_float > 0:
				return math.log(x_float)
			elif x_float == 0.0:
				return float('-inf')
			else:
				return float('nan')
		except (ValueError, TypeError):
			return float('nan')
	
	def _first_order_m_to_w (self, sji, element_j, matrix):
		"""摩尔分数一阶相互作用系数转为质量百分比。"""
		try:
			if self._safe_isnan(sji) or not element_j.m or not matrix.m:
				return float('nan')
			return (float(sji) - 1 + element_j.m / matrix.m) * matrix.m / (230 * element_j.m)
		except (ValueError, TypeError, AttributeError, ZeroDivisionError):
			return float('nan')
	
	def _first_order_w2m (self, eji, element_j, matrix):
		"""质量百分比一阶相互作用系数转为摩尔分数。"""
		try:
			if self._safe_isnan(eji) or not element_j.m or not matrix.m:
				return float('nan')
			sij = 230 * float(eji) * element_j.m / matrix.m + (1 - element_j.m / matrix.m)
			return round(sij, 2)
		except (ValueError, TypeError, AttributeError, ZeroDivisionError):
			return float('nan')
	
	# 二阶活度相互作用系数转换
	def _second_order_w2m (self, ri_jk, element_i, element_j, element_k, matrix):
		'''质量分数表示的转换成摩尔分数表示的,
		to(ri_jk) - pi_jk
		'''
		from .element import Element  # 延迟导入避免循环依赖
		
		eji = self.get_or_calculate_eki(matrix, element_i, element_j, self._tem)
		eki = self.get_or_calculate_eki(matrix, element_i, element_k, self._tem)
		
		M1 = Element(matrix).m
		Mj = Element(element_j).m
		Mk = Element(element_k).m
		roui_jk = 230 / (M1 * M1) * (100 * Mj * Mk * ri_jk + Mj * (M1 - Mk) * eji + Mk * (M1 - Mj) * eki) + (
					M1 - Mk) * (M1 - Mj) / (M1 * M1)
		return round(roui_jk, 3)
	
	def get_or_calculate_eki (self, solv, element_i, element_k, tem):
		"获取在基体1中组分k对组分j的以质量分数表示的一阶活度相互作用系数，有实验值采用实验值，无实验值采用计算值，默认采用UEM1计算值"
		from .element import Element  # 延迟导入避免循环依赖
		from models.activity_interaction_parameters import TernaryMelts  # 延迟导入
		
		eki, _, eik, _ = self._get_first_order_activity_interaction_coefficient(element_i, element_k, solv)
		
		# 修复：检查 eki 是否为有效数值，而不是检查是否为 None
		if eki is not None and not self._safe_isnan(eki):
			return eki
		else:
			'''calculate eki by UEM1'''
			try:
				ski = TernaryMelts().activity_interact_coefficient_1st(solv, element_i, element_k, tem, "Liquid",
				                                                       models.extrapolation_models.BinaryModel.UEM1)
				eki = self._first_order_m_to_w(ski, Element(element_k), Element(solv))
				return eki
			except Exception as e:
				print(f"计算UEM1一阶相互作用系数时出错: {e}")
				return float('nan')
	
	@property
	def based (self):
		return self.solv
	
	@property
	def eji (self):
		return self._eji
	
	@property
	def eij (self):
		return self._eij
	
	@property
	def sji (self):
		return self._sji
	
	@property
	def sij (self):
		return self._sij
	
	@property
	def yi0 (self):
		return self._yi0
	
	@property
	def ln_yi (self):
		return self._ln(self.yi0) if not self._safe_isnan(self.yi0) else self._ln_yi0
	
	# 新增：二阶系数的属性
	@property
	def ri_ij (self):
		return self._ri_ij
	
	@property
	def ri_jk (self):
		return self._ri_jk
	
	@property
	def pi_ij (self):
		return self._pi_ij
	
	@property
	def pi_jk (self):
		return self._pi_jk