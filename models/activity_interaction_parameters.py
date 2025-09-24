# ternary_model.py
import os
from typing import Callable

from core.constants import Constants
from core.element import Element
from core.utils import entropy_judge, get_canonical_alloy_name
from utils.DataLogger import log_contribution_coefficients
from .extrapolation_models import BinaryModel

extrap_func = Callable[[str, str, str, float, str], float]


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
    
    
    def first_derivative_qx (self, i_element: Element, j_element: Element, xi: float = 0) -> float:
        """Calculate first derivative of Q(x)
        Q(x)=A(x)B(x)/(xA(x)+(1-X)B(x))
        D(x) = xA(x)+(1-X)B(x)
        """
        
        fij = self.fab_func_contain_s(i_element, j_element, entropy_judge(i_element.name, j_element.name))
        
        
        vi = i_element.v
        vj = j_element.v
        ui = i_element.u
        uj = j_element.u
        phi_i = i_element.phi
        phi_j = j_element.phi
        delta_phi = phi_i - phi_j
        
        ax = vi * (1 + ui * delta_phi * (1 - xi)*vj/(xi*vi+(1-xi)*vj))
        bx = vj * (1 - uj * delta_phi * xi*vi/(xi*vi+(1-xi)*vj))
        dx = xi * ax + (1 - xi) * bx
        nx = ax * bx
        
        dax = ui * delta_phi * vi*(-vj*(xi*vi+(1-xi)*vj)-(1-xi)*vj*(vi-vj))/((xi*vi+(1-xi)*vj)**2)
        dbx = -uj * delta_phi * vj*(vi*(xi*vi+(1-xi)*vj)-xi*vi*(vi-vj))/((xi*vi+(1-xi)*vj)**2)
        
        ddx = ax + xi * dax - bx + (1 - xi) * dbx
        dnx = dax * bx + ax * dbx
        
        dfx = (dnx * dx - ddx * nx) / (dx * dx)
        
        return dfx*fij
    
    def second_derivative_q0 (self, i_element: Element, j_element: Element, xi=0):
        """Calculate second derivative of Q(x) at x=0"""
        fij = self.fab_func_contain_s(i_element, j_element, entropy_judge(i_element.name, j_element.name))
        
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
        fik = self.fab_func_contain_s(solvent, solutei, entropy_judge(solvent, solutei))
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
    
    #一阶活度相互作用系数，核心参数
    def activity_interact_coefficient_1st (self, solv, solui, soluj, Tem: float, state: str, extra_model: extrap_func,
                                           extra_model_name="UEM1", full_alloy_str: str = ""):
        """Calculate first-order interaction coefficient"""
        import os
        entropy_yesornot = entropy_judge(solv, solui, soluj)
        
        fij = self.fab_func_contain_s(solui, soluj, entropy_yesornot)
        fik = self.fab_func_contain_s(solv, solui, entropy_yesornot)
        fjk = self.fab_func_contain_s(solv, soluj, entropy_yesornot)
        
        
        aji_ik = extra_model(soluj.name, solui.name, solv.name, Tem, state)
        ajk_ik = extra_model(soluj.name, solv.name, solui.name, Tem, state)
        aij_jk = extra_model(solui.name, soluj.name, solv.name, Tem, state)
        aki_ij = extra_model(solv.name, solui.name, soluj.name, Tem, state)
        akj_ij = extra_model(solv.name, soluj.name, solui.name, Tem, state)
        aik_jk = extra_model(solui.name, solv.name, soluj.name, Tem, state)
        
        if aki_ij == 0 and akj_ij == 0:
            aki_ij = akj_ij = 0.5
        
        self.log_and_write_contribution_coeffs(aki_ij,akj_ij, aik_jk, aij_jk, aji_ik, ajk_ik,
    solv, solui, soluj, extra_model_name, Tem,  full_alloy_str)
        
        via = (1 + solui.u * (solui.phi - soluj.phi) * akj_ij * soluj.v /
               (aki_ij * solui.v + akj_ij * soluj.v)) * solui.v
        vja = (1 + soluj.u * (soluj.phi - solui.phi) * aki_ij * solui.v /
               (aki_ij * solui.v + akj_ij * soluj.v)) * soluj.v
        
        A_ij = fij * via * vja * (aki_ij + akj_ij) / (aki_ij * via + akj_ij * vja)
        B_ik = fik * solui.v * (1 + solui.u * (solui.phi - solv.phi))
        C_jk = fjk * soluj.v * (1 + soluj.u * (soluj.phi - solv.phi))
        
        D_ik = aji_ik * B_ik * (1 - solui.v / solv.v * (1 + 2 * solui.u * (solui.phi - solv.phi)))
        E_jk = aij_jk * C_jk * (1 - soluj.v / solv.v * (1 + 2 * soluj.u * (soluj.phi - solv.phi)))
        
        chemical_term = A_ij - C_jk - B_ik + D_ik + E_jk
        
        return 1000 * chemical_term / (Constants.R * Tem)
    
    def roui_ii (self, solv, solui, Tem: float, state: str, extra_model, extra_model_name="UEM1"):
        """Calculate second-order self-interaction coefficient ρi^ii"""
        sii = self.activity_interact_coefficient_1st(solv, solui, solui, Tem, state, extra_model, extra_model_name)
        df10 = self.first_derivative_qx(solui, solv, 0)
        df20 = self.second_derivative_q0(solui, solv, 0)
        
        rii = -sii + 1000 * (-6 * df10 + 3 * df20) / (Constants.R * Tem)
        
        return rii
    
    def roui_jj (self, solv, solui, soluj, Tem: float, state: str, extra_model: extrap_func, extra_model_name="UEM1"):
        """Calculate second-order interaction coefficient ρi^jj"""
        sjj = self.activity_interact_coefficient_1st(solv, soluj, soluj, Tem, state, extra_model, extra_model_name)
        
        aji_ik = extra_model(soluj.name, solui.name, solv.name, Tem, state)
        ajk_ik = extra_model(soluj.name, solv.name, solui.name, Tem, state)
        aij_jk = extra_model(solui.name, soluj.name, solv.name, Tem, state)
        aki_ij = extra_model(solv.name, solui.name, soluj.name, Tem, state)
        akj_ij = extra_model(solv.name, soluj.name, solui.name, Tem, state)
        aik_jk = extra_model(solui.name, solv.name, soluj.name, Tem, state)
        
        qij = -2 * aki_ij / (aki_ij + akj_ij) ** 2 * self.first_derivative_qx(solui, soluj, aki_ij / (aki_ij + akj_ij))
        qik = aji_ik * aji_ik * self.second_derivative_q0(solui, solv, 0) - 2 * aji_ik * (
                aji_ik + ajk_ik) * self.first_derivative_qx(solui, solv, 0)
        qjk = 2 * aij_jk * self.second_derivative_q0(soluj, solv, 0) - 2 * (
                2 * aij_jk + aik_jk) * self.first_derivative_qx(soluj, solv, 0)
        
        ri_jj = (-sjj + 1000 * (qij + qik + qjk) / (Constants.R * Tem))
        
        return ri_jj
    
    def roui_ij (self, solv, solui, soluj, Tem: float, state: str, extra_model: extrap_func, extra_model_name="UEM1"):
        """Calculate second-order cross-interaction coefficient ρi^ij"""
        sji = self.activity_interact_coefficient_1st(solv, solui, soluj, Tem, state, extra_model, extra_model_name)
        
        aji_ik = extra_model(soluj.name, solui.name, solv.name, Tem, state)
        ajk_ik = extra_model(soluj.name, solv.name, solui.name, Tem, state)
        aij_jk = extra_model(solui.name, soluj.name, solv.name, Tem, state)
        aki_ij = extra_model(solv.name, solui.name, soluj.name, Tem, state)
        akj_ij = extra_model(solv.name, soluj.name, solui.name, Tem, state)
        aik_jk = extra_model(solui.name, solv.name, soluj.name, Tem, state)
        
        qij = 2 * akj_ij / (akj_ij + aki_ij) ** 2 * self.first_derivative_qx(solui, soluj, aki_ij / (akj_ij + aki_ij))
        qik = 2 * aji_ik * self.second_derivative_q0(solui, solv, 0) - 2 * (
                2 * aji_ik + ajk_ik) * self.first_derivative_qx(solui, solv, 0)
        qjk = aij_jk * aij_jk * self.second_derivative_q0(soluj, solv, 0) - 2 * aij_jk * (
                aij_jk + aik_jk) * self.first_derivative_qx(soluj, solv, 0)
        
        return (-sji + 1000 * (qij + qik + qjk) / (Constants.R * Tem))
    
    def roui_jk (self, matrix, i, j, k, Tem: float, state: str, extra_model: extrap_func, extra_model_name="UEM1"):
        """Calculate cross-interaction parameter, the influence of components j,k on i"""
        skj = self.activity_interact_coefficient_1st(matrix, j, k, Tem, state, extra_model, extra_model_name)
        
        amj_ij = extra_model(matrix.name, j.name, i.name, Tem, state)
        ami_ij = extra_model(matrix.name, i.name, j.name, Tem, state)
        aki_ij = extra_model(k.name, i.name, j.name, Tem, state)
        akj_ij = extra_model(k.name, j.name, i.name, Tem, state)
        
        amk_ik = extra_model(matrix.name, k.name, i.name, Tem, state)
        ami_ik = extra_model(matrix.name, i.name, k.name, Tem, state)
        aji_ik = extra_model(j.name, i.name, k.name, Tem, state)
        ajk_ik = extra_model(j.name, k.name, i.name, Tem, state)
        
        aji_im = extra_model(j.name, i.name, matrix.name, Tem, state)
        ajm_im = extra_model(j.name, matrix.name, i.name, Tem, state)
        aki_im = extra_model(k.name, i.name, matrix.name, Tem, state)
        akm_im = extra_model(k.name, matrix.name, i.name, Tem, state)
        
        amk_jk = extra_model(matrix.name, k.name, j.name, Tem, state)
        amj_jk = extra_model(matrix.name, j.name, k.name, Tem, state)
        aik_jk = extra_model(i.name, k.name, j.name, Tem, state)
        aij_jk = extra_model(i.name, j.name, k.name, Tem, state)
        
        aij_jm = extra_model(i.name, j.name, matrix.name, Tem, state)
        aim_jm = extra_model(i.name, matrix.name, j.name, Tem, state)
        akj_jm = extra_model(k.name, j.name, matrix.name, Tem, state)
        akm_jm = extra_model(k.name, matrix.name, j.name, Tem, state)
        
        aik_km = extra_model(i.name, k.name, matrix.name, Tem, state)
        aim_km = extra_model(i.name, matrix.name, k.name, Tem, state)
        ajk_km = extra_model(j.name, k.name, matrix.name, Tem, state)
        ajm_km = extra_model(j.name, matrix.name, k.name, Tem, state)
        
        dfij = self.first_derivative_qx(i, j, ami_ij / (ami_ij + amj_ij))
        dfik = self.first_derivative_qx(i, k, ami_ik / (ami_ik + amk_ik))
        
        qij = (amj_ij * aki_ij - ami_ij * akj_ij) / (ami_ij + amj_ij) ** 2 * dfij
        qik = (amk_ik * aji_ik - ami_ik * ajk_ik) / (ami_ik + amk_ik) ** 2 * dfik
        
        dfim = self.first_derivative_qx(i, matrix, 0)
        ddfim = self.second_derivative_q0(i, matrix, 0)
        
        qim = aji_im * aki_im * ddfim - (aji_im * akm_im + aki_im * ajm_im + 2 * aji_im * aki_im) * dfim
        
        dfjk = self.first_derivative_qx(j, k, amj_jk / (amj_jk + amk_jk))
        
        qjk = (amk_jk * aij_jk - amj_jk * aik_jk) / (amj_jk + amk_jk) ** 2 * dfjk
        
        dfjm = self.first_derivative_qx(j, matrix, 0)
        ddfjm = self.second_derivative_q0(j, matrix, 0)
        qjm = aij_jm * akj_jm * ddfjm - (aij_jm * akm_jm + akj_jm * aim_jm + 2 * aij_jm * akj_jm) * dfjm
        
        dfkm = self.first_derivative_qx(k, matrix, 0)
        ddfkm = self.second_derivative_q0(k, matrix, 0)
        qkm = aik_km * ajk_km * ddfkm - (aik_km * ajm_km + ajk_km * aim_km + 2 * aik_km * ajk_km) * dfkm
        
        return 1000 * (qij + qik + qim + qjk + qjm + qkm) / (Constants.R * Tem) - skj
    
    
    #打印贡献系数和日志记录
    def log_and_write_contribution_coeffs (self,
            aki_ij: float, akj_ij: float, aik_jk: float, aij_jk: float,
            aji_ik: float, ajk_ik: float, solv: Element, solui: Element, soluj: Element,
            extra_model_name: str, Tem: float, full_alloy_str: str = "" ):
        """
        处理、过滤并记录贡献系数。

        这个函数会执行以下操作:
        1. 确保日志文件目录存在。
        2. 对 aki_ij 和 akj_ij 进行默认值处理。
        3. 只在体系组元数大于等于3时才记录日志。
        4. 构造数据并调用日志函数。

        参数:
        aki_ij, akj_ij, ...: 贡献系数值。
        solv, solui, soluj: 代表溶剂和溶质的 Element 对象。
        extra_model_name: 外推模型的名称。
        Tem: 温度 (K)。
        full_alloy_str: 完整的合金成分字符串 (可选)。
        """
        # 1. 确保日志文件目录存在
        # (这部分可以放在函数外部的初始化代码中，以避免重复执行)
        current_script_path = os.path.abspath(__file__)
        models_dir = os.path.dirname(current_script_path)
        project_root = os.path.dirname(models_dir)
        file_path = os.path.join(project_root, "results", "Contribution Coefficient")
        os.makedirs(file_path, exist_ok=True)
        
       
        # 2. 过滤条件：只在体系组元数大于等于3时才记录日志
        system_context_for_check = full_alloy_str if full_alloy_str else f"{solv.name}-{solui.name}-{soluj.name}"
        canonical_name = get_canonical_alloy_name(system_context_for_check)
        element_count = len(canonical_name.split('-'))
        
        if element_count >= 3:
            # 准备日志所需的数据
            ternary_system_str = f"{solv.name}-{solui.name}-{soluj.name}"
            
            contribution_data_for_log = {
                f"{solui.name}-{soluj.name}": {
                    f"k={solv.name}, i={solui.name}": aki_ij,
                    f"k={solv.name}, j={soluj.name}": akj_ij
                },
                f"{solv.name}-{soluj.name}": {
                    f"i={solui.name}, k={solv.name}": aik_jk,
                    f"i={solui.name}, j={soluj.name}": aij_jk
                },
                f"{solv.name}-{solui.name}": {
                    f"j={soluj.name}, i={solui.name}": aji_ik,
                    f"j={soluj.name}, k={solv.name}": ajk_ik
                }
            }
            
            # 调用日志函数 (假设 log_contribution_coefficients 已在作用域内)
            log_contribution_coefficients(
                    ternary_system=ternary_system_str,
                    model_name=extra_model_name,
                    temperature=Tem,
                    contribution_data=contribution_data_for_log,
                    full_alloy_context=full_alloy_str
            )

