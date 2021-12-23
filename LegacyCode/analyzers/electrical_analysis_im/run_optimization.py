Help = r'''Steps for adding a new slot pole combination
1. Update machine_specifications.json
2. Run winding_layout_derivation_ismb2020.py to get a new stator winding layout and paste the code into winding_layout.py
3. Run Pole-specific_winding_with_neutral_plate_the_design_table_generator.py to get a new rotor winding layout and paste the code into winding_layout.py
4. Update this file with new "select_spec".
'''

# A. select FEA setting
select_fea_config_dict = "#019 JMAG IM Nine Variables"
# select_fea_config_dict = "#0195 JMAG IM Nine Variables | 100% Torque"
# select_fea_config_dict = "#0196 JMAG IM Nine Variables | 80% Torque"

# B. select design specification
# select_spec = "IM Q24p1y9 A"
# select_spec = "IM Q24p1y9 Qr32"
# select_spec = "IM Q24p2y6 Qr32"
# select_spec = "IM Q24p2y6 Qr16"

# select_spec = "IM Q36p3y5ps2 Qr20-FSW Round Bar"
# select_spec = "IM Q36p3y5ps2 Qr24-ISW Round Bar"

# select_spec = "IM Q36p3y5ps2 Qr20-FSW Round Bar Separate Winding"
# select_spec = "IM Q36p3y5ps2 Qr24-ISW Round Bar Separate Winding"

# select_spec = "IM Q24p1y9 Qr14 Round Bar"
# select_spec = "IM Q24p1y9 Qr16 Round Bar"

# select_spec = "IM p2ps3Qs18y4 Qr30-FSW Round Bar EquivDoubleLayer"

# Dec. 11, 2020, Add a new slot-pole combination for p=2 and ps=3 motor.
# select_spec = "IM p2ps3Qs24y5 Qr18 Round Bar EquivDoubleLayer" # 这个配置的OC值非常大，基本上是废物


# # to test the Qr30ps3 rotor circuit and see if it induces current under field without/with one pole pair component.
# select_spec = "IM Q36p3y5ps2 Qr30-FSW Round Bar EquivDoubleLayer TEST"
# select_spec = "IM Q24p1y9 Qr30-FSW Round Bar EquivDoubleLayer TEST"

# p3ps4 design
# select_spec = "IM Q36p3y5 ps4 Qr20 Round Bar"
select_spec = "IM Q36p3y5 ps4 Qr16 Round Bar"
select_spec = "IM Q18p3y3 ps4 Qr12 Round Bar"

# TEC-ISMB-2021: compare sc and ps rotor
# select_spec = "IM Q24p1y9 Qr16 Round Bar SC Rotor"



# C. decide output directory 20210302
import os
data_folder_name = os.path.realpath(f'{os.path.dirname(__file__)}/../_TEC_ISMB_2021_IM') + '/' + select_spec.replace(' ', '_') + '/'

# path_to_archive = r"D:\DrH\[00]GetWorking\36 TIA_IEMDC_ECCE-Bearingless_Induction\archive-p2019_tia_iemdc_ecce_bearingless_induction\run#550/"
# path_to_archive = path_to_archive + select_spec.replace(' ', '_') + '/'

import main_utility
output_dir, spec_input_dict, fea_config_dict = main_utility.load_settings(select_spec, select_fea_config_dict, data_folder_name)
fea_config_dict["designer.Show"] = False


''' D. 
ACMDM: AC Machine Design in Modules:
    [1] Winding Part
    [2] Initial Design Part
    [3] Evaluation Part
    [4] Optimization Part
    [5] Report Part
'''

#~*~*~*~*~*~*~*~*~*~*~*~*~*~*~*~*~*~*~*~*~*~*~*~*~*~*~*~*~*~*~*~
# '[1] Winding Part (Can be skipped)'
# Use winding_layout_derivation.py to derive windings defined in class winding_layout_v2 during choosing winding phase.
#~*~*~*~*~*~*~*~*~*~*~*~*~*~*~*~*~*~*~*~*~*~*~*~*~*~*~*~*~*~*~*~
if False:
    import winding_layout
    # wily = winding_layout.winding_layout_v2(DPNV_or_SEPA=False, Qs=24, p=2, ps=1)
    # wily = winding_layout.winding_layout_v2(DPNV_or_SEPA=True, Qs=24, p=2, ps=1, coil_pitch_y=6)
    # wily = winding_layout.winding_layout_v2(DPNV_or_SEPA=True, Qs=24, p=1, ps=2, coil_pitch_y=9)
    wily = winding_layout.winding_layout_v2(DPNV_or_SEPA=spec_input_dict['DPNV_or_SEPA'],
                                            Qs=spec_input_dict['Qs'],
                                            p=spec_input_dict['p'],
                                            ps=spec_input_dict['ps'],
                                            coil_pitch_y=spec_input_dict['coil_pitch_y'])

    '[1.1] Winding in the slot'
    if True:
        import math
        import PyX_Utility
        def draw_winding_in_the_slot(u, Qs, list_layer_phases, list_layer_signs, text=''):

            for i in range(Qs):
                radius_slot = 30
                LRIF = layer_radius_incremental_factor = 0.1
                angular_loc = 2*math.pi/Qs*i
                x_slot = radius_slot*math.cos(angular_loc)
                y_slot = radius_slot*math.sin(angular_loc)
                u.pyx_text(   [ x_slot*(1.0+LRIF),
                                y_slot*(1.0+LRIF)],
                              str(i+1) )
                u.pyx_marker( [ x_slot*(1.0+2*LRIF),
                                y_slot*(1.0+2*LRIF)], size=0.05)

                radius_tooth = radius_slot + 5
                x_tooth = radius_tooth*math.cos(angular_loc + math.pi/Qs)
                y_tooth = radius_tooth*math.sin(angular_loc + math.pi/Qs)
                radius_airgap = radius_slot - 5
                x_toothtip = radius_airgap*math.cos(angular_loc+math.pi/Qs)
                y_toothtip = radius_airgap*math.sin(angular_loc+math.pi/Qs)
                u.pyx_line([x_toothtip, y_toothtip], [x_tooth, y_tooth])

                for ind, phases in enumerate(list_layer_phases):
                    signs = list_layer_signs[ind]
                    u.pyx_text(   [ x_slot*(1.0-ind*LRIF),
                                    y_slot*(1.0-ind*LRIF)],
                                  '$' + phases[i].lower() + '^' + signs[i]
                                  + '$' )

            u.pyx_text([0,0], (r'DPNV Winding' if wily.DPNV_or_SEPA else r'Separate Winding') + text)

        u = PyX_Utility.PyX_Utility()
        draw_winding_in_the_slot(u, wily.Qs, wily.list_layer_motor_phases, wily.list_layer_motor_signs, text=' Motor Mode' )
        u.cvs.writePDFfile(output_dir + 'pyx_output_M')

        u = PyX_Utility.PyX_Utility()
        draw_winding_in_the_slot(u, wily.Qs, wily.list_layer_suspension_phases, wily.list_layer_suspension_signs, text=' Suspension Mode' )
        u.cvs.writePDFfile(output_dir + 'pyx_output_S')
        # u.cvs.writeSVGfile(r'C:\Users\horyc\Desktop\pyx_output')
        # u.cvs.writeEPSfile(r'C:\Users\horyc\Desktop\pyx_output')
        # quit()
        print('Write to:', output_dir + 'pyx_output_S.pdf')

    '[1.2] Winding function / Current Linkage waveform'
    if False:
        from pylab import plt, np
        zQ = 100 # number of conductors/turns per slot (Assume to be 100 for now)
        turns_per_layer = zQ / wily.number_winding_layer
        U_phase = winding_layout.PhaseWinding(wily.Qs, wily.m, turns_per_layer, wily.ox_distribution_phase_U)
        U_phase.plotFuncObj(U_phase.winding_func)
        U_phase.fig_plotFuncObj.savefig(output_dir + 'winding_function.png')
        U_phase.plot2piFft(U_phase.winding_func, Fs=1/(2*np.pi/3600), L=32000*2**4) # 在2pi的周期内取360个点
        U_phase.fig_plot2piFft.savefig(output_dir + 'winding_function_DFT.png')
        plt.show()

    quit()

#~*~*~*~*~*~*~*~*~*~*~*~*~*~*~*~*~*~*~*~*~*~*~*~*~*~*~*~*~*~*~*~
# '[2] Initial Design Part'
#~*~*~*~*~*~*~*~*~*~*~*~*~*~*~*~*~*~*~*~*~*~*~*~*~*~*~*~*~*~*~*~

# [2.1] Attain spec_derive_dict
import pyrhonen_procedure_as_function
spec = pyrhonen_procedure_as_function.desgin_specification(**spec_input_dict)
# for k,v in spec_input_dict.items():
#     print(k+':', v)
# for k,v in spec.spec_derive_dict.items():
#     print(k+':', v)
# spec.show()
# quit()

# [2.2] Attain spec_geometry_dict
print('Build ACM template...')
if 'IM' in select_spec:
    print(spec.build_name())
    spec.bool_bad_specifications = spec.pyrhonen_procedure()
    # for k,v in spec.spec_geometry_dict.items():
    #     print(k+':', v)

    # rebuild prototype
    if False:
        print(spec.build_name()) # rebuild for new guess air gap flux density # TODO：自动修正转子电流密度的设置值？
        spec.spec_geometry_dict.update({
                                    'Qs': 24,
                                    'Qr': 16,
                                    'Radius_OuterStatorYoke': 75, # mm
                                    'Radius_InnerStatorYoke': 59.20540012659264,
                                    'Length_AirGap': 2.649964958084005,
                                    'Radius_OuterRotor': 31.8107,
                                    'Radius_Shaft': 7.515, # mm
                                    'Length_HeadNeckRotorSlot': 0.5,
                                    'Radius_of_RotorSlot': 2.5082500000000003,
                                    'Location_RotorBarCenter': 28.80245,
                                    'Width_RotorSlotOpen': 0.867331038602591,
                                    'Radius_of_RotorSlot2': 0.8096377782265239,
                                    'Location_RotorBarCenter2': 19.171743466485857,
                                    'Angle_StatorSlotOpen': 4,
                                    'Width_StatorTeethBody': 5.38242649274919,
                                    'Width_StatorTeethHeadThickness': 2.6071839703305173,
                                    'Width_StatorTeethNeck': 1.3035919851652586,
                                    'DriveW_poles': 2,
                                    'DriveW_zQ': 32,
                                    'DriveW_Rs': 0.41,
                                    'DriveW_CurrentAmp': 18.4, # about 13 Arms
                                    'DriveW_Freq': 500,
                                    'stack_length': 50,
                                    # 'area_stator_slot_Sus': 0.0002110198352301264,
                                    # 'area_rotor_slot_Sur': 7.304532757965913e-05,
                                    'minimum__area_rotor_slot_Sur': 5.9349328658473047e-05,
                                    'rotor_tooth_flux_density_B_dr': 1.5,
                                    'stator_tooth_flux_density_B_ds': 1.4,
                                    'Jr': 6500000.0,
                                    'BeariW_Poles': 4,
                                    # 'delta': 1.4367874248827988,
                                    # 'w_st': 6.99845908997596,
                                    # 'w_rt': 9.793842725966343,
                                    # 'theta_so': 7.5,
                                    # 'w_ro': 1.8750000000000002,
                                    # 'd_so': 1.0,
                                    # 'd_ro': 1.0,
                                    # 'd_st': 22.800657296866607,
                                    # 'd_sy': 31.72492200478913
                                    })
        Radius_OuterRotor = spec.spec_geometry_dict['Radius_OuterRotor']
        Length_HeadNeckRotorSlot = spec.spec_geometry_dict['Length_HeadNeckRotorSlot']
        Radius_of_RotorSlot = spec.spec_geometry_dict['Radius_of_RotorSlot']
        Qr = spec.spec_geometry_dict['Qr']
        from pylab import np
        rotor_tooth_width_b_dr = 1e-3 * ( 2*np.pi*(Radius_OuterRotor - Length_HeadNeckRotorSlot)  - Radius_of_RotorSlot * (2*Qr+2*np.pi) ) / Qr
            # print(Radius_of_RotorSlot, rotor_tooth_width_b_dr)
            # Radius_of_RotorSlot = 1e3 * (2*np.pi*(Radius_OuterRotor - Length_HeadNeckRotorSlot)*1e-3 - rotor_tooth_width_b_dr*Qr) / (2*Qr+2*np.pi) # see radius_rotor_slot_formula.wmf
            # print(Radius_of_RotorSlot, rotor_tooth_width_b_dr)
            # quit()
        spec.spec_geometry_dict.update({'rotor_tooth_width_b_dr': rotor_tooth_width_b_dr})
        print('::: rotor_tooth_width_b_dr =', rotor_tooth_width_b_dr)

    # spec.show()
    # quit()

    import population
                        # load initial design using the obsolete class bearingless_induction_motor_design
    spec.acm_template = population.bearingless_induction_motor_design(spec_input_dict, spec.spec_derive_dict, spec.spec_geometry_dict, fea_config_dict)
    # spec.acm_template.show()

    import utility_json
    utility_json.to_json(obj=spec.acm_template, fname='2019-blim-prototype', suffix='-DesignTemplate')
    # quit()

    # spec.acm_template = population.bearingless_induction_motor_design.reproduce_the_problematic_design('./shitty_design_prototype.txt')
    # spec.acm_template.show()

elif 'PMSM' in select_spec:
    spec.acm_template = spec.build_pmsm_template(fea_config_dict, spec_input_dict, im_template=None)

import acm_designer
global ad
ad = acm_designer.acm_designer(fea_config_dict, spec_input_dict, spec, output_dir, select_spec, select_fea_config_dict)
if False:
    if 'Y730' in fea_config_dict['pc_name']:
        ad.build_oneReport() # require LaTeX
        # ad.talk_to_mysql_database() # require MySQL




# for k,v in fea_config_dict.items():
#     print(k, v)
# quit()

#~*~*~*~*~*~*~*~*~*~*~*~*~*~*~*~*~*~*~*~*~*~*~*~*~*~*~*~*~*~*~*~
# '[3] Evaluation Part (Can be skipped)'
#~*~*~*~*~*~*~*~*~*~*~*~*~*~*~*~*~*~*~*~*~*~*~*~*~*~*~*~*~*~*~*~
if False:
    # build x_denorm for the template design
    x_denorm = spec.acm_template.build_x_denorm()

    # import json
    # with open('__'+'2019-blim-prototype'+'-DesignTemplate'+'.json', 'w') as f:
    #     json.dump(spec.acm_template.__dict__, f, indent=4)
    # quit()

    # evaluate design (with json output)
    cost_function, f1, f2, f3, FRW, \
        normalized_torque_ripple, \
        normalized_force_error_magnitude, \
        force_error_angle = ad.evaluate_design_json_wrapper(ad.spec.acm_template, x_denorm)

    print(cost_function, f1, f2, f3, FRW, \
    normalized_torque_ripple, \
    normalized_force_error_magnitude, \
    force_error_angle)

    print('Check several things: 1. the winding initial excitation angle; 2. the rotor d-axis initial position should be orthoganal to winding excitation field.')

    quit()

#~*~*~*~*~*~*~*~*~*~*~*~*~*~*~*~*~*~*~*~*~*~*~*~*~*~*~*~*~*~*~*~
# '[4] Optimization Part' Multi-Objective Optimization
#~*~*~*~*~*~*~*~*~*~*~*~*~*~*~*~*~*~*~*~*~*~*~*~*~*~*~*~*~*~*~*~
ad.init_logger(prefix='acmdm')

# [4.1] Get bounds
if 'IM' in select_spec:
    ad.bounds_denorm = spec.get_im_classic_bounds(which_filter=fea_config_dict['which_filter'])
    ad.bound_filter  = spec.bound_filter
    otnb = spec.original_template_neighbor_bounds
elif 'PMSM' in select_spec:
    ad.bounds_denorm = spec.acm_template.get_classic_bounds(which_filter=fea_config_dict['which_filter'])
    ad.bound_filter  = spec.acm_template.bound_filter
    otnb = spec.acm_template.original_template_neighbor_bounds
print('---------------------\nBounds: (if there are two bounds within one line, they should be the same)')
idx_ad = 0
for idx, f in enumerate(ad.bound_filter):
    if f == True:
        print(idx, f, '[%g,%g]'%tuple(otnb[idx]), '[%g,%g]'%tuple(ad.bounds_denorm[idx_ad]))
        idx_ad += 1
    else:
        print(idx, f, '[%g,%g]'%tuple(otnb[idx]))

# debug
# print(spec.acm_template.Radius_OuterRotor)
# x_denorm = spec.acm_template.build_x_denorm()
# for el in x_denorm:
#     print(el)
# quit()

if fea_config_dict['bool_post_processing'] == True: # use the new script file instead: main_post_processing_pm.py
    import one_script_pm_post_processing
    one_script_pm_post_processing.post_processing(ad, fea_config_dict)
    quit()

# [4.3] MOO
from acm_designer import get_bad_fintess_values
import logging
import utility_moo
import pygmo as pg
ad.counter_fitness_called = 0
ad.counter_fitness_return = 0
__builtins__.ad = ad # share global variable between modules # https://stackoverflow.com/questions/142545/how-to-make-a-cross-module-variable
if 'IM' in select_spec:
    import Problem_BearinglessInductionDesign # must import this after __builtins__.ad = ad
    get_prob_and_popsize = Problem_BearinglessInductionDesign.get_prob_and_popsize
elif 'PMSM' in select_spec:
    import Problem_BearinglessSynchronousDesign # must import this after __builtins__.ad = ad
    get_prob_and_popsize = Problem_BearinglessSynchronousDesign.get_prob_and_popsize
print(__builtins__.ad)

################################################################
# MOO Step 1:
#   Create UserDefinedProblem and create population
#   The magic method __init__ cannot be fined for UDP class
################################################################
# [4.3.1] Basic setup
_, prob, popsize = get_prob_and_popsize()

print('-'*40 + '\nPop size is', popsize)

# [4.3.2] Generate the pop
if False:
    pop = pg.population(prob, size=popsize)
# Add Restarting Feature when generating pop
else:
    from main_utility import get_sorted_swarm_data_from_the_archive
    # def get_sorted_swarm_data_from_the_archive(path_to_archive):
    #     output_dir_backup = ad.solver.output_dir
    #     ad.solver.output_dir = ad.solver.fea_config_dict['dir.parent'] + path_to_archive
    #     number_of_chromosome = ad.solver.read_swarm_data(ad.bound_filter)
    #     ad.solver.output_dir = output_dir_backup

    #     ad.flag_do_not_evaluate_when_init_pop = True
    #     pop = pg.population(prob, size=popsize)
    #     swarm_data_on_pareto_front = utility_moo.learn_about_the_archive(prob, ad.solver.swarm_data, popsize, ad.solver.fea_config_dict, bool_plot_and_show=False)
    #     ad.flag_do_not_evaluate_when_init_pop = False
    #     return swarm_data_on_pareto_front

    # 检查swarm_data.txt，如果有至少一个数据，返回就不是None。
    print('Check swarm_data.txt...')
    number_of_chromosome = ad.solver.read_swarm_data(ad.bound_filter)

    # case 1: swarm_data.txt exists
    if number_of_chromosome is not None:

        number_of_finished_iterations                       = number_of_chromosome // popsize
        number_of_finished_chromosome_in_current_generation = number_of_chromosome % popsize

        # 如果刚好整除，把余数0改为popsize
        if number_of_finished_chromosome_in_current_generation == 0:
            number_of_finished_chromosome_in_current_generation = popsize
            print(f'\tThere are {number_of_chromosome} chromosomes found in swarm_data.txt.')
            print('\tWhat is the odds! The script just stopped when the evaluation of the whole pop is finished.')
            print('\tSet number_of_finished_chromosome_in_current_generation to popsize %d'%(number_of_finished_chromosome_in_current_generation))

        print('This is a restart of '+ fea_config_dict['run_folder'][:-1])
        print('\tNumber of finished iterations is %d'%(number_of_finished_iterations))
        # print('This means the initialization of the population class is interrupted. So the pop in swarm_data.txt is used as the survivor.')

        # swarm_survivor feature. Not sure if this is needed anymore...
        if True:
            # 继续从swarm_survivor.txt中读取数据，注意，survivor总是是完整的一代的，除非popsize被修改了。
            print('\tCheck swarm_survivor.txt...', end='')
            ad.solver.survivor = ad.solver.read_swarm_survivor(popsize)

            # 如果发现ad.solver.survivor是None，那就说明是初始化pop的时候被中断了，此时就用swarm_data来生成pop。
            if ad.solver.survivor is not None:
                print('Found survivor!\nRestart the optimization based on the swarm_survivor.txt.')

                if len(ad.solver.survivor) != popsize:
                    print('popsize is reduced') # 如果popsize增大了，read_swarm_survivor(popsize)就会报错了，因为-----不能被split后转为float
                    raise Exception('This is a feature not tested. However, you can cheat to change popsize by manually modify swarm_data.txt or swarm_survivor.txt.')
            else:
                print('Gotta make do with swarm_data to generate survivor.')

        # 这些计数器的值永远都是评估过的chromosome的个数。
        ad.counter_fitness_called = ad.counter_fitness_return = number_of_chromosome
        print('ad.counter_fitness_called = ad.counter_fitness_return = number_of_chromosome = %d'%(number_of_chromosome))

        # case 1-A: swarm_data.txt exists and this is a re-evaluation run using the existing csv files (比如我们修改了计算铜损的代码，那就必须借助已有的有限元结果重新生成swarm_data.txt)
        if fea_config_dict['bool_re_evaluate']:
            ad.counter_fitness_called = ad.counter_fitness_return = 0

        # 禁止在初始化pop时运行有限元
        ad.flag_do_not_evaluate_when_init_pop = True
        # 初始化population，如果ad.flag_do_not_evaluate_when_init_pop是False，那么就说明是 new run，否则，整代个体的fitness都是[0,0,0]。
        pop = pg.population(prob, size=popsize)
        if fea_config_dict['bool_re_evaluate_wo_csv']:
            swarm_data_backup = ad.solver.swarm_data[::] # This is going to be over-written in next line
            swarm_data_on_pareto_front, _ = get_sorted_swarm_data_from_the_archive(prob, popsize, path_to_archive, bool_absolute_path=True)
            ad.flag_do_not_evaluate_when_init_pop = True # When you call function get_sorted_swarm_data_from_the_archive, flag_do_not_evaluate_when_init_pop is set to False at the end. Sometimes we do not want this, for example, restarting restart re-evaluation without csv.
            ad.solver.swarm_data = swarm_data_backup
            for i in range(popsize):
                # print(path_to_archive, ':', swarm_data_on_pareto_front[i][::-1])
                pop.set_xf(i, swarm_data_on_pareto_front[i][:-3], swarm_data_on_pareto_front[i][-3:])
            print('Old pop:')
            print(pop)

        # Restarting feature related codes
        # 如果整代个体的fitness都是[0,0,0]，那就需要调用set_xf，把txt文件中的数据写入pop。如果发现数据的个数不够，那就调用set_x()来产生数据，形成初代个体。
        if ad.flag_do_not_evaluate_when_init_pop == True:
            pop_array = pop.get_x()
            if number_of_chromosome <= popsize:
                for i in range(popsize):
                    if i < number_of_chromosome: #number_of_finished_chromosome_in_current_generation:
                        pop.set_xf(i, ad.solver.swarm_data[i][:-3], ad.solver.swarm_data[i][-3:])
                    else:
                        print('Set "ad.flag_do_not_evaluate_when_init_pop" to False...')
                        ad.flag_do_not_evaluate_when_init_pop = False
                        print('Calling pop.set_x()---this is a restart for individual#%d during pop initialization.'%(i))
                        print(i, 'get_fevals:', prob.get_fevals())
                        pop.set_x(i, pop_array[i]) # evaluate this guy

            else:
                # 新办法，直接从swarm_data.txt（相当于archive）中判断出当前最棒的群体
                swarm_data_on_pareto_front = utility_moo.learn_about_the_archive(prob, ad.solver.swarm_data, popsize, fea_config_dict)
                # print(swarm_data_on_pareto_front)
                for i in range(popsize):
                    pop.set_xf(i, swarm_data_on_pareto_front[i][:-3], swarm_data_on_pareto_front[i][-3:])

            # 必须放到这个if的最后，因为在 learn_about_the_archive 中是有初始化一个 pop_archive 的，会调用fitness方法。
            ad.flag_do_not_evaluate_when_init_pop = False

    # case 2: swarm_data.txt does not exist
    else:
        number_of_finished_chromosome_in_current_generation = None
        number_of_finished_iterations = 0 # 实际上跑起来它不是零，而是一，因为我们认为初始化的一代也是一代。或者，我们定义number_of_finished_iterations = number_of_chromosome // popsize

        # case 2-A: swarm_data.txt does not exist and this is a whole new run.
        if not fea_config_dict['bool_re_evaluate_wo_csv']:
            print('Nothing exists in swarm_data.txt.\nThis is a whole new run.')
            ad.flag_do_not_evaluate_when_init_pop = False
            pop = pg.population(prob, size=popsize)

        # case 2-B: swarm_data.txt does not exist and this is a re-evalation run (without csv)
        else:
            print('Nothing exists in swarm_data.txt.\nRe-start from %s'%(path_to_archive))
            ad.flag_do_not_evaluate_when_init_pop = True
            pop = pg.population(prob, size=popsize)
            # read in swarm data from another older run's archive and start from it!
            swarm_data_on_pareto_front, _ = get_sorted_swarm_data_from_the_archive(prob, popsize, path_to_archive, bool_absolute_path=True)
            ad.flag_do_not_evaluate_when_init_pop = False
            for i in range(popsize):
                print(path_to_archive, ':', swarm_data_on_pareto_front[i][::-1])
                pop.set_x(i, swarm_data_on_pareto_front[i][:-3]) # re-evaluate this guy

    # this flag must be false to move on
    ad.flag_do_not_evaluate_when_init_pop = False

print('-'*40, '\nPop is initialized:\n', pop)
hv = pg.hypervolume(pop)
quality_measure = hv.compute(ref_point=get_bad_fintess_values(machine_type='PMSM', ref=True)) # ref_point must be dominated by the pop's pareto front
print('quality_measure: %g'%(quality_measure))
# raise KeyboardInterrupt

# 初始化以后，pop.problem.get_fevals()就是popsize，但是如果大于popsize，说明“pop.set_x(i, pop_array[i]) # evaluate this guy”被调用了，说明还没输出过 survivors 数据，那么就写一下。
if pop.problem.get_fevals() > popsize:
    print('Write survivors.')
    ad.solver.write_swarm_survivor(pop, ad.counter_fitness_return)


################################################################
# MOO Step 2:
#   Select algorithm (another option is pg.nsga2())
################################################################
# [4.3.3] Selecting algorithm
# Don't forget to change neighbours to be below popsize (default is 20) decomposition="bi"
algo = pg.algorithm(pg.moead(gen=1, weight_generation="grid", decomposition="tchebycheff",
                             neighbours=20,
                             CR=1, F=0.5, eta_m=20,
                             realb=0.9,
                             limit=2, preserve_diversity=True)) # https://esa.github.io/pagmo2/docs/python/algorithms/py_algorithms.html#pygmo.moead
print('-'*40, '\n', algo)
# quit()

################################################################
# MOO Step 3:
#   Begin optimization
################################################################
# [4.3.4] Begin optimization
number_of_chromosome = ad.solver.read_swarm_data(ad.bound_filter)
number_of_finished_iterations = number_of_chromosome // popsize
number_of_iterations = 100
logger = logging.getLogger(__name__)
# try:
if True:
    for _ in range(number_of_finished_iterations, number_of_iterations):
        msg = 'This is iteration #%d. '%(_)
        print(msg)
        logger.info(msg)
        pop = algo.evolve(pop)

        msg += 'Write survivors to file. '
        ad.solver.write_swarm_survivor(pop, ad.counter_fitness_return)

        hv = pg.hypervolume(pop)
        quality_measure = hv.compute(ref_point=get_bad_fintess_values(machine_type='PMSM', ref=True)) # ref_point must be dominated by the pop's pareto front
        msg += 'Quality measure by hyper-volume: %g'% (quality_measure)
        print(msg)
        logger.info(msg)

        utility_moo.my_print(ad, pop, _)
        # my_plot(fits, vectors, ndf)
# except Exception as e:
#     print(pop.get_x())
#     print(pop.get_f().tolist())
#     raise e

quit()

#~*~*~*~*~*~*~*~*~*~*~*~*~*~*~*~*~*~*~*~*~*~*~*~*~*~*~*~*~*~*~*~
# '[5] Report Part'
#~*~*~*~*~*~*~*~*~*~*~*~*~*~*~*~*~*~*~*~*~*~*~*~*~*~*~*~*~*~*~*~

# bool_post_processing
# best desigh?

# Status report: Generation, individuals, geometry as input, fea tools, performance as output (based on JSON files)
# Do not show every step, but only those key steps showing how this population is built

# 从json重构JMAG模型（x_denorm）
