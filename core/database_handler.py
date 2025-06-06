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
			# 第二次查询 - 交换solui和soluj查找
			query2 = "SELECT eji, Rank, sji, T, reference FROM first_order WHERE solv = ? AND solui = ? AND soluj = ?"
			cursor.execute(query2, (solv, soluj, solui))  # 交换solui和soluj
			row2 = cursor.fetchone()
			
			conn.close()
			return row2, False  # ij_flag = True
	
	
	except Exception as e:
		print(f"查询一阶瓦格纳相互作用参数时出错: {e}")
		print(f"查询参数: solv={solv}, solui={solui}, soluj={soluj}")
		return None, None


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
	try:
		conn = get_database_connection()
		if conn is None:
			return None, None
		
		cursor = conn.cursor()
		
		
		# 策略1: 精确匹配 - 查找i,j对i的影响 (ri_ij, pi_ij)
		query1 = """
        SELECT ri_ij, pi_ij, ri_jk, pi_jk, T, Rank, reference
        FROM second_order
        WHERE solv = ? AND solui = ? AND soluj = ?
        """
		cursor.execute(query1, (solv, solui, soluj))
		row1 = cursor.fetchone()
		
		if row1:
			conn.close()
			return row1
	
	except Exception as e:
		print(f"查询二阶相互作用系数时出错: {e}")
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
	
	def __init__ (self, solv, solui, soluj=None, soluk = None, t=None):
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
		self.ri_ij_str = None
		self.ri_jk_str = None
		self.pi_ij_str = None
		self.pi_jk_str = None
		self.first_order_t_str = None
		self.second_order_t_str = None
		self.ln_yi_t_str = None
		self.rank_firstorder = None
		
		self.str_ln_yi0 = (None, None)
		self.str_yi0 = (None, None)
		
		self._eji = float('nan')
		self._eij = float('nan')
		self._ln_yi0 = float('nan')
		self._yi0 = float('nan')
		self._sji = float('nan')
		self._sij = float('nan')
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
		
		row_fo, flag = query_first_order_wagner_intp_db(self.solv, self.solui, self.soluj)
		if row_fo:
			eji_val, rank_val, sji_val, t_val, ref_val = row_fo
			
			# 处理NULL值和空字符串（在SQLite中NULL会被返回为None，空字符串返回为''）
			self.eji_str = eji_val if eji_val is not None and eji_val.strip() != '' else None
			self.sji_str = sji_val if sji_val is not None and sji_val.strip() != '' else None
			self.first_order_t_str = t_val if t_val is not None and str(t_val).strip() != '' else None
			self.ref = ref_val if ref_val is not None else ""
			self.rank_firstorder = rank_val
			
			
			if flag:  # ji_flag - 查询顺序是 solv-solui-soluj
				self.ji_flag = True
				
			else:  # ij_flag - 查询顺序是 solv-soluj-solui (交换了溶质顺序)
				self.ij_flag = True
				
				self.eij_str = self.eji_str
				self.sij_str = self.sji_str
				
				self.eji_str = None
				self.sji_str = None
				
		
		row_ri_ij = query_second_order_interaction_db(self.solv, self.solui, self.soluj,self.soluk)
		if row_ri_ij:
			ri_ij, pi_ij, ri_jk, pi_jk, T, Rank, reference = row_ri_ij
			self.ri_ij_str = ri_ij if ri_ij is not None and ri_ij.strip() !='' else None
			self.pi_ij_str = pi_ij if pi_ij is not None and pi_ij.strip() !='' else None
			self.ri_jk_str = ri_jk if ri_jk is not None and ri_jk.strip() != '' else None
			self.pi_jk_str = pi_jk if pi_jk is not None and pi_jk.strip() != '' else None
			
			self.ri_jk_str = ri_jk if ri_jk is not None and ri_jk.strip() != '' else None
			
			self.second_order_t_str = T if T is not None and str(T).strip() != '' else None
			
				
		row_ln_yi0 = query_ln_yi0_db(self.solv, self.solui)
		if row_ln_yi0:
			ln_yi0, yi0, t_str = row_ln_yi0
			if t_str == "T" or (self.first_order_t_str and t_str == self.first_order_t_str):
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
					self._sij = self._process_temp_data((self.sij_str, self.first_order_t_str), self._tem)
					
				elif self.eij_str is not None:
					self._eij = self._process_temp_data((self.eij_str, self.first_order_t_str), self._tem)
					
			elif self.ji_flag:
				if self.sji_str is not None:
					self._sji = self._process_temp_data((self.sji_str, self.first_order_t_str), self._tem)
					
				elif self.eji_str is not None:
					self._eji = self._process_temp_data((self.eji_str, self.first_order_t_str), self._tem)
					
			return
		
		if self.ij_flag:
			# ij_flag表示查询结果是 solv-soluj-solui 的顺序（交换了溶质）
			
			
			# 优先使用sij（摩尔分数系数）
			if self.sij_str is not None:
				self._sij = self._process_temp_data((self.sij_str, self.first_order_t_str), self._tem)
				if not math.isnan(self._sij):
					# 从sij计算eij
					self._eij = self._first_order_m_to_w(self._sij, Element(self.solui), Element(self.solv))
					# 根据Wagner formalism，在稀溶液中 εᵢⱼ ≈ εⱼᵢ
					self._sji = self._sij
					self._eji = self._first_order_m_to_w(self._sji, Element(self.soluj), Element(self.solv))
					
			
			# 如果没有sij数据，使用eij数据
			elif self.eij_str is not None:
				self._eij = self._process_temp_data((self.eij_str, self.first_order_t_str), self._tem)
				if not math.isnan(self._eij):
					# 从eij计算sij
					self._sij = self._first_order_w2m(self._eij, Element(self.solui), Element(self.solv))
					# 根据Wagner formalism，在稀溶液中 εᵢⱼ ≈ εⱼᵢ
					self._sji = self._sij
					self._eji = self._first_order_m_to_w(self._sji, Element(self.soluj), Element(self.solv))
					
		
		if self.ji_flag:
			
			# 优先使用sji（摩尔分数系数）
			if self.sji_str is not None:
				self._sji = self._process_temp_data((self.sji_str, self.first_order_t_str), self._tem)
				if not math.isnan(self._sji):
					# 从sji计算eji
					self._eji = self._first_order_m_to_w(self._sji, Element(self.soluj), Element(self.solv))
					# 根据Wagner formalism，在稀溶液中 εᵢⱼ ≈ εⱼᵢ
					self._sij = self._sji
					self._eij = self._first_order_m_to_w(self._sij, Element(self.solui), Element(self.solv))
					
			
			# 如果没有sji数据，使用eji数据
			elif self.eji_str is not None:
				self._eji = self._process_temp_data((self.eji_str, self.first_order_t_str), self._tem)
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
		
		# 处理二阶活度相互作用系数
		self._ri_ij = self._process_temp_data((self.ri_ij_str,self.second_order_t_str),self._tem)
		self._ri_jk = self._process_temp_data((self.ri_jk_str,self.second_order_t_str),self._tem)
		self._pi_ij = self._second_order_w2m(self._ri_ij, Element(self.solui), Element(self.solui), Element(self.soluj),
		                                     matrix=Element(self.solv), temp=self._tem)
		
	
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
	
	def _second_order_w2m (self, r_ijk, solu_i, solu_j, solu_k, matrix, temp):
		"""
		根据公式(8)将质量分数二阶相互作用系数转换为摩尔分数

		公式: ρᵢʲ'ᵏ = (230/(M1)²) × [100M_jM_k rᵢʲ'ᵏ + Mⱼ(M₁-M_k)eᵢʲ + Mₖ(M₁-M_j)eᵢᵏ] + [(M₁-M_k)(M₁-Mⱼ)/(M1)²]

		参数:
		r_ijk: 质量分数二阶相互作用系数 rᵢʲ'ᵏ
		solu_i: 溶质元素i
		solu_j: 溶质元素j
		solu_k: 溶质元素k
		solv: 基体元素 (M₁)
		temp: 温度
		state: 状态 ('liquid' 或 'solid')
		model_func: 模型函数
		model_name: 模型名称

		返回:
		ρᵢʲ'ᵏ: 摩尔分数二阶相互作用系数
		"""
		try:
			
			# 获取原子质量
			Mi = solu_i.m  # 溶质i的原子质量
			Mj = solu_j.m  # 溶质j的原子质量
			Mk = solu_k.m  # 溶质k的原子质量
			M1 = matrix.m  # 基体元素的原子质量
			
			
			
			# 获取一阶相互作用系数 eᵢʲ 和 eᵢᵏ
			eij = self._get_or_calculate_eij(solu_i, solu_j, matrix, temp)
			eik = self._get_or_calculate_eij(solu_i, solu_k, matrix, temp)
			
			
			# 应用公式Lupis给出的公式进行转换
			# ρᵢʲ'ᵏ = (230/(M₁)²) × [100MⱼMₖrᵢʲ'ᵏ + Mⱼ(M₁-Mₖ)eᵢʲ + Mₖ(M₁-Mᵢ)eᵢᵏ] + [(M₁-Mᵢ)(M₁-Mⱼ)/(Mⱼ)²]
			
			# 计算各项
			term1_coeff = 230 / (M1 ** 2)
			term1_bracket = (100 * Mj * Mk * r_ijk +
			                 Mj * (M1 - Mk) * eij +
			                 Mk * (M1 - Mi) * eik)
			term1 = term1_coeff * term1_bracket
			
			term2 = (M1 - Mk) * (M1 - Mj) / (M1 ** 2)
			
			rho_ijk = term1 + term2
			
			
			
			return round(rho_ijk, 6)
		
		except Exception as e:
			print(f"  错误: 二阶系数转换失败: {e}")
			return float('nan')
		
	def _get_or_calculate_eij(self, solu_i, solu_j, solv, temp):
		'''获取质量分数表示的j对i的一阶活度相互作用系数
		没有实验值，则采用计算值，默认采用UEM1计算
		'''
		melts = self.__init__(solv,solu_i,solu_j,temp)
		if melts._eji:
			return melts._eji
		else:
			eji = None
			from models.activity_interaction_parameters import TernaryMelts
			from models.extrapolation_models import BinaryModel
			from core.element import Element
			sji = TernaryMelts().activity_interact_coefficient_1st(solv,solu_i,solu_j,temp,'liquid',BinaryModel.UEM1)
			eji = self._first_order_m_to_w(sji, Element(self.solv), Element(self.solv))
			return eji
		pass
	
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


# 调试函数
def test_database_query (solv="Fe", solui="O", soluj="Al", temp=1873.0):
	"""测试数据库查询功能"""
	print(f"\n=== 测试数据库查询 ===")
	print(f"查询参数: solv={solv}, solui={solui}, soluj={soluj}, temp={temp}")
	
	# 测试数据库连接
	conn = get_database_connection()
	if conn is None:
		print("❌ 数据库连接失败")
		return
	
	
	# 查看数据库表结构
	try:
		cursor = conn.cursor()
		cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
		tables = cursor.fetchall()
		print(f"数据库表: {[table[0] for table in tables]}")
		
		# 查看first_order表的结构
		cursor.execute("PRAGMA table_info(first_order);")
		columns = cursor.fetchall()
		print(f"first_order表结构: {[col[1] for col in columns]}")
		
		# 查看相关数据
		cursor.execute("SELECT solv, solui, soluj, eji, sji, T FROM first_order WHERE solv = ? LIMIT 5;", (solv,))
		samples = cursor.fetchall()
		print(f"基体为{solv}的数据样本: {samples}")
		
		conn.close()
	except Exception as e:
		print(f"查询表结构失败: {e}")
	
	# 测试Melt类
	print(f"\n=== 测试Melt类 ===")
	melt = Melt(solv, solui, soluj, temp)
	print(f"最终结果: sji={melt.sji}, eji={melt.eji}")
	print(f"标志位: ij_flag={melt.ij_flag}, ji_flag={melt.ji_flag}")


# 根据数据库截图中的实际数据进行测试
def test_known_data ():
	"""测试数据库中已知存在的数据"""
	print("\n=== 测试已知数据 ===")
	
	# 从数据库截图中选择几个已知存在的记录进行测试
	test_cases = [
		("Cu", "Si", "Si", 1873.0),  # 行499: eji="744.06/T-0.33", sji="75500/T-32.9"
		("Ni", "O", "Mg", 1873.0),  # 行481: eji="-126300/T+39.0", sji=NULL
		("Fe", "O", "Al", 1873.0),  # 行500: eji="-0.83", sji=NULL, T="1923"
		("Co", "O", "Cu", 1873.0),  # 行476: eji="-0.009", sji=NULL, T="1873"
		("Ni", "O", "Fe", 1873.0),  # 行478: eji="-0.026", sji=NULL, T="1873"
	]
	
	for solv, solui, soluj, temp in test_cases:
		print(f"\n{'=' * 60}")
		print(f"测试组合: {solv}-{solui}-{soluj} @ {temp}K")
		print(f"{'=' * 60}")
		
		try:
			melt = Melt(solv, solui, soluj, temp)
			
			print(f"\n📊 最终结果:")
			print(f"   sji = {melt.sji}")
			print(f"   eji = {melt.eji}")
			print(f"   sij = {melt.sij}")
			print(f"   eij = {melt.eij}")
			
			# 验证转换是否正确
			if not math.isnan(melt.sji):
				print(f"\n✅ 成功获取到sji值: {melt.sji}")
			elif not math.isnan(melt.eji):
				print(f"\n✅ 成功获取到eji值: {melt.eji}")
			else:
				print(f"\n❌ 未获取到有效数据")
		
		except Exception as e:
			print(f"\n❌ 测试失败: {e}")
		
		print("-" * 60)


def test_specific_case ():
	"""测试特定的已知有sji值的案例"""
	print("\n=== 测试Cu-Si-Si案例（同时有sji和eji） ===")
	
	# 这个案例从截图看同时有sji和eji值
	solv, solui, soluj = "Cu", "Si", "Si"
	temp = 1873.0
	
	print(f"测试参数: {solv}-{solui}-{soluj} @ {temp}K")
	print("预期: eji='744.06/T-0.33', sji='75500/T-32.9'")
	
	# 手动计算预期值
	expected_eji = 744.06 / temp - 0.33
	expected_sji = 75500 / temp - 32.9
	print(f"预期计算结果: eji={expected_eji:.3f}, sji={expected_sji:.3f}")
	
	melt = Melt(solv, solui, soluj, temp)
	
	print(f"\n实际结果:")
	print(f"  sji = {melt.sji}")
	print(f"  eji = {melt.eji}")
	
	# 检查是否匹配
	if not math.isnan(melt.sji) and abs(melt.sji - expected_sji) < 0.1:
		print(f"✅ sji计算正确!")
	elif not math.isnan(melt.eji) and abs(melt.eji - expected_eji) < 0.1:
		print(f"✅ eji计算正确!")
	else:
		print(f"❌ 计算结果与预期不符")
if __name__ == "__main__":
	test_known_data()
	test_specific_case()
	test_known_data()