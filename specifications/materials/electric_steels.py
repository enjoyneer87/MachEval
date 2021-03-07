# -*- coding: utf-8 -*-
"""
Created on Sat Feb 13 19:17:41 2021

@author: Bharat
"""
import os

Arnon5 = {
    'core_material'              : 'Arnon5', 
    'core_material_density'      : 7650, # kg/m3
    'core_youngs_modulus'        : 185E9, # Pa
    'core_poission_ratio'        : .3, 
    'core_material_cost'         : 17087, # $/m3
    'core_ironloss_a'            : 1.58, 
    'core_ironloss_b'            : 1.17, 
    'core_ironloss_Kh'           : 78.94, # W/m3
    'core_ironloss_Ke'           : 0.0372, # W/m3
    'core_therm_conductivity'    : 28, # W/m-k
    'core_stacking_factor'       : 96, # percentage
    'core_bh_file'               : os.path.dirname(__file__) + '/Arnon5.BH',
    }

# os.path.abspath('')