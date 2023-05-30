import numpy as np


class StatorWindingResistanceProblem:
    """Problem class for calculating stator phase winding resistance
    Attributes:
        r_si: stator inner radius in [m]
        d_sp: stator pole thickness [m]
        d_st: stator tooth depth [m]
        w_st: stator tooth width [m]
        l_st: stack length [m]
        Q: number of slots
        y: slot pitch in number of slots
        z_Q: number of turns per coil
        z_C: number of coils per phase
        Kcu: slot fill factor
        Kov: winding overlength factor
        sigma_cond: conductor conductivity [Siemens/m]
        slot_area: stator slot area [m^2]

    """

    def __init__(self, r_si, d_sp, d_st, w_st, l_st, Q, y, z_Q, z_C, Kcu, Kov, sigma_cond, slot_area):
        self.r_si = r_si
        self.d_sp = d_sp
        self.d_st = d_st
        self.w_st = w_st
        self.l_st = l_st
        self.Q = Q
        self.y = y
        self.z_Q = z_Q
        self.z_C = z_C
        self.Kcu = Kcu
        self.Kov = Kov
        self.sigma_cond = sigma_cond
        self.slot_area = slot_area


class StatorWindingResistanceAnalyzer:
    def analyze(self, problem: StatorWindingResistanceProblem):
        """Calculates stator phase winding resistance (along stack and end winding)

        Args:
            problem: object of type StatorWindingResistanceProblem holding force data
        Returns:
            R_wdg: phase winding resistance [Ohm]
            R_wdg_coil_ends: phase winding resistance due to coil ends [Ohm]
            R_wdg_coil_sides: phase winding resistance due to coil sides [Ohm]
        """
        r_si = problem.r_si
        d_sp = problem.d_sp
        d_st = problem.d_st
        w_st = problem.w_st
        l_st = problem.l_st
        Q = problem.Q
        y = problem.y
        z_Q = problem.z_Q
        z_C = problem.z_C
        Kcu = problem.Kcu
        Kov = problem.Kov
        sigma_cond = problem.sigma_cond
        slot_area = problem.slot_area

        # Length between adjacent slots evaluated at median depth of slot
        tau_u = 2 * np.pi / Q * (r_si + d_sp + d_st / 2)
        # Length of end winding (one side of coil)
        l_end_wdg = 0.5 * np.pi * (tau_u + w_st) / 2 + tau_u * Kov * (y - 1)
        # Length of end winding (both sides of coil)
        l_coil_end_wdg = 2 * l_end_wdg
        # Mean length of one coil
        l_coil = 2 * l_st + l_coil_end_wdg
        # Conductor area
        cond_area = slot_area * Kcu / z_Q

        R_wdg = (l_coil * z_Q * z_C) / (sigma_cond * cond_area)
        R_wdg_coil_ends = (l_coil_end_wdg * z_Q * z_C) / (sigma_cond * cond_area)
        R_wdg_coil_sides = (2 * l_st * z_Q * z_C) / (sigma_cond * cond_area)

        return R_wdg, R_wdg_coil_ends, R_wdg_coil_sides