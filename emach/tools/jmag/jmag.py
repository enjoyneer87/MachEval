from win32com.client import DispatchEx
import os

from ..tool_abc import toolabc as abc
from ..token_draw import TokenDraw

__all__ = []
__all__ += ["JmagDesigner"]


class JmagDesigner(abc.ToolBase, abc.DrawerBase, abc.MakerExtrudeBase, abc.MakerRevolveBase):
    def __init__(self):
        self.jd = None
        self.geometry_editor = None
        self.doc = None
        self.assembly = None
        self.sketch = None
        self.part = None
        self.model = None
        self.study = None
        self.view = None
        self.filepath = None
        self.study_type = None
        self.default_length = None
        self.default_angle = None
        self.visible = True

    # def __del__(self):
    #     self.jd.Quit()

    def open(self, filepath, length_unit='DimMeter', angle_unit='DimDegree'):

        self.default_length = length_unit
        self.default_angle = angle_unit

        file_name, file_extension = os.path.splitext(filepath)

        if file_extension != '.jproj':
            raise TypeError('Incorrect file extension')

        jd_instance = DispatchEx('designerstarter.InstanceManager')
        self.jd = jd_instance.GetNamedInstance(filepath, 0)
        self.set_visibility(self.visible)

        # try:
        #     self.jd.Load(filepath)
        #     self.filepath = filepath
        # except FileNotFoundError:
        curr_dir = os.getcwd()
        print(curr_dir)
        filename = os.path.basename(filepath)
        filepath = curr_dir + '/' + filename
        self.jd.NewProject(filepath)
        self.save_as(filepath)

        self.view = self.jd.View()
        self.jd.GetCurrentModel().RestoreCadLink(True)
        self.geometry_editor = self.jd.CreateGeometryEditor(True)
        self.doc = self.geometry_editor.GetDocument()
        self.assembly = self.doc.GetAssembly()

    def save(self):
        if type(self.filepath) is str:
            self.jd.SaveAs(self.filepath)
        else:
            raise AttributeError('Unable to save file. Use the save_as() function')

    def save_as(self, filepath):
        self.filepath = filepath
        self.save()

    def close(self):
        del self

    def set_visibility(self, visible):
        self.visible = visible
        if self.visible:
            self.jd.Show()
        else:
            self.jd.Hide()

    def draw_line(self, startxy: 'Location2D', endxy: 'Location2D') -> 'TokenDraw':
        pass

    def draw_arc(self, centerxy: 'Location2D', startxy: 'Location2D', endxy: 'Location2D') -> 'TokenDraw':
        pass

    def select(self):
        pass

    def prepare_section(self, cs_token: 'CrossSectToken') -> any:
        pass

    def extrude(self, name, material: str, depth: float) -> any:
        pass

    def revolve(self, name, material: str, center: 'Location2D', axis: 'Location2D', angle: float) -> any:
        pass
