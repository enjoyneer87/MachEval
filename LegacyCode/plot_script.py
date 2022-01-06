import sys
import os
import pandas as pd

from datahandler import DataHandler
from data_analyzer import DataAnalyzer

sys.path.append("..")

path = os.path.abspath('')
arch_file = path + r'\opti_arch.pkl'  # specify path where saved data will reside
des_file = path + r'\opti_designer.pkl'
pop_file = path + r'\latest_pop.csv'
dh = DataHandler(arch_file, des_file)  # initialize data handler with required file paths

fitness, free_vars = dh.get_pareto_data()

da = DataAnalyzer(path)
da.plot_pareto_front(points=fitness, label=['Power Density', 'Efficiency', 'WR'])

var_label = [
             '$\delta_e$ [m]', 
             r'$\alpha_{st} [deg]$', 
             '$d_{so}$ [m]',
             '$w_{st}$ [m]',
             '$d_{st}$ [m]',
             '$d_{sy}$ [m]',
             r'$del_{dsp}$ [m]',
            ]

bp2 = (0.00275, 60, 5.43e-3, 15.09e-3, 16.94e-3, 13.54e-3, 180.0, 3.41e-3)
bounds = [
    [0.4 * bp2[0], 1.5 * bp2[0]],  # delta_e
    [0.4 * bp2[1], 1.1 * bp2[1]],  # alpha_st
    [0.4 * bp2[2], 2 * bp2[2]],  # d_so
    [0.5 * bp2[3], 2 * bp2[3]],  # w_st
    [0.5 * bp2[4], 2 * bp2[4]],  # d_st
    [0.5 * bp2[5], 2 * bp2[5]],  # d_sy
    [0, 2 * bp2[2]],  # del_dsp
]
da.plot_x_with_bounds(free_vars, var_label, bounds)
dh.get_designs()
