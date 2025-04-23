from typing import Callable

from PyQt5.QtWidgets import QMessageBox

extrap_func = Callable[[str, str, str, float, str], float]


class Constants:
	R = 8.314  # Universal gas constant J/(mol*K)
	QtoP = 9.4
	P_TT = 14.2
	P_NN = 10.7
	P_TN = 12.35
	Q_TT = 132
	Q_TN = 116
	Q_NN = 100
	
	# Periodic table with atomic numbers
	periodic_table = {
		"H": 1, "Li": 3, "Be": 4, "B": 5, "C": 6, "N": 7, "O": 8, "F": 9,
		"Na": 11, "Mg": 12, "Al": 13, "Si": 14, "P": 15, "S": 16, "Cl": 17,
		"K": 19, "Ca": 20, "Sc": 21, "Ti": 22, "V": 23, "Cr": 24, "Mn": 25, "Fe": 26,
		"Co": 27, "Ni": 28, "Cu": 29, "Zn": 30, "Ga": 31, "Ge": 32, "As": 33, "Se": 34, "Br": 35,
		"Rb": 37, "Sr": 38, "Y": 39, "Zr": 40, "Nb": 41, "Mo": 42, "Tc": 43, "Ru": 44, "Rh": 45,
		"Pd": 46, "Ag": 47, "Cd": 48, "In": 49, "Sn": 50, "Sb": 51, "Te": 52, "I": 53, "Cs": 55,
		"Ba": 56, "Hf": 72, "Ta": 73, "W": 74, "Re": 75, "Os": 76, "Ir": 77, "Pt": 78, "Au": 79,
		"Hg": 80, "Tl": 81, "Pb": 82, "Bi": 83, "Po": 84, "At": 85, "Fr": 87, "Ra": 88, "Rf": 104,
		"Db": 105, "Sg": 106, "Bh": 107, "Hs": 108, "Mt": 109, "Ds": 110, "Rg": 111, "Cn": 112,
		"Nh": 113, "Fl": 114, "Mc": 115, "Lv": 116, "Ts": 117, "La": 57, "Ce": 58, "Pr": 59,
		"Nd": 60, "Pm": 61, "Sm": 62, "Eu": 63, "Gd": 64, "Tb": 65, "Dy": 66, "Ho": 67, "Er": 68,
		"Tm": 69, "Yb": 70, "Lu": 71, "Ac": 89, "Th": 90, "Pa": 91, "U": 92, "Np": 93, "Pu": 94,
		"Am": 95, "Cm": 96, "Bk": 97, "Cf": 98, "Es": 99, "Fm": 100, "Md": 101, "No": 102,
		"Lr": 103
	}
	
	# Non-metal elements list
	non_metal_list = ["H", "B", "C", "N", "Si", "P", "Ge"]


## element.py


class Element:
	def __init__ (self, name):
		self.name = name
		self.phi = 0.0
		self.n_ws = 0.0
		self.v = 0.0
		self.u = 0.0
		self.alpha_beta = ""
		self.hybrid_value = 0.0
		self.is_trans_group = False
		self.dh_trans = 0.0
		self.m = 0.0
		self.tm = 0.0
		self.tb = 0.0
		self.bkm = 0.0  # Bulk modulus
		self.shm = 0.0  # Shear modulus
		self.is_exist = False
		
		if name in Constants.periodic_table:
			self.is_exist = True
			self.get_miedema_data()
	
	def get_miedema_data (self):
		"""Load element data from database"""
		try:
			conn = sqlite3.connect("data/DataBase.db")
			cursor = conn.cursor()
			
			query = "SELECT phi, nws, V, u, alpha_beta, hybirdvalue, isTrans, dHtrans, mass, Tm, Tb FROM MiedemaParameter WHERE Symbol = ?"
			cursor.execute(query, (self.name,))
			
			row = cursor.fetchone()
			if row:
				self.phi = row[0]
				self.n_ws = row[1]
				self.v = row[2]
				self.u = row[3]
				self.hybrid_factor = row[4]
				self.hybrid_value = row[5]
				self.is_trans_group = bool(row[6])
				self.dh_trans = row[7]
				self.m = row[8]
				self.tm = row[9]
				self.tb = row[10]
			
			conn.close()
		except Exception as e:
			print(f"Error loading element data: {e}")
			self.is_exist = False


## binary_model.py
import math

from scipy import integrate


class BinaryModel:
	def __init__ (self):
		self.ea = None
		self.eb = None
		self._state = "liquid"
		self._lambda = 0
		self.temperature = 0
		self.is_entropy = False
		
		# Dictionaries for memoization
		self.yeta_dict = {}
		self.df_uem2 = {}
		self.df_uem2adv_x = {}
		self.df_uem2adv_y = {}
		self.df_uem2adv_a = {}
		self.new_df_uem2 = {}
	
	def set_temperature (self, temp):
		self.temperature = temp
	
	def set_pair_element (self, element_a, element_b):
		self.ea = Element(element_a)
		self.eb = Element(element_b)
	
	def set_state (self, state):
		self._state = state
	
	def set_lambda (self, n):
		self._lambda = n
	
	def set_entropy (self, is_se):
		self.is_entropy = is_se
	
	def fab (self, ea, eb, state):
		"""Calculate Fab value according to Miedema model"""
		if ea.is_exist and eb.is_exist:
			p_ab = Constants.P_TT if (ea.is_trans_group and eb.is_trans_group) else \
				(Constants.P_TN if (ea.is_trans_group or eb.is_trans_group) else Constants.P_NN)
			
			rp_value = self.rp(ea, eb, state)
			
			diff = 2 * p_ab * (-(ea.phi - eb.phi) ** 2 + Constants.QtoP * (ea.n_ws - eb.n_ws) ** 2 - rp_value) / \
			       (1.0 / ea.n_ws + 1.0 / eb.n_ws)
			return diff
		else:
			return float('nan')
	
	def rp (self, ea, eb, state):
		"""Calculate RP term in Miedema model"""
		alpha = 1.0 if state == "solid" else 0.73
		
		if ea.hybrid_factor == "other" or eb.hybrid_factor == "other":
			return 0.0
		else:
			return 0.0 if ea.hybrid_factor == eb.hybrid_factor else alpha * ea.hybrid_value * eb.hybrid_value
	
	def binary_model (self, a, b, xa, xb):
		"""
		Binary model calculation

		Args:
			a: Element A name
			b: Element B name
			xa: Molar composition of A
			xb: Molar composition of B

		Returns:
			Binary system property in kJ/mol
		"""
		self.set_pair_element(a, b)
		
		f_ab = self.fab(self.ea, self.eb, self._state)
		entropy_term = 0
		
		if self.is_entropy:
			avg_tm = 1.0 / self.ea.tm + 1.0 / self.eb.tm
			if self._state == "solid":
				entropy_term = 1.0 / 15.1 * avg_tm * self.temperature
			else:
				entropy_term = 1.0 / 14 * avg_tm * self.temperature
		
		f_ab = f_ab * (1 - entropy_term)
		
		vaa, vba = self.v_in_alloy(self.ea, self.eb, xa, xb)
		
		ca = xa / (xa + xb)
		cb = xb / (xa + xb)
		
		cas = ca * vaa / (ca * vaa + cb * vba)
		cbs = cb * vba / (ca * vaa + cb * vba)
		
		fb = cbs * (1 + self._lambda * (cas * cbs) ** 2)
		
		dh_trans = self.ea.dh_trans * xa / (xa + xb) + self.eb.dh_trans * xb / (xa + xb)
		
		return fb * f_ab * ca * vaa + dh_trans
	
	def v_in_alloy (self, ea, eb, xa, xb):
		"""Calculate volumes in alloy"""
		ya = xa / (xa + xb)
		yb = xb / (xa + xb)
		
		if ea.name == "H" or eb.name == "H":
			# Special treatment for hydrogen
			vaa = ea.v
			vba = eb.v
			max_iterations = 1000
			iterations = 0
			
			while iterations < max_iterations:
				new_vaa = vaa
				new_vba = vba
				
				pax = ya * vaa / (ya * vaa + yb * vba)
				pbx = yb * vba / (ya * vaa + yb * vba)
				
				vaa = ea.v * (1 + ea.u * pbx * (1 + self._lambda * (pax * pbx) ** 2) * (ea.phi - eb.phi))
				vba = eb.v * (1 + eb.u * pax * (1 + self._lambda * (pax * pbx) ** 2) * (eb.phi - ea.phi))
				
				if abs(vaa - new_vaa) < 1e-6 and abs(vba - new_vba) < 1e-6:
					break
				
				iterations += 1
		else:
			vaa = ea.v * (1 + ea.u * ya * (ea.phi - eb.phi))
			vba = eb.v * (1 + eb.u * yb * (eb.phi - ea.phi))
		
		return vaa, vba
	
	def elastic_a_in_b (self, a, b):
		"""Calculate elastic term for solid solution phase"""
		self.set_pair_element(a, b)
		
		alpha = -6.0 * self.ea.v * (1 + self.ea.u * (self.ea.phi - self.eb.phi)) / (
				1.0 / self.ea.n_ws + 1.0 / self.eb.n_ws)
		va = self.ea.v ** (3.0 / 2) + alpha * (self.eb.phi - self.ea.phi) / self.ea.n_ws ** 3
		vb = self.eb.v ** (3.0 / 2) + alpha * (self.eb.phi - self.ea.phi) / self.eb.n_ws ** 3
		
		dhe = 2 * self.ea.bkm * self.eb.shm * (vb - va) ** 2 / (3 * self.ea.bkm * vb + 4 * self.eb.shm * va)
		
		return 10 ** (-9) * dhe
	
	def yeta (self, k, a, b,Temp:float,state:str):
		"""Calculate GSM's similarity coefficient"""
		m1 = BinaryModel()
		m2 = BinaryModel()
		
		m1.set_state(state)
		m2.set_state(state)
		m1.set_temperature(Temp)
		m2.set_temperature(Temp)
		
		key = k + a + b + str(Temp)
		if key in self.yeta_dict:
			return self.yeta_dict[key]
		
		def func (x):
			return m1.binary_model(a, b, x, 1 - x) - m2.binary_model(a, k, x, 1 - x)
		
		def func2 (x):
			return func(x) ** 2
		
		result = integrate.quad(func2, 0, 1)[0]
		self.yeta_dict[key] = result
		
		return result
	
	def deviation_func (self, k, i, j, t):
		"""Calculate deviation function for UEM2"""
		mij = BinaryModel()
		mkj = BinaryModel()
		
		mij.set_entropy(True)
		mkj.set_entropy(True)
		mij.set_pair_element(i, j)
		mij.set_state("liquid")
		mij.set_temperature(t)
		mkj.set_pair_element(k, j)
		mkj.set_state("liquid")
		mkj.set_temperature(t)
		
		cond1 = i + j + str(self._lambda) + self._state + str(self.temperature)
		cond2 = k + j + str(self._lambda) + self._state + str(self.temperature)
		
		if cond1 in self.df_uem2:
			f_ij = self.df_uem2[cond1]
		else:
			def func_ij (x):
				return mij.binary_model(i, j, x, 1 - x) * 1000 / (8.314 * t)
			
			f_ij = integrate.quad(func_ij, 0, 1)[0]
			self.df_uem2[cond1] = f_ij
		
		if cond2 in self.df_uem2:
			f_kj = self.df_uem2[cond2]
		else:
			def func_kj (x):
				return mkj.binary_model(k, j, x, 1 - x) * 1000 / (8.314 * t)
			
			f_kj = integrate.quad(func_kj, 0, 1)[0]
			self.df_uem2[cond2] = f_kj
		
		return abs((f_ij - f_kj) / (f_ij + f_kj))
	
	def get_graphic_center (self, k, i, phase_state="liquid"):
		"""Calculate center coordinates (x,y) of function graph"""
		mki = BinaryModel()
		
		mki.set_entropy(True)
		mki.set_pair_element(i, k)
		mki.set_state("liquid")
		mki.set_temperature(self.temperature)
		
		cond1 = i + k + str(self._lambda) + self._state + str(self.temperature)
		
		if cond1 in self.df_uem2adv_x:
			x_bar = self.df_uem2adv_x[cond1]
			a = self.df_uem2adv_a[cond1]
			y = self.df_uem2adv_y[cond1]
		else:
			def func_x (x):
				return mki.binary_model(k, i, x, 1 - x) * 1000
			
			def xfunc_x (x):
				return x * func_x(x)
			
			def func_x2 (x):
				return func_x(x) * func_x(x)
			
			x_bar = integrate.quad(xfunc_x, 0, 1)[0]
			a = integrate.quad(func_x, 0, 1)[0]
			y = integrate.quad(func_x2, 0, 1)[0]
			
			self.df_uem2adv_x[cond1] = x_bar
			self.df_uem2adv_a[cond1] = a
			self.df_uem2adv_y[cond1] = y
		
		x_ = x_bar / a
		y_ = y / (2.0 * a)
		
		return (x_ - 0.5, y_)
	
	def get_d_ki (self, k, i, j):
		"""Calculate property difference between components k and i"""
		xij, yij = self.get_graphic_center(i, j)
		xkj, ykj = self.get_graphic_center(k, j)
		
		hx1_x2 = abs(xij - xkj) / abs(xij + xkj)
		ty1_y2 = math.exp(abs(yij - ykj) / abs(yij + ykj))
		
		theta10 = math.atan2(xij, yij)
		theta11 = math.atan2(yij, xij)
		theta20 = math.atan2(xkj, ykj)
		theta21 = math.atan2(ykj, xkj)
		
		a = math.sqrt(xij ** 2 + yij ** 2)
		b = math.sqrt(xkj ** 2 + ykj ** 2)
		
		dki = abs((math.pi / 2.0 * (theta10 ** 2 - theta20 ** 2) + self.delta_x(theta10, theta20)) /
		          (theta10 ** 2 + theta20 ** 2)) * abs(a - b) / math.sqrt(a ** 2 + b ** 2)
		
		return dki
	
	def delta_x (self, x, y):
		"""Helper function for get_d_ki"""
		if (abs(x) >= 0 and abs(x) <= math.pi / 2.0) and (abs(y) >= 0 and abs(y) <= math.pi / 2.0):
			return 0
		elif (abs(x) >= math.pi / 2.0 and abs(x) <= math.pi) and (abs(y) >= math.pi / 2.0 and abs(y) <= math.pi):
			return 0
		else:
			return math.pi / 2.0
	
	def UEM1 (self, k, i, j, Tem: float, phase_state: str):
		"""Implementation of UEM1 model"""
		ek = Element(k)
		ei = Element(i)
		ej = Element(j)
		
		ternary = TernaryMelts()
		ternary.set_state(phase_state)
		ternary.set_temperature(Tem)
		
		inter_ik = ternary.kexi(ek, ei)
		inter_ki = ternary.kexi(ei, ek)
		inter_jk = ternary.kexi(ek, ej)
		inter_kj = ternary.kexi(ej, ek)
		
		df_ki = abs(inter_ik - inter_ki)
		df_kj = abs(inter_jk - inter_kj)
		
		if df_ki == 0 and df_kj == 0:
			df_ki = df_kj = -0.0000000000001
		
		alpha = math.exp(-df_ki)
		beta3 = df_kj / (df_ki + df_kj)
		alpha_ka = alpha * beta3
		
		return alpha_ka
	
	def UEM2 (self, k, i, j, Tem: float, phase_state: str):
		"""Implementation of UEM2 model"""
		ek = Element(k)
		ei = Element(i)
		ej = Element(j)
		
		ternary = TernaryMelts()
		ternary.set_state(phase_state)
		ternary.set_temperature(Tem)
		ternary.set_entropy(False)
		df_ki = self.deviation_func(k, i, j, Tem)
		df_kj = self.deviation_func(k, j, i, Tem)
		
		df_ki = 1 * df_ki ** 1
		df_kj = 1 * df_kj ** 1
		
		weight1 = df_kj / (df_ki + df_kj)
		alpha_ka = math.exp(-df_ki) * weight1
		
		return alpha_ka
	
	def GSM (self, k, i, j, Tem: float, phase_state: str):
		"""Implementation of GSM model"""
		nki = self.yeta(k, i, j,Tem,phase_state)
		nkj = self.yeta(k, j, i,Tem,phase_state)
		
		return nki / (nki + nkj)
	
	def Muggianu (self, k, i, j, Tem: float, phase_state: str):
		return 0.5


class TernaryMelts:
	def __init__ (self, t=0.0, phase_state="liquid", is_se=False):
		self._temperature = t
		self._state = phase_state
		self._entropy = is_se
		self._cp = False
		self._condition = (is_se, self._cp)
	
	def set_temperature (self, temp):
		self._temperature = temp
	
	def set_entropy (self, entropy):
		self._entropy = entropy
	
	def set_state (self, state):
		self._state = state
	
	def fab_pure (self, ei, ej, s=False):
		"""Calculate pure Fab without entropy term"""
		alpha = 0.73 if self._state == "liquid" else 1.0
		
		if ei.hybrid_factor != "other" or ej.hybrid_factor != "other":
			rp = 0.0 if ei.hybrid_factor == ej.hybrid_factor else ei.hybrid_value * ej.hybrid_value
		else:
			rp = 0.0
		
		p = Constants.P_TT if (ei.is_trans_group and ej.is_trans_group) else \
			(Constants.P_TN if (ei.is_trans_group or ej.is_trans_group) else Constants.P_NN)
		
		fij = 2 * p * (Constants.QtoP * (ei.n_ws - ej.n_ws) ** 2 - (ei.phi - ej.phi) ** 2 - alpha * rp) / \
		      (1 / ei.n_ws + 1 / ej.n_ws)
		
		return fij
	
	def fab_func_contain_s (self, ei, ej, s=False):
		"""Calculate Fab including entropy term"""
		alpha = 0.73 if self._state == "liquid" else 1.0
		
		avg_tm = 1.0 / ei.tm + 1.0 / ej.tm
		
		if s:
			if self._state == "liquid":
				entropy_term = 1.0 / 14 * self._temperature * avg_tm
			else:
				entropy_term = 1.0 / 15.1 * self._temperature * avg_tm
		else:
			entropy_term = 0.0
		
		if ei.hybrid_factor != "other" or ej.hybrid_factor != "other":
			rp = 0.0 if ei.hybrid_factor == ej.hybrid_factor else ei.hybrid_value * ej.hybrid_value
		else:
			rp = 0.0
		
		pij = Constants.P_TT if (ei.is_trans_group and ej.is_trans_group) else \
			(Constants.P_TN if (ei.is_trans_group or ej.is_trans_group) else Constants.P_NN)
		
		fij = 2.0 * pij * (Constants.QtoP * (ei.n_ws - ej.n_ws) ** 2 - (ei.phi - ej.phi) ** 2 - alpha * rp) / \
		      (1.0 / ei.n_ws + 1.0 / ej.n_ws)
		
		return fij * (1 - entropy_term)
	
	def kexi (self, solvent, solutei):
		"""Calculate ξ^k_i for UEM1 model"""
		fik = self.fab_pure(solvent, solutei)
		elements_lst = ["Si", "Ge"]
		
		if self._state == "liquid":
			if solutei.name in elements_lst:
				dhtrans_i = 0
			else:
				dhtrans_i = solutei.dh_trans
			
			if solvent.name in elements_lst:
				dhtrans_slv = 0
			else:
				dhtrans_slv = solvent.dh_trans
		else:
			dhtrans_i = solutei.dh_trans
			dhtrans_slv = solvent.dh_trans
		
		dhtrans = dhtrans_slv
		
		lny0 = 1000 * fik * solutei.v * (1 + solutei.u * (solutei.phi - solvent.phi)) / \
		       (Constants.R * self._temperature) + 1000 * dhtrans / (Constants.R * self._temperature)
		
		return lny0
	
	def first_derivative_qx (self, i_element: Element, j_element: Element, xi: float = 0) -> float:
		"""Calculate first derivative of Q(x)"""
		
		fij = self.fab_func_contain_s(i_element, j_element,entropy_judge(i_element.name,j_element.name))
		
		vi = i_element.v
		vj = j_element.v
		ui = i_element.u
		uj = j_element.u
		phi_i = i_element.phi
		phi_j = j_element.phi
		delta_phi = phi_i - phi_j
		
		ax = vi * (1 + ui * delta_phi * (1 - xi))
		bx = vj * (1 - uj * delta_phi * xi)
		dx = xi * ax + (1 - xi) * bx
		nx = ax * bx
		
		dax = -ui * delta_phi * vi
		dbx = -uj * delta_phi * vj
		
		ddx = ax + xi * dax - bx + (1 - xi) * dbx
		dnx = dax * bx + ax * dbx
		
		dfx = (dnx * dx - ddx * nx) / (dx * dx)
		
		return dfx
	
	def second_derivative_q0 (self, i_element: Element, j_element: Element, xi=0):
		"""Calculate second derivative of Q(x) at x=0"""
		fij = self.fab_func_contain_s(i_element, j_element,entropy_judge(i_element.name,j_element.name))
		
		vi = i_element.v
		vj = j_element.v
		ui = i_element.u
		uj = j_element.u
		phi_i = i_element.phi
		phi_j = j_element.phi
		delta_phi = phi_i - phi_j
		
		dd_f = 2 * fij * vi ** 3 * (1 + 3 * ui * delta_phi + ui * ui * delta_phi ** 2 +
		                            2 * uj * delta_phi + ui * uj * delta_phi * delta_phi) / (vj * vj)
		
		return dd_f
	
	def ln_y0 (self, solvent, solutei):
		"""Calculate ln(γ°i) = G^E_i/(RT)"""
		fik = self.fab_func_contain_s(solvent, solutei,entropy_judge(solvent,solutei))
		dhtrans = solutei.dh_trans
		
		lny0 = 1000 * fik * solutei.v * (1 + solutei.u * (solutei.phi - solvent.phi)) + 1000 * dhtrans
		
		return lny0 / (Constants.R * self._temperature)
	
	def present_model1_aip_elac (self, solv, solui, soluj, contri_func, geo_model, mode="Normal"):
		"""Calculate elastic contribution to first-order interaction parameter"""
		
		binary = BinaryModel()
		
		alphai_jk = contri_func(solui.name, soluj.name, solv.name, mode)
		alphaj_ik = contri_func(soluj.name, solui.name, solv.name, mode)
		alphai_kj = contri_func(solui.name, solv.name, soluj.name, mode)
		alphaj_ki = contri_func(soluj.name, solv.name, solui.name, mode)
		alphak_ij = contri_func(solv.name, solui.name, soluj.name, mode)
		alphak_ji = contri_func(solv.name, soluj.name, solui.name, mode)
		
		hj_in_i = binary.elastic_a_in_b(soluj.name, solui.name)
		hi_in_j = binary.elastic_a_in_b(solui.name, soluj.name)
		hi_in_k = binary.elastic_a_in_b(solui.name, solv.name)
		hk_in_i = binary.elastic_a_in_b(solv.name, solui.name)
		hj_in_k = binary.elastic_a_in_b(soluj.name, solv.name)
		hk_in_j = binary.elastic_a_in_b(solv.name, soluj.name)
		
		hik = hi_in_k
		hjk = hj_in_k
		dhik = alphaj_ik * (hk_in_i - hi_in_k)
		dhjk = alphai_jk * (hk_in_j - hj_in_k)
		
		hij = alphak_ij / (alphak_ij + alphak_ji) * hj_in_i + alphak_ji / (alphak_ij + alphak_ji) * hi_in_j
		
		return 1000.0 * (hij - hik - hjk + dhik + dhjk) / (Constants.R * self._temperature)
	
	def activity_interact_coefficient_1st (self, solv, solui, soluj, Tem: float, state: str, geo_model: extrap_func,
	                                       geo_model_name="UEM1"):
		"""Calculate first-order interaction coefficient"""
		import os
		entropy_yesornot = entropy_judge(solv,solui,soluj)
		fij = self.fab_func_contain_s(solui, soluj,entropy_yesornot)
		fik = self.fab_func_contain_s(solv, solui,entropy_yesornot)
		fjk = self.fab_func_contain_s(solv, soluj,entropy_yesornot)
		
		file_path = os.path.join(os.getcwd(), "Contribution Coefficient")
		os.makedirs(file_path, exist_ok=True)
		
		aji_ik = geo_model(soluj.name, solui.name, solv.name, Tem, state)
		ajk_ik = geo_model(soluj.name, solv.name, solui.name, Tem, state)
		aij_jk = geo_model(solui.name, soluj.name, solv.name, Tem, state)
		aki_ij = geo_model(solv.name, solui.name, soluj.name, Tem, state)
		akj_ij = geo_model(solv.name, soluj.name, solui.name, Tem, state)
		aik_jk = geo_model(solui.name, solv.name, soluj.name, Tem, state)
		
		file_name = os.path.join(file_path, f"{geo_model_name}.txt")
		content = (
			f"{solv.name}-{solui.name}: \t {aki_ij}, \t {solv.name}-{soluj.name}: \t {akj_ij} \t in ( {solui.name}-{soluj.name})\n"
			f"{solui.name}-{solv.name}: \t {aik_jk}, \t {solui.name}-{soluj.name}: \t {aij_jk} \t in ( {soluj.name}-{solv.name})\n"
			f"{soluj.name}-{solui.name}: \t {aji_ik}, \t {soluj.name}-{solv.name}: \t {ajk_ik} \t in ( {solui.name}-{solv.name})\n")
		
		with open(file_name, "a") as f:
			f.write(content)
		
		if aki_ij == 0 and akj_ij == 0:
			aki_ij = akj_ij = 0.5
		
		via = (1 + solui.u * (solui.phi - soluj.phi) * akj_ij * soluj.v /
		       (aki_ij * solui.v + akj_ij * soluj.v)) * solui.v
		vja = (1 + soluj.u * (soluj.phi - solui.phi) * aki_ij * solui.v /
		       (aki_ij * solui.v + akj_ij * soluj.v)) * soluj.v
		
		omaga_ij = fij * via * vja * (aki_ij + akj_ij) / (aki_ij * via + akj_ij * vja)
		omaga_ik = fik * solui.v * (1 + solui.u * (solui.phi - solv.phi))
		omaga_jk = fjk * soluj.v * (1 + soluj.u * (soluj.phi - solv.phi))
		
		d_omaga_ik_j = aji_ik * omaga_ik * (1 - solui.v / solv.v * (1 + 2 * solui.u * (solui.phi - solv.phi)))
		d_omaga_jk_i = aij_jk * omaga_jk * (1 - soluj.v / solv.v * (1 + 2 * soluj.u * (soluj.phi - solv.phi)))
		
		chemical_term = omaga_ij - omaga_jk - omaga_ik + d_omaga_ik_j + d_omaga_jk_i
		
		return 1000 * chemical_term / (Constants.R * Tem)
	
	def roui_ii (self, solv, solui, Tem: float, state: str, geo_model, geo_model_name="UEM1"):
		"""Calculate second-order self-interaction coefficient ρi^ii"""
		sii = self.activity_interact_coefficient_1st(solv, solui, solui, Tem, state, geo_model, geo_model_name)
		df10 = self.first_derivative_qx(solui, solv, 0)
		df20 = self.second_derivative_q0(solui, solv, 0)
		
		rii = -sii + 1000 * (-6 * df10 + 3 * df20) / (Constants.R * Tem)
		
		return rii
	
	def roui_jj (self, solv, solui, soluj, Tem: float, state: str, geo_model: extrap_func, geo_model_name="UEM1"):
		"""Calculate second-order interaction coefficient ρi^jj"""
		sjj = self.activity_interact_coefficient_1st(solv, soluj, soluj, Tem, state, geo_model, geo_model_name)
		
		aji_ik = geo_model(soluj.name, solui.name, solv.name, Tem, state)
		ajk_ik = geo_model(soluj.name, solv.name, solui.name, Tem, state)
		aij_jk = geo_model(solui.name, soluj.name, solv.name, Tem, state)
		aki_ij = geo_model(solv.name, solui.name, soluj.name, Tem, state)
		akj_ij = geo_model(solv.name, soluj.name, solui.name, Tem, state)
		aik_jk = geo_model(solui.name, solv.name, soluj.name, Tem, state)
		
		qij = -2 * aki_ij / (aki_ij + akj_ij) ** 2 * self.first_derivative_qx(solui, soluj, aki_ij / (aki_ij + akj_ij))
		qik = aji_ik * aji_ik * self.second_derivative_q0(solui, solv, 0) - 2 * aji_ik * (
				aji_ik + ajk_ik) * self.first_derivative_qx(solui, solv, 0)
		qjk = 2 * aij_jk * self.second_derivative_q0(soluj, solv, 0) - 2 * (
				2 * aij_jk + aik_jk) * self.first_derivative_qx(soluj, solv, 0)
		
		ri_jj = (-sjj + 1000 * (qij + qik + qjk) / (Constants.R * Tem))
		
		return ri_jj
	
	def roui_ij (self, solv, solui, soluj, Tem: float, state: str, geo_model: extrap_func, geo_model_name="UEM1"):
		"""Calculate second-order cross-interaction coefficient ρi^ij"""
		sji = self.activity_interact_coefficient_1st(solv, solui, soluj, Tem, state, geo_model, geo_model_name)
		
		aji_ik = geo_model(soluj.name, solui.name, solv.name, Tem, state)
		ajk_ik = geo_model(soluj.name, solv.name, solui.name, Tem, state)
		aij_jk = geo_model(solui.name, soluj.name, solv.name, Tem, state)
		aki_ij = geo_model(solv.name, solui.name, soluj.name, Tem, state)
		akj_ij = geo_model(solv.name, soluj.name, solui.name, Tem, state)
		aik_jk = geo_model(solui.name, solv.name, soluj.name, Tem, state)
		
		qij = 2 * akj_ij / (akj_ij + aki_ij) ** 2 * self.first_derivative_qx(solui, soluj, aki_ij / (aki_ij + aki_ij))
		qik = 2 * aji_ik * self.second_derivative_q0(solui, solv, 0) - 2 * (
				2 * aji_ik + ajk_ik) * self.first_derivative_qx(solui, solv, 0)
		qjk = aij_jk * aij_jk * self.second_derivative_q0(soluj, solv, 0) - 2 * aij_jk * (
				aij_jk + aik_jk) * self.first_derivative_qx(soluj, solv, 0)
		
		return (-sji + 1000 * (qij + qik + qjk) / (Constants.R * Tem))
	
	def roui_jk (self, m, i, j, k, Tem: float, state: str, geo_model: extrap_func, geo_model_name="UEM1"):
		"""Calculate cross-interaction parameter, the influence of components j,k on i"""
		skj = self.activity_interact_coefficient_1st(m, j, k, Tem, state, geo_model, geo_model_name)
		
		amj_ij = geo_model(m.name, j.name, i.name, Tem, state)
		ami_ij = geo_model(m.name, i.name, j.name, Tem, state)
		aki_ij = geo_model(k.name, i.name, j.name, Tem, state)
		akj_ij = geo_model(k.name, j.name, i.name, Tem, state)
		
		amk_ik = geo_model(m.name, k.name, j.name, Tem, state)
		ami_ik = geo_model(m.name, i.name, k.name, Tem, state)
		aji_ik = geo_model(j.name, i.name, i.name, Tem, state)
		ajk_ik = geo_model(j.name, k.name, i.name, Tem, state)
		
		aji_im = geo_model(j.name, i.name, m.name, Tem, state)
		ajm_im = geo_model(j.name, m.name, i.name, Tem, state)
		aki_im = geo_model(k.name, i.name, m.name, Tem, state)
		akm_im = geo_model(k.name, m.name, i.name, Tem, state)
		
		amk_jk = geo_model(m.name, k.name, j.name, Tem, state)
		amj_jk = geo_model(m.name, j.name, k.name, Tem, state)
		aik_jk = geo_model(i.name, k.name, j.name, Tem, state)
		aij_jk = geo_model(i.name, j.name, k.name, Tem, state)
		
		aij_jm = geo_model(i.name, j.name, m.name, Tem, state)
		aim_jm = geo_model(i.name, m.name, j.name, Tem, state)
		akj_jm = geo_model(k.name, j.name, m.name, Tem, state)
		akm_jm = geo_model(k.name, m.name, j.name, Tem, state)
		
		aik_km = geo_model(i.name, k.name, m.name, Tem, state)
		aim_km = geo_model(i.name, m.name, k.name, Tem, state)
		ajk_km = geo_model(j.name, k.name, m.name, Tem, state)
		ajm_km = geo_model(j.name, m.name, k.name, Tem, state)
		
		dfij = self.first_derivative_qx(i, j, ami_ij / (ami_ij + amj_ij))
		dfik = self.first_derivative_qx(i, k, ami_ik / (ami_ik + amk_ik))
		
		qij = (amj_ij * aki_ij - ami_ij * akj_ij) / (ami_ij + amj_ij) ** 2 * dfij
		qik = (amk_ik * aji_ik - ami_ik * ajk_ik) / (ami_ik + amk_ik) ** 2 * dfik
		
		dfim = self.first_derivative_qx(i, m, 0)
		ddfim = self.second_derivative_q0(i, m, 0)
		
		qim = aji_im * aki_im * ddfim - (aji_im * akm_im + aki_im * ajm_im + 2 * aji_im * aki_im) * dfim
		
		dfjk = self.first_derivative_qx(j, k, amj_jk / (amj_jk + amk_jk))
		
		qjk = (amk_jk * aij_jk - amj_jk * aik_jk) / (amj_jk + amk_jk) ** 2 * dfjk
		
		dfjm = self.first_derivative_qx(j, m, 0)
		ddfjm = self.second_derivative_q0(j, m, 0)
		qjm = aij_jm * akj_jm * ddfjm - (aij_jm * akm_jm + akj_jm * aim_jm + 2 * aij_jm * akj_jm) * dfjm
		
		dfkm = self.first_derivative_qx(k, m, 0)
		ddfkm = self.second_derivative_q0(k, m, 0)
		qkm = aik_km * ajk_km * ddfkm - (aik_km * ajm_km + ajk_km * aim_km + 2 * aik_km * ajk_km) * dfkm
		
		return 1000 * (qij + qik + qim + qjk + qjm + qkm) / (Constants.R * Tem) - skj


class ActivityCoefficient:
	def __init__ (self):
		self._comp_dict = {}
	
	@property
	def _comp_dict_original (self):
		return self._comp_dict
	
	@property
	def melts_dict (self):
		"""Return standardized molar composition dictionary"""
		comp_dict = {}
		if len(self._comp_dict) > 1:
			sum_val = sum(self._comp_dict.values())
			
			for key, value in self._comp_dict.items():
				if key in comp_dict:
					comp_dict[key] += value / sum_val
				else:
					comp_dict[key] = value / sum_val
		
		return comp_dict
	
	def set_composition_dict (self, text):
		"""Set initial composition of the system in form AxByCz"""
		pattern = r"([A-Z]{1}[a-z]?)(\d+[\.]?\d*)?"
		matches = re.finditer(pattern, text)
		
		for match in matches:
			groups = match.groups()
			element = groups[0]
			
			try:
				x = float(groups[1]) if groups[1] else 1.0
			except:
				x = 1.0
			
			if element in self._comp_dict:
				self._comp_dict[element] += x
			else:
				self._comp_dict[element] = x
	
	def activity_coefficient_wagner (self, comp_dict, solvent, solute_i, Tem: float, state: str, geo_model: extrap_func,
	                                 geo_model_name):
		"""
		Calculate activity coefficient using Wagner dilute solution model

		Args:
			comp_dict: Dictionary of alloy composition
			solvent: Base metal or solvent
			solute_i: Component for which activity coefficient is calculated
			geo_model: Geometric model
			geo_model_name: Name of geometric model
			Tem: Temperature
			state: phase state("liquid" or "solid")

		Returns:
			Natural log of activity coefficient
		"""
		
		ln_y0 = 0.0
		solv = Element(solvent)
		solu_i = Element(solute_i)
		acf = 0.0
		
		if solute_i in comp_dict:
			# Check if the solute is in the composition
			ternary = TernaryMelts(Tem, state)
			
			ln_y0 = ternary.ln_y0(solv, solu_i)
			
			for element_symbol in self.melts_dict.keys():
				if element_symbol != solvent:
					solu_j = Element(element_symbol)
					acf += self.melts_dict[element_symbol] * ternary.activity_interact_coefficient_1st(
							solv, solu_i, solu_j, Tem, state, geo_model, geo_model_name)
			
			ln_yi = ln_y0 + acf
		else:
			print(f"Component {solute_i} does not exist in the composition")
			ln_yi = 0.0
		
		return ln_yi
	
	def activity_coefficient_darken (self, comp_dict, solute_i, matrix, Tem: float, phase_state: str,
	                                 geo_model: extrap_func,
	                                 geo_model_name):
		"""
		Calculate activity coefficient using Pelton model, which adds correction terms to Wagner model

		Args:
			comp_dict: Dictionary of alloy composition
			solute_i: Solute component
			matrix: Base metal
			Tem: Temperature (K)
			geo_model: Geometric model
			geo_model_name: Name of geometric model
			phase_state: Phase state ("liquid" or "solid")

		Returns:
			Natural log of activity coefficient
		"""
		
		solv = Element(matrix)
		solui = Element(solute_i)
		ln_yi_0 = 0
		ln_yi = 0
		
		ternary_melts = TernaryMelts(Tem, phase_state)
		ln_yi_0 = ternary_melts.ln_y0(solv, solui)
		
		if matrix in comp_dict and solute_i in comp_dict:
			sum_xsij = 0
			sum_xskj = 0
			
			# Calculate ∑xjɛ^j_i
			for item_key, item_value in comp_dict.items():
				if item_key != solv.name:
					sji = ternary_melts.activity_interact_coefficient_1st(
							solv, solui, Element(item_key), Tem, phase_state, geo_model, geo_model_name)
					sum_xsij += sji * item_value
			
			# Calculate ∑xj*xi*ɛ^j_i
			item_list = list(comp_dict.items())
			for p in range(len(comp_dict)):
				for q in range(p, len(comp_dict)):
					m, n = item_list[p][0], item_list[q][0]
					
					if m != solv.name and n != solv.name:
						xm, xn = item_list[p][1], item_list[q][1]
						smn = ternary_melts.activity_interact_coefficient_1st(
								solv, Element(m), Element(n), Tem, phase_state, geo_model, geo_model_name)
						sum_xskj += xm * xn * smn
			
			ln_yi = ln_yi_0 + sum_xsij - 0.5 * sum_xskj
			return ln_yi
		else:
			return 0.0
	
	def activity_coefficient_elloit (self, comp_dict, solute_i, matrix, Tem, phase_state: str, geo_model: extrap_func,
	                                 geo_model_name):
		"""
		Calculate activity coefficient using the Elliot model with second-order interaction parameters

		Args:
			comp_dict: Dictionary of alloy composition
			solute_i: Solute component
			matrix: Base metal
			Tem: Temperature (K)
			geo_model: Geometric model
			geo_model_name: Name of geometric model
			phase_state: Phase state ("liquid" or "solid")

		Returns:
			Natural log of activity coefficient
		"""
		
		# Input validation
		if not solute_i or not matrix or not comp_dict or len(comp_dict) < 2:
			raise ValueError("Invalid input parameters: comp_dict, solute_i, or matrix.")
		
		solv = Element(matrix)
		solui = Element(solute_i)
		
		# Ensure the dictionary contains the specified solute and solvent
		if matrix not in comp_dict:
			raise ValueError(f"Composition dictionary must contain the solvent: {matrix}")
		
		if solute_i not in comp_dict:
			raise ValueError(f"Composition dictionary must contain the target solute: {solute_i}")
		
		# Create TernaryMelts instance
		ternary_melts = TernaryMelts(Tem, phase_state)
		
		# Term 1: Infinite dilution activity coefficient ln(gamma_i^0)
		ln_yi_0 = ternary_melts.ln_y0(solv, solui)
		if math.isnan(ln_yi_0) or math.isinf(ln_yi_0):
			print(f"Warning: lnY0 returned invalid value ({ln_yi_0}) for solute {solui.name}, solvent {solv.name}")
		
		# Term 2: First-order interaction term ∑ (epsilon_i^j * xj)
		linear_sum = 0
		# Loop through all components j
		for j_name, xj in comp_dict.items():
			# Only sum over solute components (j != m)
			if j_name != solv.name:
				soluj = Element(j_name)
				# Get first-order parameter epsilon_i^j
				epsilon_i_j = ternary_melts.activity_interact_coefficient_1st(
						solv, solui, soluj, Tem, phase_state, geo_model, geo_model_name)
				
				if math.isnan(epsilon_i_j) or math.isinf(epsilon_i_j):
					print(f"Warning: Epsilon(i={solui.name}, j={j_name}) returned invalid value ({epsilon_i_j})")
				else:
					linear_sum += epsilon_i_j * xj
		
		# Term 3: Second-order interaction term (1/2) * ∑ ∑ (rho_i^{j,k} * xj * xk)
		quadratic_sum = 0
		# Get all solute names (j != m)
		solute_keys = [k for k in comp_dict.keys() if k != solv.name]
		
		# Loop through all solute pairs (j, k)
		for j_name in solute_keys:
			xj = comp_dict[j_name]
			soluj = Element(j_name)
			
			for k_name in solute_keys:
				xk = comp_dict[k_name]
				soluk = Element(k_name)
				
				# Get second-order parameter rho_i^{j,k}
				rho_i_jk = ternary_melts.roui_jk(solv, solui, soluj, soluk, Tem, phase_state, geo_model, geo_model_name)
				
				if math.isnan(rho_i_jk) or math.isinf(rho_i_jk):
					print(f"Warning: Rho(i={solui.name}, j={j_name}, k={k_name}) returned invalid value ({rho_i_jk})")
				else:
					# Add (1/2) * rho_i^{j,k} * xj * xk
					quadratic_sum += 0.5 * rho_i_jk * xj * xk
		
		# Final result: ln(gamma_i) = ln(gamma_i^0) + linear_term + quadratic_term
		ln_yi = ln_yi_0 + linear_sum + quadratic_sum
		
		return ln_yi


## melt.py
import re

import sqlite3


class Melt:
	"""Melt class, used to store activity interaction coefficients between components in a melt"""
	
	def __init__ (self, solv, solui, soluj=None, t=None):
		"""
		Constructor for Melt

		Args:
			solv: Base metal/solvent
			solui: Solute i
			soluj: Solute j (optional)
			t: Melt temperature (K)
		"""
		self.name = solv + solui + (soluj if soluj else "")
		self.solv = solv
		self.solui = solui
		self.soluj = soluj
		self._tem = t
		
		self.ij_flag = False  # Indicate if the string queried is ij type
		self.ji_flag = False  # Indicate if the string queried is ji type
		
		self.eji_str = None
		self.sji_str = None
		self.eij_str = None
		self.sij_str = None
		
		self.str_t = None
		self.rank_firstorder = None
		
		self.str_ln_yi0 = (None, None)
		self.str_yi0 = (None, None)
		self.str_rji = (None, None)
		self.str_pji = (None, None)
		
		self._eji = 0
		self._eij = 0
		self._ln_yi0 = 0
		self._yi0 = 0
		self._sji = 0
		self._sij = 0
		self._rji = 0
		self._pji = 0
		
		self.ref = ""
		
		# Load data from database
		self.query_first_order_wagner_intp()
		self.query_ln_yi0()
		
		# Process the data
		if self.ij_flag:
			if self.eij_str is not None:
				self._eij = self.process_data((self.eij_str, self.str_t), t)
				self._sij = self.first_order_w2m(self._eij, Element(solui), Element(solv))
				self._sji = self._sij
				self._eji = self.first_order_m_to_w(self._sji, Element(soluj), Element(solv))
			else:
				self._sij = self.process_data((self.sij_str, self.str_t), t)
				self._eij = self.first_order_m_to_w(self._sij, Element(solui), Element(solv))
				self._sji = self._sij
				self._eji = self.first_order_m_to_w(self._sji, Element(soluj), Element(solv))
		elif self.ji_flag:
			if self.eji_str is not None:
				self._eji = self.process_data((self.eji_str, self.str_t), t)
				self._sji = self.first_order_w2m(self._eji, Element(soluj), Element(solv))
				self._sij = self._sji
				self._eij = self.first_order_m_to_w(self._sij, Element(solui), Element(solv))
			else:
				self._sji = self.process_data((self.sji_str, self.str_t), t)
				self._eji = self.first_order_m_to_w(self._sji, Element(soluj), Element(solv))
				self._sij = self._sji
				self._eij = self.first_order_m_to_w(self._sij, Element(solui), Element(solv))
		else:
			self._eij = self._eji = self._sij = self._sji = float('nan')
		
		self._yi0 = self.process_data(self.str_yi0, t)
		self._ln_yi0 = self.process_data(self.str_ln_yi0, t)
	
	@property
	def based (self):
		"""Return base metal"""
		return self.solv
	
	@property
	def eji (self):
		"""Return first-order interaction coefficient in weight percent, j on i"""
		return self._eji
	
	@property
	def eij (self):
		"""Return first-order interaction coefficient in weight percent, i on j"""
		return self._eij
	
	@property
	def sji (self):
		"""Return first-order interaction coefficient in mole fraction, j on i"""
		return self._sji
	
	@property
	def sij (self):
		"""Return first-order interaction coefficient in mole fraction, i on j"""
		return self._sij
	
	@property
	def yi0 (self):
		"""Return infinite dilution activity coefficient"""
		return self._yi0
	
	@property
	def ln_yi (self):
		"""Return natural log of infinite dilution activity coefficient"""
		if not math.isnan(self.yi0):
			return self.ln(self.yi0)
		else:
			return self._ln_yi0
	
	def query_first_order_wagner_intp (self):
		"""Query first-order Wagner interaction parameter from database"""
		try:
			conn = sqlite3.connect("data/DataBase.db")
			cursor = conn.cursor()
			
			# Query for k-i-j
			query1 = "SELECT eji, Rank, sji, T, reference FROM first_order WHERE solv = ? AND solui = ? AND soluj = ?"
			cursor.execute(query1, (self.solv, self.solui, self.soluj))
			row = cursor.fetchone()
			
			if row:
				self.ji_flag = True
				if not row[0]:  # eji is empty
					self.eji_str = None
					self.rank_firstorder = row[1]
					self.sji_str = row[2]
					self.str_t = row[3]
					self.ref = row[4] if row[4] else ""
				else:
					self.eji_str = row[0]
					self.rank_firstorder = row[1]
					self.sji_str = None
					self.str_t = row[3]
					self.ref = row[4] if row[4] else ""
			else:
				# Query for k-j-i
				query2 = "SELECT eji, Rank, sji, T, reference FROM first_order WHERE solv = ? AND solui = ? AND soluj = ?"
				cursor.execute(query2, (self.solv, self.soluj, self.solui))
				row = cursor.fetchone()
				
				if row:
					self.ij_flag = True
					if not row[0]:  # eji is empty
						self.eij_str = None
						self.rank_firstorder = row[1]
						self.sij_str = row[2]
						self.str_t = row[3]
						self.ref = row[4] if row[4] else ""
					else:
						self.eij_str = row[0]
						self.sij_str = None
						self.rank_firstorder = row[1]
						self.str_t = row[3]
						self.ref = row[4] if row[4] else ""
				else:
					self.ij_flag = False
					self.ji_flag = False
			
			conn.close()
		except Exception as e:
			print(f"Error querying first order Wagner interaction parameters: {e}")
	
	def query_ln_yi0 (self):
		"""Query infinite dilution activity coefficient from database"""
		try:
			conn = sqlite3.connect("data/DataBase.db")
			cursor = conn.cursor()
			
			query = "SELECT lnYi0, Yi0, T FROM lnY0 WHERE solv = ? AND solui = ?"
			cursor.execute(query, (self.solv, self.solui))
			
			row = cursor.fetchone()
			if row:
				if row[2] == "T":  # Expression
					self.str_ln_yi0 = (row[0] if row[0] else "", row[2])
					self.str_yi0 = (row[1] if row[1] else "", row[2])
				elif row[2] == self.str_t:  # Multiple temperatures
					self.str_ln_yi0 = (row[0] if row[0] else "", row[2])
					self.str_yi0 = (row[1] if row[1] else "", row[2])
			
			conn.close()
		except Exception as e:
			print(f"Error querying infinite dilution activity coefficient: {e}")
	
	def process_data (self, text_info, t):
		"""Process data with temperature dependence"""
		if not text_info or not text_info[0] or text_info[0] == "":
			return float('nan')
		
		if text_info[1] == "T":
			# Expression related to temperature
			pattern = r"^([-]?\d*\.?\d*)([\/])([T])(([\+]|[\-]?)\d*\.?\d*)"
			match = re.match(pattern, text_info[0])
			
			if match:
				groups = match.groups()
				a = float(groups[0])
				b = float(groups[3])
				return a / t + b
		else:
			# Experimental value at specific temperature
			if text_info[1] and float(text_info[1]) == t:
				return float(text_info[0])
		
		return float('nan')
	
	def ln (self, x):
		"""Calculate natural logarithm with special cases handling"""
		if x > 0:
			return math.log(x)
		elif x == 0.0:
			return float('-inf')
		else:
			return float('nan')
	
	def first_order_m_to_w (self, sji, element_j, matrix):
		"""Convert first-order interaction coefficient from mole fraction to weight percent"""
		return (sji - 1 + element_j.m / matrix.m) * matrix.m / (230 * element_j.m)
	
	def first_order_w2m (self, eji, element_j, matrix):
		"""Convert first-order interaction coefficient from weight percent to mole fraction"""
		sij = 230 * eji * element_j.m / matrix.m + (1 - element_j.m / matrix.m)
		return round(sij, 2)


## main.py


import argparse


def entropy_judge (*elements: str) -> bool:
	"""

	Args:


	Returns:
		bool: 如果根据规则需要考虑过剩熵，则返回 True，否则返回 False。

	规则 (基于 C# 代码逻辑):
	1. 如果体系中含有 'O' (氧):
	   - 当 'O' 与非金属元素相互作用时，考虑过剩熵 (返回 True)。

	2. 如果体系中不含 'O'，但含有 'H' (氢) 或 'N' (氮):
	   - 不考虑过剩熵 (返回 False)。
	3. 如果体系中既不含 'O'，也不含 'H' 或 'N':
	   - 考虑过剩熵 (返回 True)。
	"""
	if not elements:
		QMessageBox.warning(None, "输入错误", "entropy_judge 函数至少需要一个元素参数。")
		return False
	
	s_set = set(elements)  # 使用集合进行快速成员检查
	
	if "O" in s_set:
		# 规则 1: 体系含 O
		# 检查 O 是否与非金属元素相互作用 (遵循 C# 的配对逻辑)
		other_elements = s_set - {"O"}
		if other_elements.intersection(Constants.non_metal_list):
			return True
		else:
			return False
	
	elif "H" in s_set or "N" in s_set:
		# 规则 2: 不含 O，但含 H 或 N
		return False
	else:
		# 规则 3: 不含 O、H、N
		
		return True

def calculate_activity (alloy_composition, solvent, solute, temperature, state, geomodel: extrap_func,
                        extra_model_name: str):
	"""
	Calculate activity and activity coefficients for a given alloy system

	Args:
		alloy_composition: String representing alloy composition (e.g., "Ni0.5Al0.5")
		solvent: Base metal (e.g., "Fe")
		solute: Solute element (e.g., "C")
		temperature: Temperature in K
		state: Phase state ("liquid" or "solid")

	Returns:
		Dictionary with calculated values
	"""
	# Create composition dictionary
	ac = ActivityCoefficient()
	if solvent in alloy_composition:
		ac.set_composition_dict(alloy_composition)
	else:
		ac.set_composition_dict(solvent + alloy_composition)
	comp_dict = ac.melts_dict
	
	# Create binary model
	binary_model = BinaryModel()
	binary_model.set_state(state)
	binary_model.set_temperature(temperature)
	
	# Calculate activity coefficients using different models
	darken_acf = ac.activity_coefficient_darken(comp_dict, solute, solvent, temperature, state,
	                                            geomodel, extra_model_name)
	
	xi = comp_dict[solute]
	darken_acf = math.exp(darken_acf) * xi
	
	wagner_act = ac.activity_coefficient_wagner(comp_dict, solvent, solute, temperature, state,
	                                            geomodel, extra_model_name)
	wagner_act = math.exp(wagner_act) * xi
	
	elloit_act = ac.activity_coefficient_elloit(comp_dict, solute, solvent, temperature, state,
	                                            geomodel, extra_model_name)
	elloit_act = math.exp(elloit_act) * xi
	
	# Prepare and return results
	results = {
		"composition": alloy_composition,
		"solvent": solvent,
		"solute": solute,
		"temperature": temperature,
		"state": state,
		"activity_darken": round(darken_acf, 3),
		"activity_wagner": round(wagner_act, 3),
		"activity_elloit": round(elloit_act, 3),
		"mole_fraction": round(xi, 3)
	}
	
	return results


def calculate_activity_coefficient (alloy_composition, solvent, solute, temperature, state, geomodel: extrap_func,
                                    extra_model_name: str):
	"""
	Calculate activity coefficients for a given alloy system

	Args:
		alloy_composition: String representing alloy composition (e.g., "Ni0.5Al0.5")
		solvent: Base metal (e.g., "Fe")
		solute: Solute element (e.g., "C")
		temperature: Temperature in K
		state: Phase state ("liquid" or "solid")

	Returns:
		Dictionary with calculated values
	"""
	# Create composition dictionary
	ac = ActivityCoefficient()
	if solvent in alloy_composition:
		ac.set_composition_dict(alloy_composition)
	else:
		ac.set_composition_dict(solvent + alloy_composition)
	comp_dict = ac.melts_dict
	
	# Create binary model
	binary_model = BinaryModel()
	binary_model.set_state(state)
	binary_model.set_temperature(temperature)
	
	# Calculate activity coefficients using different models
	darken_acf = ac.activity_coefficient_darken(comp_dict, solute, solvent, temperature, state,
	                                            geomodel, extra_model_name)
	
	wagner_acf = ac.activity_coefficient_wagner(comp_dict, solvent, solute, temperature, state,
	                                            geomodel, extra_model_name)
	
	elloit_acf = ac.activity_coefficient_elloit(comp_dict, solute, solvent, temperature, state,
	                                            geomodel, extra_model_name)
	
	# Prepare and return results
	results = {
		"composition": alloy_composition,
		"solvent": solvent,
		"solute": solute,
		"temperature": temperature,
		"state": state,
		"activity_coefficient_darken": round(darken_acf, 3),
		"activity_coefficient_wagner": round(wagner_acf, 3),
		"activity_coefficient_elloit": round(elloit_acf, 3)
	}
	
	return results


def calculate_interaction_coefficient (solvent, solute_i, solute_j, temperature, state, geomodel: extrap_func,
                                       extra_model_name: str):
	"""
	Calculate interaction coefficients for a given alloy system

	Args:
		solvent: Base metal (e.g., "Fe")
		solute_i: First solute element (e.g., "C")
		solute_j: Second solute element (e.g., "Si")
		temperature: Temperature in K
		state: Phase state ("liquid" or "solid")

	Returns:
		Dictionary with calculated values
	"""
	# Create elements
	solv = Element(solvent)
	solui = Element(solute_i)
	soluj = Element(solute_j)
	
	# Create melts object for experimental interaction parameter
	melt = Melt(solvent, solute_i, solute_j, temperature)
	
	# Create ternary melts object for calculation
	ternary = TernaryMelts(temperature, state, entropy_judge(solvent, solute_i, solute_j))
	
	# Create binary model for UEM parameters
	binary_model = BinaryModel()
	binary_model.set_state(state)
	binary_model.set_temperature(temperature)
	
	# Calculate interaction coefficient
	sij_uem1 = ternary.activity_interact_coefficient_1st(solv, solui, soluj, temperature, state, geomodel,
	                                                     extra_model_name)
	sij_uem2 = ternary.activity_interact_coefficient_1st(solv, solui, soluj, temperature, state, binary_model.UEM2,
	                                                     "UEM2-Adv")
	
	# Get experimental value if available
	if state == "liquid":
		sij_exp = melt.sji
	else:
		sij_exp = float('nan')
	
	# Prepare and return results
	results = {
		"solvent": solvent,
		"solute_i": solute_i,
		"solute_j": solute_j,
		"temperature": temperature,
		"state": state,
		"sij_uem1": round(sij_uem1, 3),
		"sij_uem2": round(sij_uem2, 3),
		"sij_experimental": sij_exp
	}
	
	return results


def calculate_second_order (solvent, solute_i, solute_j, solute_k, temperature, state, geomodel: extrap_func,
                            extra_model_name: str):
	"""
	Calculate second-order interaction coefficients

	Args:
		solvent: Base metal (e.g., "Fe")
		solute_i: First solute element (e.g., "C")
		solute_j: Second solute element (e.g., "Si")
		solute_k: Third solute element (e.g., "Mn")
		temperature: Temperature in K
		state: Phase state ("liquid" or "solid")

	Returns:
		Dictionary with calculated values
	"""
	# Create elements
	solv = Element(solvent)
	solui = Element(solute_i)
	soluj = Element(solute_j)
	soluk = Element(solute_k)
	
	# Create ternary melts object for calculation
	ternary = TernaryMelts(temperature, state, entropy_judge(solvent, solute_i, solute_j, solute_k))
	
	# Create binary model for UEM parameters
	binary_model = BinaryModel()
	binary_model.set_state(state)
	binary_model.set_temperature(temperature)
	
	# Calculate second-order coefficients
	rii = ternary.roui_ii(solv, solui, temperature, state, geomodel)
	rij = ternary.roui_ij(solv, solui, soluj, temperature, state, geomodel)
	rjj = ternary.roui_jj(solv, solui, soluj, temperature, state, geomodel)
	rjk = ternary.roui_jk(solv, solui, soluj, soluk, temperature, state, geomodel)
	
	# Prepare and return results
	results = {
		"solvent": solvent,
		"solute_i": solute_i,
		"solute_j": solute_j,
		"solute_k": solute_k,
		"temperature": temperature,
		"state": state,
		"ri_ii": round(rii, 3),
		"ri_ij": round(rij, 3),
		"ri_jj": round(rjj, 3),
		"ri_jk": round(rjk, 3)
	}
	
	return results

def main ():
	parser = argparse.ArgumentParser(description="AlloyAct - Thermodynamic calculations for alloys")
	subparsers = parser.add_subparsers(dest="command", help="Command to execute")
	binary_model = BinaryModel()
	results = calculate_activity("Fe0.70C0.03Si0.27", "Fe", "C", 1873.0, "liquid", binary_model.UEM1, 'UEM1')
	print(results)
	
	results = calculate_interaction_coefficient("Fe", "C", "Si", 1873.0, "liquid", binary_model.UEM1, 'UEM1')
	print(results)
	# Calculate activity coefficient
	results = calculate_activity_coefficient("Ni0.5Al0.3", "Fe", "Ni", 1600.0, "liquid", binary_model.UEM1, 'UEM1')
	print(results)
	
	results = calculate_second_order('Al', 'Si', 'Cu', 'Mn', 805, 'liquid', binary_model.UEM1, 'UEM1')
	
	print(results)


if __name__ == "__main__":
	main()
