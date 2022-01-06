import sys
import os
from copy import deepcopy
import pandas as pd

sys.path.append("..")

from machine_design import BSPMArchitectType2

from specifications.bspm_specification import BSPMMachineSpec
from specifications.machine_specs.bp4_spec import DesignSpec
from specifications.materials.electric_steels import Arnon5
from specifications.materials.jmag_library_magnets import N40H
from specifications.materials.miscellaneous_materials import CarbonFiber, Steel, Copper, Hub, Air
from specifications.analyzer_config.em_fea_config import JMAG_FEA_Configuration

from problems.bspm_em_problem import BSPM_EM_Problem
from post_analyzers.bpsm_em_post_analyzer import BSPM_EM_PostAnalyzer

from settings.bspmsettingshandler import BSPMSettingsHandler
from analyzers.em_5phase import BSPM_EM_Analysis
from analyzers import structrual_analyzer as sta
from analyzers import thermal_analyzer as therm

from bspm_ds import BSPMDesignSpace
from mach_eval import AnalysisStep, MachineDesigner, MachineEvaluator
from des_opt import DesignProblem, DesignOptimizationMOEAD, InvalidDesign

from datahandler import DataHandler

##############################################################################
############################ Define Design ###################################
##############################################################################

# create specification object for the BSPM machine
machine_spec = BSPMMachineSpec(design_spec=DesignSpec, rotor_core=Arnon5,
                               stator_core=Arnon5, magnet=N40H, conductor=Copper,
                               shaft=Steel, air=Air, sleeve=CarbonFiber, hub=Hub)

# initialize BSPMArchitect with machine specification
arch = BSPMArchitectType2(machine_spec)
set_handler = BSPMSettingsHandler()

bspm_designer = MachineDesigner(arch, set_handler)
##############################################################################
############################ Define Struct AnalysisStep ######################
##############################################################################
stress_limits = {'rad_sleeve': -100E6,
                 'tan_sleeve': 1300E6,
                 'rad_magnets': 0,
                 'tan_magnets': 80E6}
# spd = sta.SleeveProblemDef(design_variant)
# problem = spd.get_problem()
struct_ana = sta.SleeveAnalyzer(stress_limits)


# sleeve_dim = ana.analyze(problem)
# print(sleeve_dim)


class StructPostAnalyzer:
    """Converts a State into a problem"""

    def get_next_state(results, in_state):
        if results is False:
            raise InvalidDesign('Suitable sleeve not found')
        else:
            print('Results are ', type(results))
            machine = in_state.design.machine
            new_machine = machine.clone(machine_parameter_dict={'d_sl': results[0]})
        state_out = deepcopy(in_state)
        state_out.design.machine = new_machine
        return state_out


struct_step = AnalysisStep(sta.SleeveProblemDef, struct_ana, StructPostAnalyzer)


##############################################################################
############################ Define EM AnalysisStep ##########################
##############################################################################


class BSPM_EM_ProblemDefinition():
    """Converts a State into a problem"""

    def get_problem(state):
        problem = BSPM_EM_Problem(state.design.machine, state.design.settings)
        return problem


# initialize em analyzer class with FEA configuration
em_analysis = BSPM_EM_Analysis(JMAG_FEA_Configuration)

# define em step
em_step = AnalysisStep(BSPM_EM_ProblemDefinition, em_analysis, BSPM_EM_PostAnalyzer)


##############################################################################
############################ Define Thermal AnalysisStep #####################
##############################################################################


class AirflowPostAnalyzer:
    """Converts a State into a problem"""

    def get_next_state(results, in_state):
        if results['valid'] is False:
            raise InvalidDesign('Magnet temperature beyond limits')
        else:
            state_out = deepcopy(in_state)
            state_out.conditions.airflow = results
        return state_out


thermal_step = AnalysisStep(therm.AirflowProblemDef, therm.AirflowAnalyzer, AirflowPostAnalyzer)


##############################################################################
############################ Define Windage AnalysisStep #####################
##############################################################################


class WindageLossPostAnalyzer:
    """Converts a State into a problem"""

    def get_next_state(results, in_state):
        state_out = deepcopy(in_state)
        machine = state_out.design.machine
        eff = 100 * machine.mech_power / (machine.mech_power + results +
                                          state_out.conditions.em['rotor_iron_loss'] +
                                          state_out.conditions.em['stator_iron_loss'] +
                                          state_out.conditions.em['magnet_loss'])
        state_out.conditions.windage = {'loss': results,
                                        'efficiency': eff
                                        }
        return state_out


windage_step = AnalysisStep(therm.WindageProblemDef, therm.WindageLossAnalyzer, WindageLossPostAnalyzer)

# create evaluator
evaluator = MachineEvaluator([struct_step, em_step, thermal_step, windage_step])

# run optimization
bp2 = (0.00275, 60, 5.43e-3, 15.09e-3, 16.94e-3, 13.54e-3)
# design = bspm_designer.create_design(bp2)

# Evaluate BP2 machine alone
# results = evaluator.evaluate(design)

# set bounds for pygmo optimization problem
bounds = [
    [0.8 * bp2[0], 2.5 * bp2[0]],  # delta_e
    [0.4 * bp2[1], 1.1 * bp2[1]],  # alpha_st
    [0.2 * bp2[2], 3 * bp2[2]],  # d_so
    [0.25 * bp2[3], 2.5 * bp2[3]],  # w_st
    [0.2 * bp2[4], 1.5 * bp2[4]],  # d_st
    [0.2 * bp2[5], 1 * bp2[5]],  # d_sy
    [0, 3 * bp2[2]],  # del_dsp
]

path = os.path.abspath('')
arch_file = path + r'\opti_archive.pkl'  # specify path where saved data will reside
des_file = path + r'\opti_designer.pkl'
pop_file = path + r'\latest_pop.csv'
dh = DataHandler(arch_file, des_file)  # initialize data handler with required file paths

# archive = dh.load_from_archive()
# for data in archive:
#     print('The rotor outer radius is', data.x[1])

opt_settings = BSPMDesignSpace(3, bounds)
design_prob = DesignProblem(bspm_designer, evaluator, opt_settings, dh)
design_opt = DesignOptimizationMOEAD(design_prob)

pop_size = 78
gen_size = 10

population = design_opt.load_pop(filepath=pop_file, pop_size=pop_size)
if population is None:
    print("New population")
    population = design_opt.initial_pop(pop_size)
pop = design_opt.run_optimization(population, gen_size, pop_file)
