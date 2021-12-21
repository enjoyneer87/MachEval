from time import time as clock_time
import os
from .FEMM_Solver import FEMM_Solver


class IM_EM_Analysis():

    def __init__(self, configuration):
        self.configuration = configuration
        self.machine_variant = None
        self.operating_point = None

    def analyze(self, problem, counter = 0):
        self.machine_variant = problem.machine
        self.operating_point = problem.operating_point
        problem.configuration = self.configuration
        ####################################################
        # 01 Setting project name and output folder
        ####################################################
        self.project_name = 'proj_%d_' % (counter)
        # Create output folder
        if not os.path.isdir(self.configuration['JMAG_csv_folder']):
            os.makedirs(self.configuration['JMAG_csv_folder'])

        self.machine_variant.fea_config_dict = self.configuration
        self.machine_variant.bool_initial_design = self.configuration['bool_initial_design']
        self.machine_variant.ID = self.project_name
        self.bool_run_in_JMAG_Script_Editor = False

        print('Run greedy_search_for_breakdown_slip...')
        femm_tic = clock_time()
        self.femm_solver = FEMM_Solver(self.machine_variant, flag_read_from_jmag=False, freq=500)  # eddy+static
        self.femm_solver.greedy_search_for_breakdown_slip(self.configuration['JMAG_csv_folder'], self.project_name,
                                                          bool_run_in_JMAG_Script_Editor=self.bool_run_in_JMAG_Script_Editor,
                                                          fraction=1)

        slip_freq_breakdown_torque, breakdown_torque, breakdown_force = self.femm_solver.wait_greedy_search(femm_tic)

        # print('Stack length', self.machine_variant.l_st)
        if True:
            number_of_steps_2ndTSS = self.configuration['designer.number_of_steps_2ndTSS']
            from ..electrical_analysis.JMAG import JMAG
            toolJd = JMAG(self.configuration)
            app, attempts = toolJd.open(self.configuration['JMAG_csv_folder'])
            model = app.GetModel(self.project_name)
            DM = app.GetDataManager()
            DM.CreatePointArray("point_array/timevsdivision", "SectionStepTable")
            refarray = [[0 for i in range(3)] for j in range(3)]
            refarray[0][0] = 0
            refarray[0][1] = 1
            refarray[0][2] = 50
            refarray[1][0] = 0.5 / slip_freq_breakdown_torque  # 0.5 for 17.1.03l # 1 for 17.1.02y
            refarray[1][1] = number_of_steps_2ndTSS  # 16 for 17.1.03l #32 for 17.1.02y
            refarray[1][2] = 50
            refarray[2][0] = refarray[1][0] + 0.5 / self.machine_variant.DriveW_Freq  # 0.5 for 17.1.03l
            refarray[2][1] = number_of_steps_2ndTSS  # also modify range_ss! # don't forget to modify below!
            refarray[2][2] = 50
            DM.GetDataSet("SectionStepTable").SetTable(refarray)
            number_of_total_steps = 1 + 2 * number_of_steps_2ndTSS  # [Double Check] don't forget to modify here!
            study = self.add_study(app, model, self.configuration['JMAG_csv_folder'], choose_study_type='frequency')
            study.GetStep().SetValue("Step", number_of_total_steps)
            study.GetStep().SetValue("StepType", 3)
            study.GetStep().SetTableProperty("Division", DM.GetDataSet("SectionStepTable"))



    def add_study(self, app, model, dir_csv_output_folder, choose_study_type='frequency'):

        self.choose_study_type = choose_study_type  # Transient solves for different Qr, skewing angles and short pitches.

        # Time step initialization
        if self.choose_study_type == 'transient':
            self.minimal_time_interval = 1 / 16. / self.DriveW_Freq
            self.end_time = 0.2  # 20 / self.DriveW_Freq
            self.no_divisiton = int(self.end_time / self.minimal_time_interval)
            self.no_steps = int(self.no_divisiton + 1)
            # print self.minimal_time_interval, end_time, no_divisiton, no_steps
            # quit()
        elif self.choose_study_type == 'frequency':  # freq analysis
            self.table_freq_division_refarray = [[0 for i in range(3)] for j in range(4)]
            self.table_freq_division_refarray[0][0] = 2
            self.table_freq_division_refarray[0][1] = 1
            self.table_freq_division_refarray[0][2] = self.configuration["max_nonlinear_iteration"]
            self.table_freq_division_refarray[1][0] = 10
            self.table_freq_division_refarray[1][1] = 32  # 8
            self.table_freq_division_refarray[1][2] = self.configuration["max_nonlinear_iteration"]
            self.table_freq_division_refarray[2][0] = 16
            self.table_freq_division_refarray[2][1] = 2
            self.table_freq_division_refarray[2][2] = self.configuration["max_nonlinear_iteration"]
            self.table_freq_division_refarray[3][0] = 24
            self.table_freq_division_refarray[3][1] = 2
            self.table_freq_division_refarray[3][2] = self.configuration["max_nonlinear_iteration"]

            # self.table_freq_division_refarray = [[0 for i in range(3)] for j in range(2)]
            # self.table_freq_division_refarray[0][0] = 2
            # self.table_freq_division_refarray[0][1] =   1
            # self.table_freq_division_refarray[0][2] =    self.max_nonlinear_iteration
            # self.table_freq_division_refarray[1][0] = 18
            # self.table_freq_division_refarray[1][1] =   4 # for testing the script # 16
            # self.table_freq_division_refarray[1][2] =    self.max_nonlinear_iteration

            self.no_steps = sum([el[1] for el in self.table_freq_division_refarray])
        elif self.choose_study_type == 'static':  # static analysis
            pass

        # Study property
        if self.choose_study_type == 'transient':
            study_name = self.project_name + "Tran"
            model.CreateStudy("Transient2D", study_name)
            app.SetCurrentStudy(study_name)
            study = model.GetStudy(study_name)

            study.GetStudyProperties().SetValue("ModelThickness", self.machine_variant.l_st)  # Stack Length
            study.GetStudyProperties().SetValue("ConversionType", 0)
            study.GetStudyProperties().SetValue("ApproximateTransientAnalysis",
                                                1)  # psuedo steady state freq is for PWM drive to use
            study.GetStudyProperties().SetValue("SpecifySlip", 1)
            study.GetStudyProperties().SetValue("Slip", self.the_slip)
            study.GetStudyProperties().SetValue("OutputSteadyResultAs1stStep", 0)
            study.GetStudyProperties().SetValue("NonlinearMaxIteration", self.configuration["max_nonlinear_iteration"])
            study.GetStudyProperties().SetValue("CsvOutputPath",
                                                dir_csv_output_folder)  # it's folder rather than file!
            # study.GetStudyProperties().SetValue(u"CsvResultTypes", u"Torque;Force;FEMCoilFlux;LineCurrent;ElectricPower;TerminalVoltage;JouleLoss;TotalDisplacementAngle")
            study.GetStudyProperties().SetValue("CsvResultTypes",
                                                "Torque;Force;LineCurrent;TerminalVoltage;JouleLoss;TotalDisplacementAngle")
            study.GetStudyProperties().SetValue("TimePeriodicType",
                                                2)  # This is for TP-EEC but is not effective
            study.GetStep().SetValue("StepType", 1)
            study.GetStep().SetValue("Step", self.no_steps)
            study.GetStep().SetValue("StepDivision", self.no_divisiton)
            study.GetStep().SetValue("EndPoint", self.end_time)
            # study.GetStep().SetValue(u"Step", 501)
            # study.GetStep().SetValue(u"StepDivision", 500)
            # study.GetStep().SetValue(u"EndPoint", 0.5)
            # app.View().SetCurrentCase(1)
        elif self.choose_study_type == 'frequency':  # freq analysis
            study_name = self.project_name + "Freq"
            model.CreateStudy("Frequency2D", study_name)
            app.SetCurrentStudy(study_name)
            study = model.GetStudy(study_name)

            # Misc
            study.GetStudyProperties().SetValue("NonlinearMaxIteration", self.configuration["max_nonlinear_iteration"])
            study.GetStudyProperties().SetValue("ModelThickness", self.machine_variant.l_st)  # Stack Length
            study.GetStudyProperties().SetValue("ConversionType", 0)

            # CSV & Output
            study.GetStudyProperties().SetValue("CsvOutputPath",
                                                dir_csv_output_folder)  # it's folder rather than file!
            # study.GetStudyProperties().SetValue(u"CsvResultTypes", u"Torque;Force;FEMCoilFlux;LineCurrent;ElectricPower;TerminalVoltage;JouleLoss;TotalDisplacementAngle")
            study.GetStudyProperties().SetValue("CsvResultTypes", "Torque;Force;LineCurrent;JouleLoss")
            study.GetStudyProperties().SetValue("DeleteResultFiles",
                                                self.configuration['delete_results_after_calculation'])

            # Time step
            DM = app.GetDataManager()
            DM.CreatePointArray("point_array/frequency_vs_division", "table_freq_division")
            # DM.GetDataSet(u"").SetName(u"table_freq_division")
            DM.GetDataSet("table_freq_division").SetTable(self.table_freq_division_refarray)
            study.GetStep().SetValue("Step", self.no_steps)
            study.GetStep().SetValue("StepType", 3)
            study.GetStep().SetTableProperty("Division", DM.GetDataSet("table_freq_division"))

            # This is exclusive for freq analysis
            study.GetStudyProperties().SetValue("BHCorrection", 1)
            # print 'BHCorrection for nonlinear time harmonic analysis is turned ON.'
        elif self.choose_study_type == 'static':  # static analysis
            study_name = "Static"
            model.CreateStudy("Static2D", study_name)
            app.SetCurrentStudy(study_name)
            study = model.GetStudy(study_name)

            study.GetStudyProperties().SetValue("NonlinearMaxIteration", self.configuration["max_nonlinear_iteration"])
            study.GetStudyProperties().SetValue("ModelThickness", self.machine_variant.l_st)  # Stack Length
            study.GetStudyProperties().SetValue("ConversionType", 0)
            study.GetStudyProperties().SetValue("CsvOutputPath",
                                                dir_csv_output_folder)  # it's folder rather than file!
            # study.GetStudyProperties().SetValue(u"CsvResultTypes", u"Torque;Force;FEMCoilFlux;LineCurrent;ElectricPower;TerminalVoltage;JouleLoss;TotalDisplacementAngle")
            study.GetStudyProperties().SetValue("CsvResultTypes", "Torque;Force;LineCurrent;JouleLoss")
            study.GetStudyProperties().SetValue("DeleteResultFiles",
                                                self.configuration['delete_results_after_calculation'])

        # Material
        self.add_material(study)

        # Conditions - Motion
        if self.choose_study_type == 'transient':
            study.CreateCondition("RotationMotion", "RotCon")
            # study.GetCondition(u"RotCon").SetXYZPoint(u"", 0, 0, 1) # megbox warning
            study.GetCondition("RotCon").SetValue("AngularVelocity", int(self.the_speed))
            study.GetCondition("RotCon").ClearParts()
            study.GetCondition("RotCon").AddSet(model.GetSetList().GetSet("Motion_Region"), 0)

            study.CreateCondition("Torque", "TorCon")
            # study.GetCondition(u"TorCon").SetXYZPoint(u"", 0, 0, 0) # megbox warning
            study.GetCondition("TorCon").SetValue("TargetType", 1)
            study.GetCondition("TorCon").SetLinkWithType("LinkedMotion", "RotCon")
            study.GetCondition("TorCon").ClearParts()

            study.CreateCondition("Force", "ForCon")
            study.GetCondition("ForCon").SetValue("TargetType", 1)
            study.GetCondition("ForCon").SetLinkWithType("LinkedMotion", "RotCon")
            study.GetCondition("ForCon").ClearParts()
        elif self.choose_study_type == 'frequency':  # freq analysis
            study.CreateCondition("FQRotationMotion", "RotCon")
            # study.GetCondition(u"RotCon").SetXYZPoint(u"", 0, 0, 0)
            study.GetCondition("RotCon").ClearParts()
            study.GetCondition("RotCon").AddSet(model.GetSetList().GetSet("Motion_Region"), 0)

            study.CreateCondition("Torque", "TorCon")
            study.GetCondition("TorCon").SetValue("TargetType", 1)
            study.GetCondition("TorCon").SetLinkWithType("LinkedMotion", "RotCon")
            study.GetCondition("TorCon").ClearParts()

            study.CreateCondition("Force", "ForCon")
            study.GetCondition("ForCon").SetValue("TargetType", 1)
            study.GetCondition("ForCon").SetLinkWithType("LinkedMotion", "RotCon")
            study.GetCondition("ForCon").ClearParts()
        elif self.choose_study_type == 'static':  # static analysis
            # duplicating study can fail if the im instance is destroyed.
            # model.DuplicateStudyWithType(original_study_name, u"Static2D", "Static")
            # study = app.GetCurrentStudy()

            study.CreateCondition("Torque", "TorCon")
            study.GetCondition("TorCon").SetValue("TargetType", 1)
            study.GetCondition("TorCon").ClearParts()
            study.GetCondition("TorCon").AddSet(model.GetSetList().GetSet("Motion_Region"), 0)

            study.CreateCondition("Force", "ForCon")
            study.GetCondition("ForCon").SetValue("TargetType", 1)
            study.GetCondition("ForCon").ClearParts()
            study.GetCondition("ForCon").AddSet(model.GetSetList().GetSet("Motion_Region"), 0)

            # 静态场不需要用到电路和FEM Coil/Conductor，这里设置完直接返回了
            # no mesh results are needed
            study.GetStudyProperties().SetValue("OnlyTableResults", self.configuration["designer.OnlyTableResults"])
            study.GetStudyProperties().SetValue("Magnetization", 0)
            study.GetStudyProperties().SetValue("PermeanceFactor", 0)
            study.GetStudyProperties().SetValue("DifferentialPermeability", 0)
            study.GetStudyProperties().SetValue("LossDensity", 0)
            study.GetStudyProperties().SetValue("SurfaceForceDensity", 0)
            study.GetStudyProperties().SetValue("LorentzForceDensity", 0)
            study.GetStudyProperties().SetValue("Stress", 0)
            study.GetStudyProperties().SetValue("HysteresisLossDensity", 0)
            study.GetStudyProperties().SetValue("RestartFile", 0)
            study.GetStudyProperties().SetValue("JCGMonitor", 0)
            study.GetStudyProperties().SetValue("CoerciveForceNormal", 0)
            study.GetStudyProperties().SetValue("Temperature", 0)
            study.GetStudyProperties().SetValue("IronLossDensity",
                                                0)  # 我们要铁耗作为后处理，而不是和磁场同时求解。（[搜Iron Loss Formulas] Use one of the following methods to calculate iron loss and iron loss density generated in magnetic materials in JMAG. • Calculating Iron Loss Using Only the Magnetic Field Analysis Solver (page 6): It is a method to run magnetic field analysis considering the effect of iron loss. In this method, iron loss condition is not used. • Calculating Iron Loss Using the Iron Loss Analysis Solver (page 8): It is a method to run iron loss analysis using the results data of magnetic field analysis. It will be one of the following procedures. • Run magnetic field analysis study with iron loss condition • Run iron loss analysis study with reference to the result file of magnetic field analysis This chapter describes these two methods.）

            # Linear Solver
            if False:
                # sometime nonlinear iteration is reported to fail and recommend to increase the accerlation rate of ICCG solver
                study.GetStudyProperties().SetValue("IccgAccel", 1.2)
                study.GetStudyProperties().SetValue("AutoAccel", 0)
            else:
                # https://www2.jmag-international.com/support/en/pdf/JMAG-Designer_Ver.17.1_ENv3.pdf
                study.GetStudyProperties().SetValue("DirectSolverType", 1)

            # too many threads will in turn make them compete with each other and slow down the solve. 2 is good enough for eddy current solve. 6~8 is enough for transient solve.
            study.GetStudyProperties().SetValue("UseMultiCPU", True)
            study.GetStudyProperties().SetValue("MultiCPU",
                                                2)  # this is effective for Transient Solver and 2 is enough!

            self.study_name = study_name
            return study
        from .winding_layout_im import winding_layout_v2
        print('Qs, p, ps, y', self.machine_variant.Qs, self.machine_variant.DriveW_poles / 1,
                                                                        self.machine_variant.BeariW_poles / 1,
                                                                        self.machine_variant.pitch)
        wily = winding_layout_v2(DPNV_or_SEPA=True, Qs = self.machine_variant.Qs,
                                                                        p = self.machine_variant.BeariW_poles / 2,
                                 ps = self.machine_variant.DriveW_poles / 2,
                                                                        )
        self.wily = wily
        # Conditions - FEM Coils & Conductors (i.e. stator/rotor winding)
        if choose_study_type == 'frequency':
            if self.wily.bool_3PhaseCurrentSource == True:
                msg = 'Cannot use Composite type function for the CurrentSource in circuit of JMAG. So it needs more work, e.g., two more CurrentSources.'
                logging.getLogger(__name__).warn(msg)
            self.add_circuit(app, model, study, bool_3PhaseCurrentSource=self.wily.bool_3PhaseCurrentSource)
        elif choose_study_type == 'transient':
            self.add_circuit(app, model, study, bool_3PhaseCurrentSource=self.wily.bool_3PhaseCurrentSource)

        # True: no mesh or field results are needed
        study.GetStudyProperties().SetValue("OnlyTableResults",
                                            self.configuration['designer.OnlyTableResults'])

        # Linear Solver
        if False:
            # sometime nonlinear iteration is reported to fail and recommend to increase the accerlation rate of ICCG solver
            study.GetStudyProperties().SetValue("IccgAccel", 1.2)
            study.GetStudyProperties().SetValue("AutoAccel", 0)
        else:
            # this can be said to be super fast over ICCG solver.
            # https://www2.jmag-international.com/support/en/pdf/JMAG-Designer_Ver.17.1_ENv3.pdf
            study.GetStudyProperties().SetValue("DirectSolverType", 1)

        # This SMP is effective only if there are tons of elements. e.g., over 100,000.
        # too many threads will in turn make them compete with each other and slow down the solve. 2 is good enough for eddy current solve. 6~8 is enough for transient solve.
        study.GetStudyProperties().SetValue("UseMultiCPU", True)
        study.GetStudyProperties().SetValue("MultiCPU", 2)

        # # this is for the CAD parameters to rotate the rotor. the order matters for param_no to begin at 0.
        # if self.MODEL_ROTATE:
        #     self.add_cad_parameters(study)

        self.study_name = study_name
        return study

    def add_material(self, study):
        if 'M19' in self.machine_variant.stator_iron_mat['core_material']:
            study.SetMaterialByName("Stator Core", "M-19 Steel Gauge-29")
            study.GetMaterial("Stator Core").SetValue("Laminated", 1)
            study.GetMaterial("Stator Core").SetValue("LaminationFactor", 95)
                # study.GetMaterial(u"Stator Core").SetValue(u"UserConductivityValue", 1900000)

            study.SetMaterialByName("Rotor Core", "M-19 Steel Gauge-29")
            study.GetMaterial("Rotor Core").SetValue("Laminated", 1)
            study.GetMaterial("Rotor Core").SetValue("LaminationFactor", 95)

        elif 'M15' in self.machine_variant.stator_iron_mat['core_material']:
            study.SetMaterialByName("Stator Core", "M-15 Steel")
            study.GetMaterial("Stator Core").SetValue("Laminated", 1)
            study.GetMaterial("Stator Core").SetValue("LaminationFactor", 98)

            study.SetMaterialByName("Rotor Core", "M-15 Steel")
            study.GetMaterial("Rotor Core").SetValue("Laminated", 1)
            study.GetMaterial("Rotor Core").SetValue("LaminationFactor", 98)

        elif self.machine_variant.stator_iron_mat['core_material'] == 'Arnon5':
            study.SetMaterialByName("Stator Core", "Arnon5-final")
            study.GetMaterial("Stator Core").SetValue("Laminated", 1)
            study.GetMaterial("Stator Core").SetValue("LaminationFactor", 96)

            study.SetMaterialByName("Rotor Core", "Arnon5-final")
            study.GetMaterial("Rotor Core").SetValue("Laminated", 1)
            study.GetMaterial("Rotor Core").SetValue("LaminationFactor", 96)

        else:
            msg = 'Warning: default material is used: DCMagnetic Type/50A1000.'
            print(msg)
            logging.getLogger(__name__).warn(msg)
            study.SetMaterialByName("Stator Core", "DCMagnetic Type/50A1000")
            study.GetMaterial("Stator Core").SetValue("UserConductivityType", 1)
            study.SetMaterialByName("Rotor Core", "DCMagnetic Type/50A1000")
            study.GetMaterial("Rotor Core").SetValue("UserConductivityType", 1)

        study.SetMaterialByName("Coil", "Copper")
        study.GetMaterial("Coil").SetValue("UserConductivityType", 1)

        study.SetMaterialByName("Cage", "Aluminium")
        study.GetMaterial("Cage").SetValue("EddyCurrentCalculation", 1)
        study.GetMaterial("Cage").SetValue("UserConductivityType", 1)
        study.GetMaterial("Cage").SetValue("UserConductivityValue", self.machine_variant.rotor_bar_mat['BarConductivity'])

    def add_circuit(self, app, model, study, bool_3PhaseCurrentSource=True):
        # Circuit - Current Source
        app.ShowCircuitGrid(True)
        study.CreateCircuit()
        JMAG_CIRCUIT_Y_POSITION_BIAS_FOR_CURRENT_SOURCE = 0
        # 4 pole motor Qs=24 dpnv implemented by two layer winding (6 coils). In this case, drive winding has the same slot turns as bearing winding
        def circuit(Grouping, turns, Rs, ampD, ampB, freq, phase=0, CommutatingSequenceD=0, CommutatingSequenceB=0,
                    x=10, y=10 + JMAG_CIRCUIT_Y_POSITION_BIAS_FOR_CURRENT_SOURCE, bool_3PhaseCurrentSource=True):
            study.GetCircuit().CreateSubCircuit("Star Connection", "Star Connection %s" % (Grouping), x, y)
            study.GetCircuit().GetSubCircuit("Star Connection %s" % (Grouping)).GetComponent("Coil1").SetValue(
                "Turn", turns)
            study.GetCircuit().GetSubCircuit("Star Connection %s" % (Grouping)).GetComponent("Coil1").SetValue(
                "Resistance", Rs)
            study.GetCircuit().GetSubCircuit("Star Connection %s" % (Grouping)).GetComponent("Coil2").SetValue(
                "Turn", turns)
            study.GetCircuit().GetSubCircuit("Star Connection %s" % (Grouping)).GetComponent("Coil2").SetValue(
                "Resistance", Rs)
            study.GetCircuit().GetSubCircuit("Star Connection %s" % (Grouping)).GetComponent("Coil3").SetValue(
                "Turn", turns)
            study.GetCircuit().GetSubCircuit("Star Connection %s" % (Grouping)).GetComponent("Coil3").SetValue(
                "Resistance", Rs)
            study.GetCircuit().GetSubCircuit("Star Connection %s" % (Grouping)).GetComponent("Coil1").SetName(
                "CircuitCoil%sU" % (Grouping))
            study.GetCircuit().GetSubCircuit("Star Connection %s" % (Grouping)).GetComponent("Coil2").SetName(
                "CircuitCoil%sV" % (Grouping))
            study.GetCircuit().GetSubCircuit("Star Connection %s" % (Grouping)).GetComponent("Coil3").SetName(
                "CircuitCoil%sW" % (Grouping))

            if bool_3PhaseCurrentSource == True:  # must use this for frequency analysis

                study.GetCircuit().CreateComponent("3PhaseCurrentSource", "CS%s" % (Grouping))
                study.GetCircuit().CreateInstance("CS%s" % (Grouping), x - 4, y + 1)
                study.GetCircuit().GetComponent("CS%s" % (Grouping)).SetValue("Amplitude", ampD + ampB)
                # study.GetCircuit().GetComponent("CS%s"%(Grouping)).SetValue("Frequency", "freq") # this is not needed for freq analysis # "freq" is a variable | 这个本来是可以用的，字符串"freq"的意思是用定义好的变量freq去代入，但是2020/07/07我重新搞Qs=36，p=3的Separate Winding的时候又不能正常工作的，circuit中设置的频率不是freq，而是0。
                study.GetCircuit().GetComponent("CS%s" % (Grouping)).SetValue("Frequency",
                                                                              self.DriveW_Freq)  # this is not needed for freq analysis # "freq" is a variable
                study.GetCircuit().GetComponent("CS%s" % (Grouping)).SetValue("PhaseU",
                                                                              phase)  # initial phase for phase U

                # Commutating sequence is essencial for the direction of the field to be consistent with speed: UVW rather than UWV
                # CommutatingSequenceD == 1 被我定义为相序UVW，相移为-120°，对应JMAG的"CommutatingSequence"为0，嗯，刚好要反一下，但我不改我的定义，因为DPNV那边（包括转子旋转方向）都已经按照这个定义测试好了，不改！
                # CommutatingSequenceD == 0 被我定义为相序UWV，相移为+120°，对应JMAG的"CommutatingSequence"为1，嗯，刚好要反一下，但我不改我的定义，因为DPNV那边（包括转子旋转方向）都已经按照这个定义测试好了，不改！
                if Grouping == 'Torque':
                    JMAGCommutatingSequence = 0
                    study.GetCircuit().GetComponent("CS%s" % (Grouping)).SetValue("CommutatingSequence",
                                                                                  JMAGCommutatingSequence)
                elif Grouping == 'Suspension':
                    JMAGCommutatingSequence = 1
                    study.GetCircuit().GetComponent("CS%s" % (Grouping)).SetValue("CommutatingSequence",
                                                                                  JMAGCommutatingSequence)
            else:
                I1 = "CS%s-1" % (Grouping)
                I2 = "CS%s-2" % (Grouping)
                I3 = "CS%s-3" % (Grouping)
                study.GetCircuit().CreateComponent("CurrentSource", I1)
                study.GetCircuit().CreateInstance(I1, x - 4, y + 3)
                study.GetCircuit().CreateComponent("CurrentSource", I2)
                study.GetCircuit().CreateInstance(I2, x - 4, y + 1)
                study.GetCircuit().CreateComponent("CurrentSource", I3)
                study.GetCircuit().CreateInstance(I3, x - 4, y - 1)

                phase_shift_drive = -120 if CommutatingSequenceD == 1 else 120
                phase_shift_beari = -120 if CommutatingSequenceB == 1 else 120

                func = app.FunctionFactory().Composite()
                f1 = app.FunctionFactory().Sin(ampD, freq,
                                               0 * phase_shift_drive)  # "freq" variable cannot be used here. So pay extra attension here when you create new case of a different freq.
                f2 = app.FunctionFactory().Sin(ampB, freq, 0 * phase_shift_beari)
                func.AddFunction(f1)
                func.AddFunction(f2)
                study.GetCircuit().GetComponent(I1).SetFunction(func)

                func = app.FunctionFactory().Composite()
                f1 = app.FunctionFactory().Sin(ampD, freq, 1 * phase_shift_drive)
                f2 = app.FunctionFactory().Sin(ampB, freq, 1 * phase_shift_beari)
                func.AddFunction(f1)
                func.AddFunction(f2)
                study.GetCircuit().GetComponent(I2).SetFunction(func)

                func = app.FunctionFactory().Composite()
                f1 = app.FunctionFactory().Sin(ampD, freq, 2 * phase_shift_drive)
                f2 = app.FunctionFactory().Sin(ampB, freq, 2 * phase_shift_beari)
                func.AddFunction(f1)
                func.AddFunction(f2)
                study.GetCircuit().GetComponent(I3).SetFunction(func)

            study.GetCircuit().CreateComponent("Ground", "Ground")
            study.GetCircuit().CreateInstance("Ground", x + 2, y + 1)

        # 这里电流幅值中的0.5因子源自DPNV导致的等于2的平行支路数。没有考虑到这一点，是否会对initial design的有效性产生影响？
        # 仔细看DPNV的接线，对于转矩逆变器，绕组的并联支路数为2，而对于悬浮逆变器，绕组的并联支路数为1。

        npb = self.wily.number_parallel_branch
        nwl = self.wily.number_winding_layer  # number of windign layers
        # if self.fea_config_dict['DPNV_separate_winding_implementation'] == True or self.machine_variant.DPNV_or_SEPA == False:
        if self.machine_variant.DPNV_or_SEPA == False:
            # either a separate winding or a DPNV winding implemented as a separate winding
            ampD = 0.5 * (self.DriveW_CurrentAmp / npb + self.BeariW_CurrentAmp)  # 为了代码能被四极电机和二极电机通用，代入看看就知道啦。
            ampB = -0.5 * (
                        self.DriveW_CurrentAmp / npb - self.BeariW_CurrentAmp)  # 关于符号，注意下面的DriveW对应的circuit调用时的ampB前还有个负号！
            if bool_3PhaseCurrentSource != True:
                raise Exception('Logic Error Detected.')
        else:
            '[B]: DriveW_CurrentAmp is set.'
            # case: DPNV as an actual two layer winding
            ampD = self.machine_variant.DriveW_CurrentAmp / npb
            ampB = self.machine_variant.BeariW_CurrentAmp
            if bool_3PhaseCurrentSource != False:
                raise Exception('Logic Error Detected.')

        Function = 'GroupAC' if self.machine_variant.DPNV_or_SEPA == True else 'Torque'
        circuit(Function, self.machine_variant.DriveW_zQ / nwl, bool_3PhaseCurrentSource=bool_3PhaseCurrentSource,
                Rs=self.machine_variant.DriveW_Rs, ampD=ampD,
                ampB=-ampB, freq=self.machine_variant.DriveW_Freq, phase=0,
                CommutatingSequenceD=self.wily.CommutatingSequenceD,
                CommutatingSequenceB=self.wily.CommutatingSequenceB)
        Function = 'GroupBD' if self.machine_variant.DPNV_or_SEPA == True else 'Suspension'
        circuit(Function, self.machine_variant.BeariW_turns / nwl, bool_3PhaseCurrentSource=bool_3PhaseCurrentSource,
                Rs=self.machine_variant.BeariW_Rs, ampD=ampD,
                ampB=+ampB, freq=self.machine_variant.BeariW_Freq, phase=0,
                CommutatingSequenceD=self.wily.CommutatingSequenceD,
                CommutatingSequenceB=self.wily.CommutatingSequenceB,
                x=25)  # CS4 corresponds to uauc (conflict with following codes but it does not matter.)

        # Link FEM Coils to Coil Set
        # if self.fea_config_dict['DPNV_separate_winding_implementation'] == True or self.machine_variant.DPNV_or_SEPA == False:
        if self.machine_variant.DPNV_or_SEPA == False:  # Separate Winding
            def link_FEMCoils_2_CoilSet(Function, l1, l2):
                # link between FEM Coil Condition and Circuit FEM Coil
                for UVW in ['U', 'V', 'W']:
                    which_phase = "Cond-%s-%s" % (Function, UVW)
                    study.CreateCondition("FEMCoil", which_phase)

                    condition = study.GetCondition(which_phase)
                    condition.SetLink("CircuitCoil%s%s" % (Function, UVW))
                    condition.GetSubCondition("untitled").SetName("Coil Set 1")
                    condition.GetSubCondition("Coil Set 1").SetName("delete")
                count = 0
                dict_dir = {'+': 1, '-': 0, 'o': None}
                # select the part to assign the FEM Coil condition
                for UVW, UpDown in zip(l1, l2):
                    count += 1
                    if dict_dir[UpDown] is None:
                        # print 'Skip', UVW, UpDown
                        continue
                    which_phase = "Cond-%s-%s" % (Function, UVW)
                    condition = study.GetCondition(which_phase)
                    condition.CreateSubCondition("FEMCoilData", "%s-Coil Set %d" % (Function, count))
                    subcondition = condition.GetSubCondition("%s-Coil Set %d" % (Function, count))
                    subcondition.ClearParts()
                    layer_symbol = 'LX' if Function == 'Torque' else 'LY'
                    subcondition.AddSet(model.GetSetList().GetSet(f"Coil{layer_symbol}{UVW}{UpDown} {count}"), 0)
                    subcondition.SetValue("Direction2D", dict_dir[UpDown])
                # clean up
                for UVW in ['U', 'V', 'W']:
                    which_phase = "Cond-%s-%s" % (Function, UVW)
                    condition = study.GetCondition(which_phase)
                    condition.RemoveSubCondition("delete")

            link_FEMCoils_2_CoilSet('Torque',
                                    self.dict_coil_connection['layer X phases'],
                                    self.dict_coil_connection['layer X signs'])
            link_FEMCoils_2_CoilSet('Suspension',
                                    self.dict_coil_connection['layer Y phases'],
                                    self.dict_coil_connection['layer Y signs'])
        else:  # DPNV Winding
            # 两个改变，一个是激励大小的改变（本来是200A 和 5A，现在是205A和195A），
            # 另一个绕组分组的改变，现在的A相是上层加下层为一相，以前是用俩单层绕组等效的。

            # Link FEM Coils to Coil Set as double layer short pitched winding
            # Create FEM Coil Condition
            # here we map circuit component `Coil2A' to FEM Coil Condition 'phaseAuauc
            # here we map circuit component `Coil4A' to FEM Coil Condition 'phaseAubud
            for suffix in ['GroupAC',
                           'GroupBD']:  # 仍然需要考虑poles，是因为为Coil设置Set那里的代码还没有更新。这里的2和4等价于leftlayer和rightlayer。
                for UVW in ['U', 'V', 'W']:
                    study.CreateCondition("FEMCoil", 'phase' + UVW + suffix)
                    # link between FEM Coil Condition and Circuit FEM Coil
                    condition = study.GetCondition('phase' + UVW + suffix)
                    condition.SetLink("CircuitCoil%s%s" % (suffix, UVW))
                    condition.GetSubCondition("untitled").SetName("delete")

            count = 0  # count indicates which slot the current rightlayer is in.
            index = 0
            dict_dir = {'+': 1, '-': 0}
            coil_pitch = self.wily.coil_pitch_y  # self.dict_coil_connection[0]
            # select the part (via `Set') to assign the FEM Coil condition
            for UVW, UpDown in zip(self.wily.layer_X_phases, self.wily.layer_X_signs):

                count += 1
                if self.wily.grouping_AC[index] == 1:
                    suffix = 'GroupAC'
                else:
                    suffix = 'GroupBD'
                condition = study.GetCondition('phase' + UVW + suffix)

                # right layer
                condition.CreateSubCondition("FEMCoilData", "Coil Set Layer X %d" % (count))
                subcondition = condition.GetSubCondition("Coil Set Layer X %d" % (count))
                subcondition.ClearParts()
                subcondition.AddSet(model.GetSetList().GetSet("CoilLX%s%s %d" % (UVW, UpDown, count)),
                                    0)  # poles=4 means right layer, rather than actual poles
                subcondition.SetValue("Direction2D", dict_dir[UpDown])

                # left layer
                if coil_pitch <= 0:
                    raise Exception('把永磁电机circuit部分的代码移植过来！')
                if count + coil_pitch <= self.machine_variant.Qs:
                    count_leftlayer = count + coil_pitch
                    index_leftlayer = index + coil_pitch
                else:
                    count_leftlayer = int(count + coil_pitch - self.machine_variant.Qs)
                    index_leftlayer = int(index + coil_pitch - self.machine_variant.Qs)
                # 右层导体的电流方向是正，那么与其串联的一个coil_pitch之处的左层导体就是负！不需要再检查l_leftlayer2了~
                if UpDown == '+':
                    UpDown = '-'
                else:
                    UpDown = '+'
                condition.CreateSubCondition("FEMCoilData", "Coil Set Layer Y %d" % (count_leftlayer))
                subcondition = condition.GetSubCondition("Coil Set Layer Y %d" % (count_leftlayer))
                subcondition.ClearParts()
                subcondition.AddSet(model.GetSetList().GetSet("CoilLY%s%s %d" % (UVW, UpDown, count_leftlayer)),
                                    0)  # poles=2 means left layer, rather than actual poles
                subcondition.SetValue("Direction2D", dict_dir[UpDown])
                index += 1

                # double check
                if self.wily.layer_Y_phases[index_leftlayer] != UVW:
                    raise Exception('Bug in winding diagram.')
            # clean up
            for suffix in ['GroupAC', 'GroupBD']:
                for UVW in ['U', 'V', 'W']:
                    condition = study.GetCondition('phase' + UVW + suffix)
                    condition.RemoveSubCondition("delete")
            # raise Exception('Test DPNV PE.')

        # Condition - Conductor (i.e. rotor winding)
        for ind in range(int(self.machine_variant.Qr)):
            natural_ind = ind + 1
            study.CreateCondition("FEMConductor", "CdctCon %d" % (natural_ind))
            study.GetCondition("CdctCon %d" % (natural_ind)).GetSubCondition("untitled").SetName("Conductor Set 1")
            study.GetCondition("CdctCon %d" % (natural_ind)).GetSubCondition("Conductor Set 1").ClearParts()
            study.GetCondition("CdctCon %d" % (natural_ind)).GetSubCondition("Conductor Set 1").AddSet(
                model.GetSetList().GetSet("Bar %d" % (natural_ind)), 0)

        # Condition - Conductor - Grouping
        study.CreateCondition("GroupFEMConductor", "CdctCon_Group")
        for ind in range(int(self.machine_variant.Qr)):
            natural_ind = ind + 1
            study.GetCondition("CdctCon_Group").AddSubCondition("CdctCon %d" % (natural_ind), ind)

        # Link Conductors to Circuit
        def place_conductor(x, y, name):
            study.GetCircuit().CreateComponent("FEMConductor", name)
            study.GetCircuit().CreateInstance(name, x, y)

        def place_resistor(x, y, name, end_ring_resistance):
            study.GetCircuit().CreateComponent("Resistor", name)
            study.GetCircuit().CreateInstance(name, x, y)
            study.GetCircuit().GetComponent(name).SetValue("Resistance", end_ring_resistance)

        rotor_phase_name_list = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
        X = 40;
        Y = 60;
        #
        if self.machine_variant.PoleSpecificNeutral == True:  # Our proposed pole-specific winding with a neutral plate

            wily_Qr = winding_layout.pole_specific_winding_with_neutral(self.Qr, self.DriveW_poles / 2,
                                                                        self.BeariW_poles / 2,
                                                                        self.spec_input_dict['coil_pitch_y_Qr'])
            for ind, pair in enumerate(wily_Qr.pairs):
                X += -12
                # Y += -12
                if len(pair) != 2:
                    # double layer pole-specific winding with neutral plate

                    # print(f'This double layer rotor winding is goting to be implemented as its single layer equivalent (a coil with {len(pair)} conductors) with the neutral plate structure.\n')

                    for index, k in enumerate(pair):
                        string_conductor = f"Conductor{rotor_phase_name_list[ind]}{index + 1}"
                        place_conductor(X, Y - 9 * index, string_conductor)
                        study.GetCondition("CdctCon %d" % (k)).SetLink(string_conductor)

                        # no end ring resistors to behave like FEMM model
                        study.GetCircuit().CreateInstance("Ground", X - 5, Y - 2)
                        study.GetCircuit().CreateWire(X - 2, Y, X - 5, Y)
                        study.GetCircuit().CreateWire(X - 5, Y, X - 2, Y - 9 * index)
                        study.GetCircuit().CreateWire(X + 2, Y, X + 2, Y - 9 * index)

                    # quit()
                else:
                    # single layer pole-specific winding with neutral plate
                    i, j = pair
                    place_conductor(X, Y, "Conductor%s1" % (rotor_phase_name_list[ind]))
                    place_conductor(X, Y - 9, "Conductor%s2" % (rotor_phase_name_list[ind]))
                    study.GetCondition("CdctCon %d" % (i)).SetLink("Conductor%s1" % (rotor_phase_name_list[ind]))
                    study.GetCondition("CdctCon %d" % (j)).SetLink("Conductor%s2" % (rotor_phase_name_list[ind]))

                    # no end ring resistors to behave like FEMM model
                    study.GetCircuit().CreateWire(X + 2, Y, X + 2, Y - 9)
                    study.GetCircuit().CreateInstance("Ground", X - 5, Y - 2)
                    study.GetCircuit().CreateWire(X - 2, Y, X - 5, Y)
                    study.GetCircuit().CreateWire(X - 5, Y, X - 2, Y - 9)

            if self.End_Ring_Resistance != 0:  # setting a small value to End_Ring_Resistance is a bad idea (slow down the solver). Instead, don't model it
                raise Exception('With end ring is not implemented.')
        else:
            # 下边的方法只适用于Qr是p的整数倍的情况，比如Qr=28，p=3就会出错哦。
            if self.machine_variant.PS_or_SC == True:  # Chiba's conventional pole-specific winding
                if self.machine_variant.DriveW_poles == 2:
                    for i in range(int(self.machine_variant.no_slot_per_pole)):
                        Y += -12
                        place_conductor(X, Y, "Conductor%s1" % (rotor_phase_name_list[i]))
                        # place_conductor(X, Y-3, u"Conductor%s2"%(rotor_phase_name_list[i]))
                        # place_conductor(X, Y-6, u"Conductor%s3"%(rotor_phase_name_list[i]))
                        place_conductor(X, Y - 9, "Conductor%s2" % (rotor_phase_name_list[i]))

                        if self.machine_variant.End_Ring_Resistance == 0:  # setting a small value to End_Ring_Resistance is a bad idea (slow down the solver). Instead, don't model it
                            # no end ring resistors to behave like FEMM model
                            study.GetCircuit().CreateWire(X + 2, Y, X + 2, Y - 9)
                            # study.GetCircuit().CreateWire(X-2, Y-3, X-2, Y-6)
                            # study.GetCircuit().CreateWire(X+2, Y-6, X+2, Y-9)
                            study.GetCircuit().CreateInstance("Ground", X - 5, Y - 2)
                            study.GetCircuit().CreateWire(X - 2, Y, X - 5, Y)
                            study.GetCircuit().CreateWire(X - 5, Y, X - 2, Y - 9)
                        else:
                            raise Exception('With end ring is not implemented.')
                elif self.DriveW_poles == 4:  # poles = 4
                    for i in range(int(self.machine_variant.no_slot_per_pole)):
                        Y += -12
                        place_conductor(X, Y, "Conductor%s1" % (rotor_phase_name_list[i]))
                        place_conductor(X, Y - 3, "Conductor%s2" % (rotor_phase_name_list[i]))
                        place_conductor(X, Y - 6, "Conductor%s3" % (rotor_phase_name_list[i]))
                        place_conductor(X, Y - 9, "Conductor%s4" % (rotor_phase_name_list[i]))

                        if self.End_Ring_Resistance == 0:  # setting a small value to End_Ring_Resistance is a bad idea (slow down the solver). Instead, don't model it
                            # no end ring resistors to behave like FEMM model
                            study.GetCircuit().CreateWire(X + 2, Y, X + 2, Y - 3)
                            study.GetCircuit().CreateWire(X - 2, Y - 3, X - 2, Y - 6)
                            study.GetCircuit().CreateWire(X + 2, Y - 6, X + 2, Y - 9)
                            study.GetCircuit().CreateInstance("Ground", X - 5, Y - 2)
                            study.GetCircuit().CreateWire(X - 2, Y, X - 5, Y)
                            study.GetCircuit().CreateWire(X - 5, Y, X - 2, Y - 9)
                        else:
                            place_resistor(X + 4, Y, "R_%s1" % (rotor_phase_name_list[i]), self.End_Ring_Resistance)
                            place_resistor(X - 4, Y - 3, "R_%s2" % (rotor_phase_name_list[i]),
                                           self.End_Ring_Resistance)
                            place_resistor(X + 4, Y - 6, "R_%s3" % (rotor_phase_name_list[i]),
                                           self.End_Ring_Resistance)
                            place_resistor(X - 4, Y - 9, "R_%s4" % (rotor_phase_name_list[i]),
                                           self.End_Ring_Resistance)

                            study.GetCircuit().CreateWire(X + 6, Y, X + 2, Y - 3)
                            study.GetCircuit().CreateWire(X - 6, Y - 3, X - 2, Y - 6)
                            study.GetCircuit().CreateWire(X + 6, Y - 6, X + 2, Y - 9)
                            study.GetCircuit().CreateWire(X - 6, Y - 9, X - 7, Y - 9)
                            study.GetCircuit().CreateWire(X - 2, Y, X - 7, Y)
                            study.GetCircuit().CreateInstance("Ground", X - 7, Y - 2)
                            # study.GetCircuit().GetInstance(u"Ground", ini_ground_no+i).RotateTo(90)
                            study.GetCircuit().CreateWire(X - 7, Y, X - 6, Y - 9)

                elif self.DriveW_poles == 6:  # poles = 6
                    for i in range(int(self.machine_variant.no_slot_per_pole)):
                        # Y += -3*(self.DriveW_poles-1) # work for poles below 6
                        X += 10  # tested for End_Ring_Resistance==0 only
                        place_conductor(X, Y, "Conductor%s1" % (rotor_phase_name_list[i]))
                        place_conductor(X, Y - 3, "Conductor%s2" % (rotor_phase_name_list[i]))
                        place_conductor(X, Y - 6, "Conductor%s3" % (rotor_phase_name_list[i]))
                        place_conductor(X, Y - 9, "Conductor%s4" % (rotor_phase_name_list[i]))
                        place_conductor(X, Y - 12, "Conductor%s5" % (rotor_phase_name_list[i]))
                        place_conductor(X, Y - 15, "Conductor%s6" % (rotor_phase_name_list[i]))

                        if self.End_Ring_Resistance == 0:  # setting a small value to End_Ring_Resistance is a bad idea (slow down the solver). Instead, don't model it
                            # no end ring resistors to behave like FEMM model
                            study.GetCircuit().CreateWire(X + 2, Y, X + 2, Y - 3)
                            study.GetCircuit().CreateWire(X - 2, Y - 3, X - 2, Y - 6)
                            study.GetCircuit().CreateWire(X + 2, Y - 6, X + 2, Y - 9)
                            study.GetCircuit().CreateWire(X - 2, Y - 9, X - 2, Y - 12)
                            study.GetCircuit().CreateWire(X + 2, Y - 12, X + 2, Y - 15)
                            study.GetCircuit().CreateWire(X - 2, Y, X - 5, Y)
                            study.GetCircuit().CreateWire(X - 5, Y, X - 2, Y - 15)
                            study.GetCircuit().CreateInstance("Ground", X - 5, Y - 2)
                        else:
                            raise Exception(
                                'Not implemented error: pole-specific rotor winding circuit for %d poles are not implemented' % (
                                    im.DriveW_poles))
                else:
                    raise Exception(
                        'Not implemented error: pole-specific rotor winding circuit for %d poles and non-zero End_Ring_Resistance are not implemented' % (
                            im.DriveW_poles))

                for i in range(0, int(self.machine_variant.no_slot_per_pole)):
                    natural_i = i + 1
                    if self.machine_variant.DriveW_poles == 2:
                        study.GetCondition("CdctCon %d" % (natural_i)).SetLink(
                            "Conductor%s1" % (rotor_phase_name_list[i]))
                        study.GetCondition("CdctCon %d" % (natural_i + self.machine_variant.no_slot_per_pole)).SetLink(
                            "Conductor%s2" % (rotor_phase_name_list[i]))
                    elif self.machine_variant.DriveW_poles == 4:
                        study.GetCondition("CdctCon %d" % (natural_i)).SetLink(
                            "Conductor%s1" % (rotor_phase_name_list[i]))
                        study.GetCondition("CdctCon %d" % (natural_i + self.machine_variant.no_slot_per_pole)).SetLink(
                            "Conductor%s2" % (rotor_phase_name_list[i]))
                        study.GetCondition("CdctCon %d" % (natural_i + 2 * self.machine_variant.no_slot_per_pole)).SetLink(
                            "Conductor%s3" % (rotor_phase_name_list[i]))
                        study.GetCondition("CdctCon %d" % (natural_i + 3 * self.machine_variant.no_slot_per_pole)).SetLink(
                            "Conductor%s4" % (rotor_phase_name_list[i]))
                    elif self.DriveW_poles == 6:
                        study.GetCondition("CdctCon %d" % (natural_i)).SetLink(
                            "Conductor%s1" % (rotor_phase_name_list[i]))
                        study.GetCondition("CdctCon %d" % (natural_i + self.machine_variant.no_slot_per_pole)).SetLink(
                            "Conductor%s2" % (rotor_phase_name_list[i]))
                        study.GetCondition("CdctCon %d" % (natural_i + 2 * self.machine_variant.no_slot_per_pole)).SetLink(
                            "Conductor%s3" % (rotor_phase_name_list[i]))
                        study.GetCondition("CdctCon %d" % (natural_i + 3 * self.machine_variant.no_slot_per_pole)).SetLink(
                            "Conductor%s4" % (rotor_phase_name_list[i]))
                        study.GetCondition("CdctCon %d" % (natural_i + 4 * self.machine_variant.no_slot_per_pole)).SetLink(
                            "Conductor%s5" % (rotor_phase_name_list[i]))
                        study.GetCondition("CdctCon %d" % (natural_i + 5 * self.machine_variant.no_slot_per_pole)).SetLink(
                            "Conductor%s6" % (rotor_phase_name_list[i]))
                    else:
                        raise Exception('Not implemented for poles %d' % (self.DriveW_poles))
            else:  # Caged rotor circuit
                dyn_circuit = study.GetCircuit().CreateDynamicCircuit("Cage")
                dyn_circuit.SetValue("AntiPeriodic", False)
                dyn_circuit.SetValue("Bars", int(self.Qr))
                dyn_circuit.SetValue("EndringResistance", self.End_Ring_Resistance)
                dyn_circuit.SetValue("GroupCondition", True)
                dyn_circuit.SetValue("GroupName", "CdctCon_Group")
                dyn_circuit.SetValue("UseInductance", False)
                dyn_circuit.Submit("Cage1", 23, 2)
                study.GetCircuit().CreateInstance("Ground", 25, 1)











            


    


