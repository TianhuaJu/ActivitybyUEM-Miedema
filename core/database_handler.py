# database_handler.py
import os
import sys
import sqlite3
import math
import re


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


# 修正：移除模块级别的DB_PATH，改为每次动态获取
# DB_PATH = get_database_path()  # ❌ 错误：模块加载时执行可能导致路径问题


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
			
			conn.close()
			return row1, True  # ji_flag = True
		else:
			print("查询1无结果")
		
		# 第二次查询 - 交换solui和soluj查找
		query2 = "SELECT eji, Rank, sji, T, reference FROM first_order WHERE solv = ? AND solui = ? AND soluj = ?"
		cursor.execute(query2, (solv, soluj, solui))  # 交换solui和soluj
		row2 = cursor.fetchone()
		
		
		if row2:
			
			conn.close()
			return row2, False  # ij_flag = True
		else:
			print("查询2无结果")
		
		
		conn.close()
		return None, None
	
	except Exception as e:
		print(f"查询一阶瓦格纳相互作用参数时出错: {e}")
		print(f"查询参数: solv={solv}, solui={solui}, soluj={soluj}")
		return None, None


def query_ln_yi0_db (solv, solui):
	"""从数据库查询无限稀释活度系数。"""
	try:
		# 使用新的连接方式
		conn = get_database_connection()
		if conn is None:
			return None
		
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
	
	def __init__ (self, solv, solui, soluj=None, t=None):
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
	
	def _load_data_from_db (self):
		"""从数据库加载数据。"""
		
		
		row_fo, flag = query_first_order_wagner_intp_db(self.solv, self.solui, self.soluj)
		if row_fo:
			eji_val, rank_val, sji_val, t_val, ref_val = row_fo
			
			# 处理NULL值和空字符串（在SQLite中NULL会被返回为None，空字符串返回为''）
			self.eji_str = eji_val if eji_val is not None and eji_val.strip() != '' else None
			self.sji_str = sji_val if sji_val is not None and sji_val.strip() != '' else None
			self.str_t = t_val if t_val is not None and str(t_val).strip() != '' else None
			self.ref = ref_val if ref_val is not None else ""
			self.rank_firstorder = rank_val
			
			
			if flag:  # ji_flag - 查询顺序是 solv-solui-soluj
				self.ji_flag = True
				
			else:  # ij_flag - 查询顺序是 solv-soluj-solui (交换了溶质顺序)
				self.ij_flag = True
				# 由于查询时交换了solui和soluj，需要调整字段的含义
				# 原来的eji实际上是eij，原来的sji实际上是sij
				self.eij_str = self.eji_str  # 保存原始的eji作为eij
				self.sij_str = self.sji_str  # 保存原始的sji作为sij
				# 清空ji字段，因为我们没有直接的ji数据
				self.eji_str = None
				self.sji_str = None
				
		else:
			print("未找到相互作用参数数据")
		
		row_ln_yi0 = query_ln_yi0_db(self.solv, self.solui)
		if row_ln_yi0:
			
			ln_yi0, yi0, t_str = row_ln_yi0
			if t_str == "T" or (self.str_t and t_str == self.str_t):
				self.str_ln_yi0 = (ln_yi0 if ln_yi0 else "", t_str)
				self.str_yi0 = (yi0 if yi0 else "", t_str)
		else:
			print("未找到Yi0数据")
	
	def _process_loaded_data (self):
		"""处理加载的数据。"""
		# 修正导入问题 - 支持直接运行和模块导入两种方式
		try:
			from .element import Element  # 相对导入（模块内使用）
		except ImportError:
			# 如果相对导入失败，尝试绝对导入或跳过Element相关计算
			try:
				from core.element import Element  # 绝对导入
			except ImportError:
				print("警告: 无法导入Element类，将跳过转换计算")
				Element = None
		
		if Element is None:
			
			# 直接使用原始值，不进行转换
			if self.ij_flag:
				if self.sij_str is not None:
					self._sij = self._process_temp_data((self.sij_str, self.str_t), self._tem)
					print(f"  直接使用sij值: {self._sij}")
				elif self.eij_str is not None:
					self._eij = self._process_temp_data((self.eij_str, self.str_t), self._tem)
					print(f"  直接使用eij值: {self._eij}")
			elif self.ji_flag:
				if self.sji_str is not None:
					self._sji = self._process_temp_data((self.sji_str, self.str_t), self._tem)
					print(f"  直接使用sji值: {self._sji}")
				elif self.eji_str is not None:
					self._eji = self._process_temp_data((self.eji_str, self.str_t), self._tem)
					print(f"  直接使用eji值: {self._eji}")
			return
		
		if self.ij_flag:
			# ij_flag表示查询结果是 solv-soluj-solui 的顺序（交换了溶质）
			
			# 优先使用sij（摩尔分数系数）
			if self.sij_str is not None:
				print(f"  使用sij数据进行计算")
				self._sij = self._process_temp_data((self.sij_str, self.str_t), self._tem)
				if not math.isnan(self._sij):
					# 从sij计算eij
					self._eij = self._first_order_m_to_w(self._sij, Element(self.solui), Element(self.solv))
					# 根据Wagner formalism，在稀溶液中 εᵢⱼ ≈ εⱼᵢ
					self._sji = self._sij
					self._eji = self._first_order_m_to_w(self._sji, Element(self.soluj), Element(self.solv))
					
			# 如果没有sij数据，使用eij数据
			elif self.eij_str is not None:
				
				self._eij = self._process_temp_data((self.eij_str, self.str_t), self._tem)
				if not math.isnan(self._eij):
					# 从eij计算sij
					self._sij = self._first_order_w2m(self._eij, Element(self.solui), Element(self.solv))
					# 根据Wagner formalism，在稀溶液中 εᵢⱼ ≈ εⱼᵢ
					self._sji = self._sij
					self._eji = self._first_order_m_to_w(self._sji, Element(self.soluj), Element(self.solv))
					
		if self.ji_flag:
			# ji_flag表示查询结果是 solv-solui-soluj 的原始顺序
			
			# 优先使用sji（摩尔分数系数）
			if self.sji_str is not None:
				
				self._sji = self._process_temp_data((self.sji_str, self.str_t), self._tem)
				if not math.isnan(self._sji):
					# 从sji计算eji
					self._eji = self._first_order_m_to_w(self._sji, Element(self.soluj), Element(self.solv))
					# 根据Wagner formalism，在稀溶液中 εᵢⱼ ≈ εⱼᵢ
					self._sij = self._sji
					self._eij = self._first_order_m_to_w(self._sij, Element(self.solui), Element(self.solv))
					
			# 如果没有sji数据，使用eji数据
			elif self.eji_str is not None:
				self._eji = self._process_temp_data((self.eji_str, self.str_t), self._tem)
				if not math.isnan(self._eji):
					# 从eji计算sji
					self._sji = self._first_order_w2m(self._eji, Element(self.soluj), Element(self.solv))
					# 根据Wagner formalism，在稀溶液中 εᵢⱼ ≈ εⱼᵢ
					self._sij = self._sji
					self._eij = self._first_order_m_to_w(self._sij, Element(self.solui), Element(self.solv))
					
			else:
				print(f"  警告：既没有sji数据也没有eji数据")
		else:
			print(f"  警告：没有找到任何相互作用参数数据")
		
		# 处理无限稀释活度系数
		self._yi0 = self._process_temp_data(self.str_yi0, self._tem)
		self._ln_yi0 = self._process_temp_data(self.str_ln_yi0, self._tem)
		
	
	def _process_temp_data (self, text_info, t):
		"""处理含温度依赖性的数据。"""
		if not t or not text_info or not text_info[0]:
			return float('nan')
		
		data_str, t_str = text_info
		
		
		if t_str == "T":
			# 处理温度相关公式，如 "-126300/T+39.0" 或 "744.06/T-0.33"
			try:
				# 匹配形如 "a/T+b" 或 "a/T-b" 的模式
				pattern1 = r"^([-]?\d*\.?\d*)/T([\+\-]\d*\.?\d*)$"
				match1 = re.match(pattern1, data_str)
				if match1:
					a = float(match1.group(1))
					b = float(match1.group(2))
					result = a / t + b
					return result
				
				# 匹配纯数字
				try:
					result = float(data_str)
					
					return result
				except ValueError:
					
					return float('nan')
			
			except Exception as e:
				
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
	
	def _ln (self, x):
		"""计算自然对数，处理特殊情况。"""
		if x > 0:
			return math.log(x)
		elif x == 0.0:
			return float('-inf')
		else:
			return float('nan')
	
	def _first_order_m_to_w (self, sji, element_j, matrix):
		"""摩尔分数一阶相互作用系数转为质量百分比。"""
		if math.isnan(sji) or not element_j.m or not matrix.m:
			return float('nan')
		return (sji - 1 + element_j.m / matrix.m) * matrix.m / (230 * element_j.m)
	
	def _first_order_w2m (self, eji, element_j, matrix):
		"""质量百分比一阶相互作用系数转为摩尔分数。"""
		if math.isnan(eji) or not element_j.m or not matrix.m:
			return float('nan')
		sij = 230 * eji * element_j.m / matrix.m + (1 - element_j.m / matrix.m)
		return round(sij, 2)
	
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
		return self._ln(self.yi0) if not math.isnan(self.yi0) else self._ln_yi0


