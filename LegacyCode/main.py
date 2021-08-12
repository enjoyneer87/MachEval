import sys

sys.path.append("..")
from copy import deepcopy

from machine_design import BSPMArchitectType1
from specifications.bspm_specification import BSPMMachineSpec

from specifications.machine_specs.bp1_machine_specs import DesignSpec
from specifications.materials.electric_steels import Arnon5
from specifications.materials.jmag_library_magnets import N40H
from specifications.materials.miscellaneous_materials import CarbonFiber, Steel, Copper, Hub, Air
from settings.bspm_settings_handler import BSPM_Settings_Handler
from analyzers.em import BSPM_EM_Analysis
from specifications.analyzer_config.em_fea_config import JMAG_FEA_Configuration

from problems.bspm_em_problem import BSPM_EM_Problem
from post_analyzers.bpsm_em_post_analyzer import BSPM_EM_PostAnalyzer
from length_scale_step import LengthScaleStep
from mach_eval import AnalysisStep, MachineDesigner, MachineEvaluator

from analyzers import structrual_analyzer as sta
from analyzers import thermal_analyzer as therm
from bspm_obj import BspmObjectives

##############################################################################
############################ Define Design ###################################
##############################################################################

# create specification object for the BSPM machine
machine_spec = BSPMMachineSpec(design_spec=DesignSpec, rotor_core=Arnon5,
                               stator_core=Arnon5, magnet=N40H, conductor=Copper,
                               shaft=Steel, air=Air, sleeve=CarbonFiber, hub=Hub)

# initialize BSPMArchitect with machine specification
arch = BSPMArchitectType1(machine_spec)
set_handler = BSPM_Settings_Handler()

bspm_designer = MachineDesigner(arch, set_handler)
# create machine variant using architect
free_var = (0.00275, 0.01141, 44.51, 5.43e-3, 9.09e-3, 16.94e-3, 13.54e-3, 180.0, 3.41e-3, 0, 3e-3,
            0.0, 0.95, 0, 0.05, 160000, 25, 55)
# set operating point for BSPM machine

design_variant = bspm_designer.create_design(free_var)
print(design_variant.machine.Z_q)
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
        if results is bool:
            raise AttributeError
        else:
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
            raise AttributeError
        else:
            state_out = deepcopy(in_state)
            state_out.conditions.airflow = results['Required Airflow']
        return state_out


thermal_step = AnalysisStep(therm.AirflowProblemDef, therm.AirflowAnalyzer, AirflowPostAnalyzer)


##############################################################################
############################ Define Windage AnalysisStep #####################
##############################################################################


class WindageLossPostAnalyzer:
    """Converts a State into a problem"""

    def get_next_state(results, in_state):
        state_out = deepcopy(in_state)
        state_out.conditions.windage_loss = results
        machine = state_out.design.machine
        state_out.conditions.efficiency = 100 * machine.mech_power / (machine.mech_power + results +
                                                                      state_out.conditions.em['rotor_iron_loss'] +
                                                                      state_out.conditions.em['stator_iron_loss'] +
                                                                      state_out.conditions.em['magnet_loss'])

        return state_out


windage_step = AnalysisStep(therm.WindageProblemDef, therm.WindageLossAnalyzer, WindageLossPostAnalyzer)

# evaluate machine design
evaluator = MachineEvaluator([struct_step, em_step, LengthScaleStep, thermal_step, windage_step])
results = evaluator.evaluate(design_variant)
objectives = BspmObjectives.get_objectives(True, results)
