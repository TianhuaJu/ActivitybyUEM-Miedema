# ternary_model.py

import math
from core.constants import Constants
from core.element import Element
from core.utils import entropy_judge
from typing import Callable
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
        
        fij = self.fab_func_contain_s(i_element, j_element, entropy_judge(i_element.name, j_element.name))
        
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
    
    def activity_interact_coefficient_1st (self, solv, solui, soluj, Tem: float, state: str, geo_model: extrap_func,
                                           geo_model_name="UEM1"):
        """Calculate first-order interaction coefficient"""
        import os
        entropy_yesornot = entropy_judge(solv, solui, soluj)
        fij = self.fab_func_contain_s(solui, soluj, entropy_yesornot)
        fik = self.fab_func_contain_s(solv, solui, entropy_yesornot)
        fjk = self.fab_func_contain_s(solv, soluj, entropy_yesornot)
        
        
        aji_ik = geo_model(soluj.name, solui.name, solv.name, Tem, state)
        ajk_ik = geo_model(soluj.name, solv.name, solui.name, Tem, state)
        aij_jk = geo_model(solui.name, soluj.name, solv.name, Tem, state)
        aki_ij = geo_model(solv.name, solui.name, soluj.name, Tem, state)
        akj_ij = geo_model(solv.name, soluj.name, solui.name, Tem, state)
        aik_jk = geo_model(solui.name, solv.name, soluj.name, Tem, state)
        
        current_script_path = os.path.abspath(__file__)
        models_dir = os.path.dirname(current_script_path)
        project_root = os.path.dirname(models_dir)
        file_path = os.path.join(project_root, "results", "Contribution Coefficient")
        os.makedirs(file_path, exist_ok=True)
        
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
        
        qij = 2 * akj_ij / (akj_ij + aki_ij) ** 2 * self.first_derivative_qx(solui, soluj, aki_ij / (akj_ij + aki_ij))
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

