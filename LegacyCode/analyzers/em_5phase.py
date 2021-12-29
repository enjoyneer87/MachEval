from time import time as clock_time
import os
import numpy as np
import pandas as pd
import sys
sys.path.append("../..")

from des_opt import InvalidDesign
from .electrical_analysis import CrossSectInnerNotchedRotor as CrossSectInnerNotchedRotor
from .electrical_analysis import CrossSectStator as CrossSectStator
from .electrical_analysis.Location2D import Location2D

EPS = 1e-2  # unit: mm


class BSPM_EM_Analysis:
    def __init__(self, configuration):
        self.configuration = configuration
        self.counter = 0

    def analyze(self, problem, counter=0):
        self.counter = self.counter + 1
        self.machine_variant = problem.machine
        self.operating_point = problem.operating_point
        ####################################################
        # 01 Setting project name and output folder
        ####################################################
        self.project_name = 'proj_%d_' % self.counter

        expected_project_file = self.configuration['run_folder'] + "%s.jproj" % self.project_name

        # Create output folder
        if not os.path.isdir(self.configuration['JMAG_csv_folder']):
            os.makedirs(self.configuration['JMAG_csv_folder'])

        from .electrical_analysis.JMAG import JMAG
        toolJd = JMAG(self.configuration)
        app, attempts = toolJd.open(expected_project_file)
        print('Application is', app)
        if attempts > 1:
            self.project_name = self.project_name + 'attempts_%d' % (attempts)

        self.study_name = self.project_name + "TranPMSM"
        self.design_results_folder = self.configuration['run_folder'] + "%sresults/" % self.project_name
        if not os.path.isdir(self.design_results_folder):
            os.makedirs(self.design_results_folder)
        ################################################################
        # 02 Run ElectroMagnetic analysis
        ################################################################
        self.create_custom_material(app, self.machine_variant.stator_iron_mat['core_material'])
        # Draw cross_section
        draw_success = self.draw_machine(toolJd)
        if not draw_success:
            raise InvalidDesign
        # Import Model into Designer
        toolJd.doc.SaveModel(False)  # True: Project is also saved.
        model = toolJd.app.GetCurrentModel()
        model.SetName(self.project_name)
        model.SetDescription(self.show(self.project_name, toString=True))
        # Add study and run
        valid_design = self.pre_process(app, model)
        if not valid_design:
            raise InvalidDesign
        study = self.add_magnetic_transient_study(app, model, self.configuration['JMAG_csv_folder'],
                                                  self.study_name)  # Change here and there
        self.mesh_study(app, model, study)
        self.run_study(app, study, clock_time())
        # export Voltage if field data exists.
        if not self.configuration['delete_results_after_calculation']:
            # Export Circuit Voltage
            ref1 = app.GetDataManager().GetDataSet("Circuit Voltage")
            app.GetDataManager().CreateGraphModel(ref1)
            app.GetDataManager().GetGraphModel("Circuit Voltage").WriteTable(
                self.configuration['JMAG_csv_folder'] + self.study_name + "_EXPORT_CIRCUIT_VOLTAGE.csv")
        toolJd.close()
        ####################################################
        # 03 Load FEA output
        ####################################################

        fea_rated_output = self.extract_JMAG_results(self.configuration['JMAG_csv_folder'], self.study_name)
        # dh.read_csv_results(self.study_name, self.configuration['JMAG_csv_folder'], self.configuration)

        ####################################################
        # 04 Update stack length for rated torque, update design param and performance accordingly
        ####################################################

        return fea_rated_output

    def initial_excitation_bias_compensation_deg(self):
        return -18

    @property
    def current_trms(self):
        return self.operating_point.Iq * self.machine_variant.Rated_current

    @property
    def current_srms(self):
        return self.operating_point.Iy * self.machine_variant.Rated_current

    @property
    def excitation_freq(self):
        return self.operating_point.speed * self.machine_variant.p / 60

    @property
    def l_coil(self):
        tau_u = (2 * np.pi / self.machine_variant.Q) * (
                self.machine_variant.r_si + self.machine_variant.d_sp + self.machine_variant.d_st / 2)
        l_ew = np.pi * 0.5 * (tau_u + self.machine_variant.w_st) / 2 + tau_u * self.machine_variant.Kov * (
                self.machine_variant.pitch - 1)
        l_coil = 2 * (self.machine_variant.l_st + l_ew)  # length of one coil
        return l_coil

    @property
    def R_coil(self):
        a_wire = (self.machine_variant.s_slot * self.machine_variant.Kcu) / (2 * self.machine_variant.Z_q)
        return (self.l_coil * self.machine_variant.Z_q * self.machine_variant.Q / 5) / (
                self.machine_variant.coil_mat['copper_elec_conductivity'] * a_wire)

    @property
    def copper_loss(self):
        return self.machine_variant.Q * ((self.current_trms) ** 2 + self.current_srms ** 2) * self.R_coil

    def draw_machine(self, toolJd):
        ####################################################
        # Adding parts object
        ####################################################
        self.rotorCore = CrossSectInnerNotchedRotor.CrossSectInnerNotchedRotor(
            name='NotchedRotor',
            mm_d_m=self.machine_variant.d_m * 1e3,
            deg_alpha_m=self.machine_variant.alpha_m,  # angular span of the pole: class type DimAngular
            deg_alpha_ms=self.machine_variant.alpha_ms,  # segment span: class type DimAngular
            mm_d_ri=self.machine_variant.d_ri * 1e3,  # inner radius of rotor: class type DimLinear
            mm_r_sh=self.machine_variant.r_sh * 1e3,  # rotor iron thickness: class type DimLinear
            mm_d_mp=self.machine_variant.d_mp * 1e3,  # inter polar iron thickness: class type DimLinear
            mm_d_ms=self.machine_variant.d_ms * 1e3,  # inter segment iron thickness: class type DimLinear
            p=self.machine_variant.p,  # Set pole-pairs to 2
            s=self.machine_variant.n_m,  # Set magnet segments/pole to 4
            location=Location2D(anchor_xy=[0, 0], deg_theta=0))

        self.shaft = CrossSectInnerNotchedRotor.CrossSectShaft(name='Shaft',
                                                               notched_rotor=self.rotorCore
                                                               )

        self.rotorMagnet = CrossSectInnerNotchedRotor.CrossSectInnerNotchedMagnet(name='RotorMagnet',
                                                                                  notched_rotor=self.rotorCore
                                                                                  )

        self.stator_core = CrossSectStator.CrossSectInnerRotorStator(name='StatorCore',
                                                                     deg_alpha_st=self.machine_variant.alpha_st,
                                                                     deg_alpha_so=self.machine_variant.alpha_so,
                                                                     mm_r_si=self.machine_variant.r_si * 1e3,
                                                                     mm_d_so=self.machine_variant.d_so * 1e3,
                                                                     mm_d_sp=self.machine_variant.d_sp * 1e3,
                                                                     mm_d_st=self.machine_variant.d_st * 1e3,
                                                                     mm_d_sy=self.machine_variant.d_sy * 1e3,
                                                                     mm_w_st=self.machine_variant.w_st * 1e3,
                                                                     mm_r_st=0,  # dummy
                                                                     mm_r_sf=0,  # dummy
                                                                     mm_r_sb=0,  # dummy
                                                                     Q=self.machine_variant.Q,
                                                                     location=Location2D(anchor_xy=[0, 0], deg_theta=0)
                                                                     )

        self.coils = CrossSectStator.CrossSectInnerRotorStatorWinding(name='Coils',
                                                                      stator_core=self.stator_core)
        ####################################################
        # Drawing parts
        ####################################################
        # Rotor Core
        # list_segments = self.rotorCore.draw(toolJd)
        # toolJd.bMirror = False
        # toolJd.iRotateCopy = self.rotorMagnet.notched_rotor.p * 2
        # try:
        #     region1 = toolJd.prepareSection(list_segments)
        # except:
        #     return False

        # Shaft
        list_segments = self.shaft.draw(toolJd)
        toolJd.bMirror = False
        toolJd.iRotateCopy = 1
        region0 = toolJd.prepareSection(list_segments)

        # Rotor Magnet
        list_regions = self.rotorMagnet.draw(toolJd)
        toolJd.bMirror = False
        toolJd.iRotateCopy = self.rotorMagnet.notched_rotor.p * 2
        region2 = toolJd.prepareSection(list_regions, bRotateMerge=False)

        # Sleeve
        # sleeve = CrossSectInnerNotchedRotor.CrossSectSleeve(
        #     name='Sleeve',
        #     notched_magnet=self.rotorMagnet,
        #     d_sleeve=self.machine_variant.d_sl * 1e3  # mm
        # )
        # list_regions = sleeve.draw(toolJd)
        # toolJd.bMirror = False
        # toolJd.iRotateCopy = self.rotorMagnet.notched_rotor.p * 2
        # try:
        #     regionS = toolJd.prepareSection(list_regions)
        # except:
        #     return False

        # Stator Core
        list_regions = self.stator_core.draw(toolJd)
        toolJd.bMirror = True
        toolJd.iRotateCopy = self.stator_core.Q
        region3 = toolJd.prepareSection(list_regions)

        # Stator Winding
        list_regions = self.coils.draw(toolJd)
        toolJd.bMirror = False
        toolJd.iRotateCopy = self.coils.stator_core.Q
        region4 = toolJd.prepareSection(list_regions)

        return True

    def pre_process(self, app, model):
        # pre-process : you can select part by coordinate!
        """ Group """

        def group(name, id_list):
            model.GetGroupList().CreateGroup(name)
            for the_id in id_list:
                model.GetGroupList().AddPartToGroup(name, the_id)
                # model.GetGroupList().AddPartToGroup(name, name) #<- this also works

        part_ID_list = model.GetPartIDs()

        if len(part_ID_list) != int(1 + self.machine_variant.p * 2 + 1 + self.machine_variant.Q * 2):
            print('Parts are missing in this machine')
            return False

        id_shaft = part_ID_list[0]
        partIDRange_Magnet = part_ID_list[1:int(1 + self.machine_variant.p * 2)]
        # id_sleeve = part_ID_list[int(2 + self.machine_variant.p * 2)]
        id_statorCore = part_ID_list[int(2 + self.machine_variant.p * 2)]
        partIDRange_Coil = part_ID_list[
                           int(self.machine_variant.p * 2) + 2: int(2 + self.machine_variant.p * 2) + 2 + int(
                               self.machine_variant.Q * 2)]

        # model.SuppressPart(id_sleeve, 1)

        group("Magnet", partIDRange_Magnet)
        group("Coils", partIDRange_Coil)

        ''' Add Part to Set for later references '''

        def add_part_to_set(name, x, y, ID=None):
            model.GetSetList().CreatePartSet(name)
            model.GetSetList().GetSet(name).SetMatcherType("Selection")
            model.GetSetList().GetSet(name).ClearParts()
            sel = model.GetSetList().GetSet(name).GetSelection()
            if ID is None:
                # print x,y
                sel.SelectPartByPosition(x, y, 0)  # z=0 for 2D
            else:
                sel.SelectPart(ID)
            model.GetSetList().GetSet(name).AddSelected(sel)

        # Shaft
        add_part_to_set('ShaftSet', 0.0, 0.0, ID=id_shaft)  # 坐标没用，不知道为什么，而且都给了浮点数了

        # Create Set for right layer
        Angle_StatorSlotSpan = 360 / self.machine_variant.Q
        # R = self.r_si + self.d_sp + self.d_st *0.5 # this is not generally working (JMAG selects stator core instead.)
        # THETA = 0.25*(Angle_StatorSlotSpan)/180.*np.pi
        R = np.sqrt(self.coils.PCoil[0] ** 2 + self.coils.PCoil[1] ** 2)
        THETA = np.arctan(self.coils.PCoil[1] / self.coils.PCoil[0])
        X = R * np.cos(THETA)
        Y = R * np.sin(THETA)
        count = 0
        for UVW, UpDown in zip(self.machine_variant.layer_phases[0], self.machine_variant.layer_polarity[0]):
            count += 1
            add_part_to_set("coil_right_%s%s %d" % (UVW, UpDown, count), X, Y)

            # print(X, Y, THETA)
            THETA += Angle_StatorSlotSpan / 180. * np.pi
            X = R * np.cos(THETA)
            Y = R * np.sin(THETA)

        # Create Set for left layer
        # THETA = 0.75*(Angle_StatorSlotSpan)/180.*np.pi # 这里这个角度的选择，决定了悬浮绕组产生悬浮力的方向！！！！！
        THETA = np.arctan(-self.coils.PCoil[1] / self.coils.PCoil[0]) + (2 * np.pi) / self.machine_variant.Q
        X = R * np.cos(THETA)
        Y = R * np.sin(THETA)
        count = 0
        for UVW, UpDown in zip(self.machine_variant.layer_phases[1], self.machine_variant.layer_polarity[1]):
            count += 1
            add_part_to_set("coil_left_%s%s %d" % (UVW, UpDown, count), X, Y)

            THETA += Angle_StatorSlotSpan / 180. * np.pi
            X = R * np.cos(THETA)
            Y = R * np.sin(THETA)

        # Create Set for Magnets
        R = (self.machine_variant.r_si - self.machine_variant.delta_e - 0.5 * self.machine_variant.d_m) * 1e3
        Angle_RotorSlotSpan = 360 / (self.machine_variant.p * 2)
        THETA = 0.5 * self.machine_variant.alpha_m / 180 * np.pi  # initial position
        X = R * np.cos(THETA)
        Y = R * np.sin(THETA)
        list_xy_magnets = []
        for ind in range(int(self.machine_variant.p * 2)):
            natural_ind = ind + 1
            add_part_to_set("Magnet %d" % (natural_ind), X, Y)
            list_xy_magnets.append([X, Y])

            THETA += Angle_RotorSlotSpan / 180. * np.pi
            X = R * np.cos(THETA)
            Y = R * np.sin(THETA)

        # Create Set for Motion Region
        def part_list_set(name, list_xy, list_part_id=None, prefix=None):
            model.GetSetList().CreatePartSet(name)
            model.GetSetList().GetSet(name).SetMatcherType("Selection")
            model.GetSetList().GetSet(name).ClearParts()
            sel = model.GetSetList().GetSet(name).GetSelection()
            for xy in list_xy:
                sel.SelectPartByPosition(xy[0], xy[1], 0)  # z=0 for 2D
            if list_part_id is not None:
                for ID in list_part_id:
                    sel.SelectPart(ID)
            model.GetSetList().GetSet(name).AddSelected(sel)

        part_list_set('Motion_Region', list_xy_magnets, list_part_id=[id_shaft])

        part_list_set('MagnetSet', list_xy_magnets)
        return True

    def add_magnetic_transient_study(self, app, model, dir_csv_output_folder, study_name):
        model.CreateStudy("Transient2D", study_name)
        app.SetCurrentStudy(study_name)
        study = model.GetStudy(study_name)

        study.GetStudyProperties().SetValue("ConversionType", 0)
        study.GetStudyProperties().SetValue("NonlinearMaxIteration", self.configuration['max_nonlinear_iterations'])
        study.GetStudyProperties().SetValue("ModelThickness", self.machine_variant.l_st * 1e3)  # [mm] Stack Length

        # Material
        self.add_material(study)

        # Conditions - Motion
        self.the_speed = self.excitation_freq * 60. / self.machine_variant.p  # rpm
        study.CreateCondition("RotationMotion",
                              "RotCon")  # study.GetCondition(u"RotCon").SetXYZPoint(u"", 0, 0, 1) # megbox warning
        print('the_speed:', self.the_speed)
        study.GetCondition("RotCon").SetValue("AngularVelocity", int(self.the_speed))
        study.GetCondition("RotCon").ClearParts()
        study.GetCondition("RotCon").AddSet(model.GetSetList().GetSet("Motion_Region"), 0)
        # Implementation of id=0 control:
        #   d-axis initial position is self.alpha_m*0.5
        #   The U-phase current is sin(omega_syn*t) = 0 at t=0.
        study.GetCondition("RotCon").SetValue(u"InitialRotationAngle", -self.machine_variant.alpha_m * 0.5 + 90 +
                                              self.initial_excitation_bias_compensation_deg() +
                                              (180 / self.machine_variant.p))
        # add 360/(2p) deg to reverse the initial magnetizing direction to make torque positive.

        study.CreateCondition("Torque",
                              "TorCon")  # study.GetCondition(u"TorCon").SetXYZPoint(u"", 0, 0, 0) # megbox warning
        study.GetCondition("TorCon").SetValue("TargetType", 1)
        study.GetCondition("TorCon").SetLinkWithType("LinkedMotion", "RotCon")
        study.GetCondition("TorCon").ClearParts()

        study.CreateCondition("Force", "ForCon")
        study.GetCondition("ForCon").SetValue("TargetType", 1)
        study.GetCondition("ForCon").SetLinkWithType("LinkedMotion", "RotCon")
        study.GetCondition("ForCon").ClearParts()

        # Conditions - FEM Coils & Conductors (i.e. stator/rotor winding)
        self.add_circuit(app, model, study, bool_3PhaseCurrentSource=False)

        # True: no mesh or field results are needed
        study.GetStudyProperties().SetValue("OnlyTableResults", self.configuration['OnlyTableResults'])

        # Linear Solver
        if False:
            # sometime nonlinear iteration is reported to fail and recommend to increase the accerlation rate of ICCG solver
            study.GetStudyProperties().SetValue("IccgAccel", 1.2)
            study.GetStudyProperties().SetValue("AutoAccel", 0)
        else:
            # this can be said to be super fast over ICCG solver.
            # https://www2.jmag-international.com/support/en/pdf/JMAG-Designer_Ver.17.1_ENv3.pdf
            study.GetStudyProperties().SetValue("DirectSolverType", 1)

        if self.configuration['MultipleCPUs']:
            # This SMP(shared memory process) is effective only if there are tons of elements. e.g., over 100,000.
            # too many threads will in turn make them compete with each other and slow down the solve. 2 is good enough
            # for eddy current solve. 6~8 is enough for transient solve.
            study.GetStudyProperties().SetValue("UseMultiCPU", True)
            study.GetStudyProperties().SetValue("MultiCPU", 4)

            # two sections of different time step
        if True:
            number_of_revolution_1TS = self.configuration['number_of_revolution_1TS']
            number_of_revolution_2TS = self.configuration['number_of_revolution_2TS']
            number_of_steps_1TS = self.configuration['number_of_steps_per_rev_1TS'] * number_of_revolution_1TS
            number_of_steps_2TS = self.configuration['number_of_steps_per_rev_2TS'] * number_of_revolution_2TS
            DM = app.GetDataManager()
            DM.CreatePointArray("point_array/timevsdivision", "SectionStepTable")
            refarray = [[0 for i in range(3)] for j in range(3)]
            refarray[0][0] = 0
            refarray[0][1] = 1
            refarray[0][2] = 50
            refarray[1][0] = number_of_revolution_1TS / self.excitation_freq
            refarray[1][1] = number_of_steps_1TS
            refarray[1][2] = 50
            refarray[2][0] = (number_of_revolution_1TS + number_of_revolution_2TS) / self.excitation_freq
            refarray[2][1] = number_of_steps_2TS  # 最后的number_of_steps_2TS（32）步，必须对应半个周期，从而和后面的铁耗计算相对应。
            refarray[2][2] = 50
            DM.GetDataSet("SectionStepTable").SetTable(refarray)
            number_of_total_steps = 1 + number_of_steps_1TS + number_of_steps_2TS  # don't forget to modify here!
            study.GetStep().SetValue("Step", number_of_total_steps)
            study.GetStep().SetValue("StepType", 3)
            study.GetStep().SetTableProperty("Division", DM.GetDataSet("SectionStepTable"))

        # add equations
        study.GetDesignTable().AddEquation("freq")
        study.GetDesignTable().AddEquation("speed")
        study.GetDesignTable().GetEquation("freq").SetType(0)
        study.GetDesignTable().GetEquation("freq").SetExpression("%g" % self.excitation_freq)
        study.GetDesignTable().GetEquation("freq").SetDescription("Excitation Frequency")
        study.GetDesignTable().GetEquation("speed").SetType(1)
        study.GetDesignTable().GetEquation("speed").SetExpression("freq * %d" % (60 / self.machine_variant.p))
        study.GetDesignTable().GetEquation("speed").SetDescription("mechanical speed of four pole")

        # speed, freq, slip
        study.GetCondition("RotCon").SetValue("AngularVelocity", 'speed')

        # Iron Loss Calculation Condition
        # Stator 
        if True:
            cond = study.CreateCondition("Ironloss", "IronLossConStator")
            cond.SetValue("RevolutionSpeed", "freq*60/%d" % self.machine_variant.p)
            cond.ClearParts()
            sel = cond.GetSelection()
            sel.SelectPartByPosition(self.machine_variant.r_si * 1e3 + EPS, EPS, 0)
            cond.AddSelected(sel)
            # Use FFT for hysteresis to be consistent with FEMM's results and to have a FFT plot
            cond.SetValue("HysteresisLossCalcType", 1)
            cond.SetValue("PresetType", 3)  # 3:Custom
            # Specify the reference steps yourself because you don't really know what JMAG is doing behind you
            cond.SetValue("StartReferenceStep",
                          number_of_total_steps + 1 - number_of_steps_2TS * 0.5)  # 1/4 period = number_of_steps_2TS*0.5
            cond.SetValue("EndReferenceStep", number_of_total_steps)
            cond.SetValue("UseStartReferenceStep", 1)
            cond.SetValue("UseEndReferenceStep", 1)
            cond.SetValue("Cyclicity", 4)  # specify reference steps for 1/4 period and extend it to whole period
            cond.SetValue("UseFrequencyOrder", 1)
            cond.SetValue("FrequencyOrder", "1-50")  # Harmonics up to 50th orders
        # Check CSV results for iron loss (You cannot check this for Freq study) # CSV and save space
        study.GetStudyProperties().SetValue("CsvOutputPath", dir_csv_output_folder)  # it's folder rather than file!
        study.GetStudyProperties().SetValue("CsvResultTypes", self.configuration['Csv_Results'])
        study.GetStudyProperties().SetValue("DeleteResultFiles", self.configuration['delete_results_after_calculation'])

        # Rotor
        if False:
            cond = study.CreateCondition("Ironloss", "IronLossConRotor")
            cond.SetValue("BasicFrequencyType", 2)
            cond.SetValue("BasicFrequency", "freq")
            # cond.SetValue(u"BasicFrequency", u"slip*freq") # this require the signal length to be at least 1/4 of
            # slip period, that's too long!
            cond.ClearParts()
            sel = cond.GetSelection()
            sel.SelectPart(self.id_backiron)

            cond.AddSelected(sel)
            # Use FFT for hysteresis to be consistent with FEMM's results
            cond.SetValue("HysteresisLossCalcType", 1)
            cond.SetValue("PresetType", 3)
            # Specify the reference steps yourself because you don't really know what JMAG is doing behind you
            cond.SetValue("StartReferenceStep",
                          number_of_total_steps + 1 - number_of_steps_2TS * 0.5)  # 1/4 period = number_of_steps_2TS*0.5
            cond.SetValue("EndReferenceStep", number_of_total_steps)
            cond.SetValue("UseStartReferenceStep", 1)
            cond.SetValue("UseEndReferenceStep", 1)
            cond.SetValue("Cyclicity", 4)  # specify reference steps for 1/4 period and extend it to whole period
            cond.SetValue("UseFrequencyOrder", 1)
            cond.SetValue("FrequencyOrder", "1-50")  # Harmonics up to 50th orders
        self.study_name = study_name
        return study

    def add_mesh(self, study, model):
        # this is for multi slide planes, which we will not be usin
        refarray = [[0 for i in range(2)] for j in range(1)]
        refarray[0][0] = 3
        refarray[0][1] = 1
        study.GetMeshControl().GetTable("SlideTable2D").SetTable(refarray)

        study.GetMeshControl().SetValue("MeshType",
                                        1)  # make sure this has been exe'd:
        # study.GetCondition(u"RotCon").AddSet(model.GetSetList().GetSet(u"Motion_Region"), 0)
        study.GetMeshControl().SetValue("RadialDivision", self.configuration[
            'mesh_radial_division'])  # for air region near which motion occurs
        study.GetMeshControl().SetValue("CircumferentialDivision", self.configuration[
            'mesh_circum_division'])  # 1440) # for air region near which motion occurs 这个数足够大，sliding mesh才准确。
        study.GetMeshControl().SetValue("AirRegionScale", self.configuration[
            'mesh_air_region_scale'])  # [Model Length]: Specify a value within (1.05 <= value < 1000)
        study.GetMeshControl().SetValue("MeshSize", self.configuration['mesh_size'] * 1e3)  # mm
        study.GetMeshControl().SetValue("AutoAirMeshSize", 0)
        study.GetMeshControl().SetValue("AirMeshSize", self.configuration['mesh_size'] * 1e3)  # mm
        study.GetMeshControl().SetValue("Adaptive", 0)

        # This is not neccessary for whole model FEA. In fact, for BPMSM simulation, it causes mesh error "The copy
        # target region is not found".
        # study.GetMeshControl().CreateCondition("RotationPeriodicMeshAutomatic", "autoRotMesh") with this you can
        # choose to set CircumferentialDivision automatically

        study.GetMeshControl().CreateCondition("Part", "MagnetMeshCtrl")
        study.GetMeshControl().GetCondition("MagnetMeshCtrl").SetValue("Size", self.configuration[
            'mesh_magnet_size'] * 1e3)  # mm
        study.GetMeshControl().GetCondition("MagnetMeshCtrl").ClearParts()
        study.GetMeshControl().GetCondition("MagnetMeshCtrl").AddSet(model.GetSetList().GetSet("MagnetSet"), 0)

        def mesh_all_cases(study):
            numCase = study.GetDesignTable().NumCases()
            for case in range(0, numCase):
                study.SetCurrentCase(case)
                if not study.HasMesh():
                    study.CreateMesh()

        mesh_all_cases(study)

    def create_custom_material(self, app, steel_name):

        core_mat_obj = app.GetMaterialLibrary().GetCustomMaterial(self.machine_variant.stator_iron_mat['core_material'])
        app.GetMaterialLibrary().DeleteCustomMaterialByObject(core_mat_obj)

        app.GetMaterialLibrary().CreateCustomMaterial(self.machine_variant.stator_iron_mat['core_material'],
                                                      "Custom Materials")
        app.GetMaterialLibrary().GetUserMaterial(self.machine_variant.stator_iron_mat['core_material']).SetValue(
            "Density", self.machine_variant.stator_iron_mat['core_material_density'])
        app.GetMaterialLibrary().GetUserMaterial(self.machine_variant.stator_iron_mat['core_material']).SetValue(
            "MagneticSteelPermeabilityType", 2)
        app.GetMaterialLibrary().GetUserMaterial(self.machine_variant.stator_iron_mat['core_material']).SetValue(
            "CoerciveForce", 0)
        # app.GetMaterialLibrary().GetUserMaterial(u"Arnon5-final").GetTable("BhTable").SetName(u"SmoothZeroPointOne")
        BH = np.loadtxt(self.machine_variant.stator_iron_mat['core_bh_file'], unpack=True,
                        usecols=(0, 1))  # values from Nishanth Magnet BH curve
        refarray = BH.T.tolist()
        app.GetMaterialLibrary().GetUserMaterial(self.machine_variant.stator_iron_mat['core_material']).GetTable(
            "BhTable").SetTable(refarray)
        app.GetMaterialLibrary().GetUserMaterial(self.machine_variant.stator_iron_mat['core_material']).SetValue(
            "DemagnetizationCoerciveForce", 0)
        app.GetMaterialLibrary().GetUserMaterial(self.machine_variant.stator_iron_mat['core_material']).SetValue(
            "MagnetizationSaturated", 0)
        app.GetMaterialLibrary().GetUserMaterial(self.machine_variant.stator_iron_mat['core_material']).SetValue(
            "MagnetizationSaturated2", 0)
        app.GetMaterialLibrary().GetUserMaterial(self.machine_variant.stator_iron_mat['core_material']).SetValue(
            "ExtrapolationMethod", 1)
        app.GetMaterialLibrary().GetUserMaterial(self.machine_variant.stator_iron_mat['core_material']).SetValue(
            "YoungModulus", self.machine_variant.stator_iron_mat['core_youngs_modulus'])
        app.GetMaterialLibrary().GetUserMaterial(self.machine_variant.stator_iron_mat['core_material']).SetValue(
            "ShearModulus", 0)
        app.GetMaterialLibrary().GetUserMaterial(self.machine_variant.stator_iron_mat['core_material']).SetValue(
            "YoungModulusX", 0)
        app.GetMaterialLibrary().GetUserMaterial(self.machine_variant.stator_iron_mat['core_material']).SetValue(
            "YoungModulusY", 0)
        app.GetMaterialLibrary().GetUserMaterial(self.machine_variant.stator_iron_mat['core_material']).SetValue(
            "YoungModulusZ", 0)
        app.GetMaterialLibrary().GetUserMaterial(self.machine_variant.stator_iron_mat['core_material']).SetValue(
            "ShearModulusXY", 0)
        app.GetMaterialLibrary().GetUserMaterial(self.machine_variant.stator_iron_mat['core_material']).SetValue(
            "ShearModulusYZ", 0)
        app.GetMaterialLibrary().GetUserMaterial(self.machine_variant.stator_iron_mat['core_material']).SetValue(
            "ShearModulusZX", 0)
        app.GetMaterialLibrary().GetUserMaterial(self.machine_variant.stator_iron_mat['core_material']).SetValue(
            "MagnetizationSaturated2", 0)
        app.GetMaterialLibrary().GetUserMaterial(self.machine_variant.stator_iron_mat['core_material']).SetValue(
            "MagnetizationSaturatedMakerValue", 0)
        app.GetMaterialLibrary().GetUserMaterial(self.machine_variant.stator_iron_mat['core_material']).SetValue(
            "Loss_Type", 1)
        app.GetMaterialLibrary().GetUserMaterial(self.machine_variant.stator_iron_mat['core_material']).SetValue(
            "LossConstantKhX", self.machine_variant.stator_iron_mat['core_ironloss_Kh'])
        app.GetMaterialLibrary().GetUserMaterial(self.machine_variant.stator_iron_mat['core_material']).SetValue(
            "LossConstantKeX", self.machine_variant.stator_iron_mat['core_ironloss_Ke'])
        app.GetMaterialLibrary().GetUserMaterial(self.machine_variant.stator_iron_mat['core_material']).SetValue(
            "LossConstantAlphaX", self.machine_variant.stator_iron_mat['core_ironloss_a'])
        app.GetMaterialLibrary().GetUserMaterial(self.machine_variant.stator_iron_mat['core_material']).SetValue(
            "LossConstantBetaX", self.machine_variant.stator_iron_mat['core_ironloss_b'])

    def add_material(self, study):
        study.SetMaterialByName("StatorCore", self.machine_variant.stator_iron_mat['core_material'])
        study.GetMaterial("StatorCore").SetValue("Laminated", 1)
        study.GetMaterial("StatorCore").SetValue("LaminationFactor",
                                                 self.machine_variant.stator_iron_mat['core_stacking_factor'])

        study.SetMaterialByName("NotchedRotor", self.machine_variant.stator_iron_mat['core_material'])
        study.GetMaterial("NotchedRotor").SetValue("Laminated", 1)
        study.GetMaterial("NotchedRotor").SetValue("LaminationFactor",
                                                   self.machine_variant.stator_iron_mat['core_stacking_factor'])

        study.SetMaterialByName("Coils", "Copper")
        study.GetMaterial("Coils").SetValue("UserConductivityType", 1)

        study.SetMaterialByName(u"Magnet", u"{}".format(self.machine_variant.magnet_mat['magnet_material']))
        study.GetMaterial(u"Magnet").SetValue(u"EddyCurrentCalculation", 1)
        study.GetMaterial(u"Magnet").SetValue(u"Temperature", self.machine_variant.magnet_mat[
            'magnet_max_temperature'])  # TEMPERATURE (There is no 75 deg C option)

        study.GetMaterial(u"Magnet").SetValue(u"Poles", 2 * self.machine_variant.p)

        study.GetMaterial(u"Magnet").SetDirectionXYZ(1, 0, 0)
        study.GetMaterial(u"Magnet").SetAxisXYZ(0, 0, 1)
        study.GetMaterial(u"Magnet").SetOriginXYZ(0, 0, 0)
        study.GetMaterial(u"Magnet").SetPattern(u"ParallelCircular")
        study.GetMaterial(u"Magnet").SetValue(u"StartAngle", 0.5 * self.machine_variant.alpha_m)

        study.SetMaterialByName("Shaft", self.machine_variant.shaft_mat['shaft_material'])
        study.GetMaterial("Shaft").SetValue("Laminated", 0)
        study.GetMaterial("Shaft").SetValue("EddyCurrentCalculation", 1)

    def add_circuit(self, app, model, study, bool_3PhaseCurrentSource=True):
        # Circuit - Current Source
        app.ShowCircuitGrid(True)
        study.CreateCircuit()

        # 4 pole motor Qs=24 dpnv implemented by two layer winding (6 coils). In this case, drive winding has the same
        # slot turns as bearing winding
        def circuit(poles, turns, Rs, ampT, ampS, freq, x=10, y=10):
            # Star Connection_2 is GroupAC
            # Star Connection_4 is GroupBD

            # placing Coils
            y_offset = 4
            study.GetCircuit().CreateComponent("Coil", "coil_U")
            study.GetCircuit().CreateInstance("coil_U", x - 4, y + y_offset)
            study.GetCircuit().GetComponent("coil_U").SetValue("Turn", turns)
            study.GetCircuit().GetComponent("coil_U").SetValue("Resistance", Rs)
            study.GetCircuit().GetInstance("coil_U", 0).RotateTo(90)

            study.GetCircuit().CreateComponent("Coil", "coil_V")
            study.GetCircuit().CreateInstance("coil_V", x + 4, y + y_offset)
            study.GetCircuit().GetComponent("coil_V").SetValue("Turn", turns)
            study.GetCircuit().GetComponent("coil_V").SetValue("Resistance", Rs)
            study.GetCircuit().GetInstance("coil_V", 0).RotateTo(90)

            study.GetCircuit().CreateComponent("Coil", "coil_W")
            study.GetCircuit().CreateInstance("coil_W", x + 12, y + y_offset)
            study.GetCircuit().GetComponent("coil_W").SetValue("Turn", turns)
            study.GetCircuit().GetComponent("coil_W").SetValue("Resistance", Rs)
            study.GetCircuit().GetInstance("coil_W", 0).RotateTo(90)

            study.GetCircuit().CreateComponent("Coil", "coil_X")
            study.GetCircuit().CreateInstance("coil_X", x + 20, y + y_offset)
            study.GetCircuit().GetComponent("coil_X").SetValue("Turn", turns)
            study.GetCircuit().GetComponent("coil_X").SetValue("Resistance", Rs)
            study.GetCircuit().GetInstance("coil_X", 0).RotateTo(90)

            study.GetCircuit().CreateComponent("Coil", "coil_Y")
            study.GetCircuit().CreateInstance("coil_Y", x + 28, y + y_offset)
            study.GetCircuit().GetComponent("coil_Y").SetValue("Turn", turns)
            study.GetCircuit().GetComponent("coil_Y").SetValue("Resistance", Rs)
            study.GetCircuit().GetInstance("coil_Y", 0).RotateTo(90)

            # Connecting one side of Coils to GND
            study.GetCircuit().CreateWire(x-4, y + y_offset-2, x, y + y_offset-2)
            study.GetCircuit().CreateWire(x+4, y + y_offset-2, x, y + y_offset-2)
            study.GetCircuit().CreateWire(x+12, y + y_offset-2, x, y + y_offset-2)
            study.GetCircuit().CreateWire(x+20, y + y_offset-2, x, y + y_offset-2)
            study.GetCircuit().CreateWire(x+28, y + y_offset-2, x, y + y_offset-2)

            study.GetCircuit().CreateComponent("Ground", "Ground")
            study.GetCircuit().CreateInstance("Ground", x, y + y_offset - 4)

            # Placing current sources
            I1 = "CS_U"
            I2 = "CS_V"
            I3 = "CS_W"
            I4 = "CS_X"
            I5 = "CS_Y"
            study.GetCircuit().CreateComponent("CurrentSource", I1)
            study.GetCircuit().CreateInstance(I1, x - 4, y + y_offset + 4)
            study.GetCircuit().GetInstance(I1, 0).RotateTo(90)

            study.GetCircuit().CreateComponent("CurrentSource", I2)
            study.GetCircuit().CreateInstance(I2, x + 4, y + y_offset + 4)
            study.GetCircuit().GetInstance(I2, 0).RotateTo(90)

            study.GetCircuit().CreateComponent("CurrentSource", I3)
            study.GetCircuit().CreateInstance(I3, x + 12, y + y_offset + 4)
            study.GetCircuit().GetInstance(I3, 0).RotateTo(90)

            study.GetCircuit().CreateComponent("CurrentSource", I4)
            study.GetCircuit().CreateInstance(I4, x + 20, y + y_offset + 4)
            study.GetCircuit().GetInstance(I4, 0).RotateTo(90)

            study.GetCircuit().CreateComponent("CurrentSource", I5)
            study.GetCircuit().CreateInstance(I5, x + 28, y + y_offset + 4)
            study.GetCircuit().GetInstance(I5, 0).RotateTo(90)

            # Setting current values
            func = app.FunctionFactory().Composite()
            f1 = app.FunctionFactory().Sin(ampT, freq, 0)
            f2 = app.FunctionFactory().Sin(ampS, freq, 0)
            func.AddFunction(f1)
            func.AddFunction(f2)
            study.GetCircuit().GetComponent(I1).SetFunction(func)

            func = app.FunctionFactory().Composite()
            f1 = app.FunctionFactory().Sin(ampT, freq, -72)
            f2 = app.FunctionFactory().Sin(ampS, freq, -144)
            func.AddFunction(f1)
            func.AddFunction(f2)
            study.GetCircuit().GetComponent(I2).SetFunction(func)

            func = app.FunctionFactory().Composite()
            f1 = app.FunctionFactory().Sin(ampT, freq, -144)
            f2 = app.FunctionFactory().Sin(ampS, freq, -288)
            func.AddFunction(f1)
            func.AddFunction(f2)
            study.GetCircuit().GetComponent(I3).SetFunction(func)

            func = app.FunctionFactory().Composite()
            f1 = app.FunctionFactory().Sin(ampT, freq, -216)
            f2 = app.FunctionFactory().Sin(ampS, freq, -72)
            func.AddFunction(f1)
            func.AddFunction(f2)
            study.GetCircuit().GetComponent(I4).SetFunction(func)

            func = app.FunctionFactory().Composite()
            f1 = app.FunctionFactory().Sin(ampT, freq, -288)
            f2 = app.FunctionFactory().Sin(ampS, freq, -216)
            func.AddFunction(f1)
            func.AddFunction(f2)
            study.GetCircuit().GetComponent(I5).SetFunction(func)

            # Terminal Voltage/Circuit Voltage: Check for outputting CSV results
            study.GetCircuit().CreateTerminalLabel("Terminal_U", x - 4, -1*(y + y_offset + 2))
            study.GetCircuit().CreateTerminalLabel("Terminal_V", x + 4, -1*(y + y_offset + 2))
            study.GetCircuit().CreateTerminalLabel("Terminal_W", x + 12, -1*(y + y_offset + 2))
            study.GetCircuit().CreateTerminalLabel("Terminal_X", x + 20, -1*(y + y_offset + 2))
            study.GetCircuit().CreateTerminalLabel("Terminal_Y", x + 28, -1*(y + y_offset + 2))

        current_tpeak = self.current_trms * np.sqrt(2)  # It, max current at torque terminal
        current_speak = self.current_srms * np.sqrt(2)  # Is, max current at suspension terminal Is+It/2

        slot_area_utilizing_ratio = (current_tpeak + current_speak) / (self.machine_variant.Rated_current * np.sqrt(2))
        print('---Slot area utilizing ratio is', slot_area_utilizing_ratio)
        print('---Peak Current per coil :', self.machine_variant.Rated_current * np.sqrt(2))
        print('---Peak torque current :', current_tpeak)
        print('---Peak suspension current :', current_speak)
        print('---Torque_current_ratio:', self.operating_point.Iq)
        print('---Suspension_current_ratio:', self.operating_point.Iy)

        circuit(self.machine_variant.p, self.machine_variant.Z_q, Rs=self.R_coil, ampT=current_tpeak,
                ampS=current_speak, freq=self.excitation_freq)

        for phase in ['U', 'V', 'W', 'X', 'Y']:
            study.CreateCondition("FEMCoil", 'phase_' + phase)
            # link between FEM Coil Condition and Circuit FEM Coil
            condition = study.GetCondition('phase_' + phase)
            condition.SetLink("coil_%s" % phase)
            condition.GetSubCondition("untitled").SetName("delete")

        count = 0  # count indicates which slot the current rightlayer is in.
        index = 0
        dict_dir = {'+': 1, '-': 0}
        coil_pitch = self.machine_variant.pitch  # self.dict_coil_connection[0]
        # select the part (via `Set') to assign the FEM Coil condition
        for UVW, UpDown in zip(self.machine_variant.layer_phases[0], self.machine_variant.layer_polarity[0]):
            count += 1
            condition = study.GetCondition('phase_' + UVW)

            # right layer
            condition.CreateSubCondition("FEMCoilData", "Coil Set Right %d" % count)
            subcondition = condition.GetSubCondition("Coil Set Right %d" % count)
            subcondition.ClearParts()
            subcondition.AddSet(model.GetSetList().GetSet("coil_%s%s%s %d" % ('right_', UVW, UpDown, count)), 0)
            subcondition.SetValue("Direction2D", dict_dir[UpDown])

            # left layer
            if coil_pitch > 0:
                if count + coil_pitch <= self.machine_variant.Q:
                    count_leftlayer = count + coil_pitch
                    index_leftlayer = index + coil_pitch
                else:
                    count_leftlayer = int(count + coil_pitch - self.machine_variant.Q)
                    index_leftlayer = int(index + coil_pitch - self.machine_variant.Q)
            else:
                if count + coil_pitch > 0:
                    count_leftlayer = count + coil_pitch
                    index_leftlayer = index + coil_pitch
                else:
                    count_leftlayer = int(count + coil_pitch + self.machine_variant.Q)
                    index_leftlayer = int(index + coil_pitch + self.machine_variant.Q)

            # Check if it is a distributed windg???
            if self.machine_variant.pitch == 1:
                print('Concentrated winding!')
                UVW = self.machine_variant.layer_phases[1][index_leftlayer]
                UpDown = self.machine_variant.layer_polarity[1][index_leftlayer]
            else:
                if self.machine_variant.layer_phases[1][index_leftlayer] != UVW:
                    print('[Warn] Potential bug in your winding layout detected.')
                    raise Exception('Bug in winding layout detected.')
                if UpDown == '+':
                    UpDown = '-'
                else:
                    UpDown = '+'

            condition.CreateSubCondition("FEMCoilData", "Coil Set Left %d" % count_leftlayer)
            subcondition = condition.GetSubCondition("Coil Set Left %d" % count_leftlayer)
            subcondition.ClearParts()
            subcondition.AddSet(model.GetSetList().GetSet("coil_%s%s%s %d" % ('left_', UVW, UpDown, count_leftlayer)),
                                0)  # left layer
            subcondition.SetValue("Direction2D", dict_dir[UpDown])
            index += 1
            # clean up
            for phase in ['U', 'V', 'W', 'X', 'Y']:
                condition = study.GetCondition('phase_' + phase)
                condition.RemoveSubCondition("delete")

    def show(self, name, toString=False):
        attrs = list(vars(self).items())
        key_list = [el[0] for el in attrs]
        val_list = [el[1] for el in attrs]
        the_dict = dict(list(zip(key_list, val_list)))
        sorted_key = sorted(key_list, key=lambda item: (
            int(item.partition(' ')[0]) if item[0].isdigit() else float('inf'),
            item))  # this is also useful for string beginning with digiterations '15 Steel'.
        tuple_list = [(key, the_dict[key]) for key in sorted_key]
        if not toString:
            print('- Bearingless PMSM Individual #%s\n\t' % name, end=' ')
            print(', \n\t'.join("%s = %s" % item for item in tuple_list))
            return ''
        else:
            return '\n- Bearingless PMSM Individual #%s\n\t' % name + ', \n\t'.join(
                "%s = %s" % item for item in tuple_list)

    def run_study(self, app, study, toc):
        if not self.configuration['JMAG_Scheduler']:
            print('-----------------------Running JMAG (et 30 secs)...')
            # if run_list[1] == True:
            study.RunAllCases()
            msg = 'Time spent on %s is %g s.' % (study.GetName(), clock_time() - toc)
            print(msg)
        else:
            print('Submit to JMAG_Scheduler...')
            job = study.CreateJob()
            job.SetValue("Title", study.GetName())
            job.SetValue("Queued", True)
            job.Submit(False)  # False:CurrentCase, True:AllCases
            # wait and check
            # study.CheckForCaseResults()
        app.Save()

    def mesh_study(self, app, model, study):

        # this `if' judgment is effective only if JMAG-DeleteResultFiles is False 
        # if not study.AnyCaseHasResult(): 
        # mesh
        print('------------------Adding mesh')
        self.add_mesh(study, model)

        # Export Image
        app.View().ShowAllAirRegions()
        # app.View().ShowMeshGeometry() # 2nd btn
        app.View().ShowMesh()  # 3rn btn
        app.View().Zoom(3)
        app.View().Pan(-self.machine_variant.r_si, 0)
        app.ExportImageWithSize(self.design_results_folder + self.project_name + 'mesh.png', 2000, 2000)
        app.View().ShowModel()  # 1st btn. close mesh view, and note that mesh data will be deleted if only ouput table
        # results are selected.

    def extract_JMAG_results(self, path, study_name):
        current_csv_path = path + study_name + '_circuit_current.csv'
        voltage_csv_path = path + study_name + '_EXPORT_CIRCUIT_VOLTAGE.csv'
        torque_csv_path = path + study_name + '_torque.csv'
        force_csv_path = path + study_name + '_force.csv'
        iron_loss_path = path + study_name + '_iron_loss_loss.csv'
        hysteresis_loss_path = path + study_name + '_hysteresis_loss_loss.csv'
        eddy_current_loss_path = path + study_name + '_joule_loss.csv'

        curr_df = pd.read_csv(current_csv_path, skiprows=6)
        volt_df = pd.read_csv(voltage_csv_path,)
        volt_df.rename(columns={'Time, s': 'Time(s)', 'Terminal_Us [Case 1]': 'Terminal_Us',
                                'Terminal_U [Case 1]': 'Terminal_U',
                                'Terminal_V [Case 1]': 'Terminal_V',
                                'Terminal_W [Case 1]': 'Terminal_W',
                                'Terminal_X [Case 1]': 'Terminal_X',
                                'Terminal_Y [Case 1]': 'Terminal_Y', }, inplace=True)

        tor_df = pd.read_csv(torque_csv_path, skiprows=6)
        force_df = pd.read_csv(force_csv_path, skiprows=6)
        iron_df = pd.read_csv(iron_loss_path, skiprows=6)
        hyst_df = pd.read_csv(hysteresis_loss_path, skiprows=6)
        eddy_df = pd.read_csv(eddy_current_loss_path, skiprows=6)

        range_2TS = int(
            self.configuration['number_of_steps_per_rev_2TS'] * self.configuration['number_of_revolution_2TS'])

        curr_df = curr_df.set_index('Time(s)')
        tor_df = tor_df.set_index('Time(s)')
        volt_df = volt_df.set_index('Time(s)')
        force_df = force_df.set_index('Time(s)')
        eddy_df = eddy_df.set_index('Time(s)')
        hyst_df = hyst_df.set_index('Frequency(Hz)')
        iron_df = iron_df.set_index('Frequency(Hz)')

        fea_data = {
            'current': curr_df,
            'voltage': volt_df,
            'torque': tor_df,
            'force': force_df,
            'iron_loss': iron_df,
            'hysteresis_loss': hyst_df,
            'eddy_current_loss': eddy_df,
            'copper_loss': self.copper_loss,
            'range_fine_step': range_2TS
        }

        return fea_data
