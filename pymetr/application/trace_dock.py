# --- trace_dock.py ---
import numpy as np
import pyqtgraph as pg
from PySide6.QtWidgets import QWidget, QVBoxLayout, QPushButton, QDockWidget, QComboBox
from PySide6.QtCore import QObject, Signal, Qt

class TraceManager(QObject):
    traceDataChanged = Signal(object)

    def __init__(self):
        super().__init__()
        self.traces = []
        self.plot_mode = 'Add'
        self.trace_mode = 'Group'  # Add this line

    def add_trace(self, trace):
        if self.plot_mode == "Replace":
            self.traces.clear()
        trace.mode = self.trace_mode 
        self.traces.append(trace)
        self.emit_trace_data()

    def remove_trace(self, trace):
        if trace in self.traces:
            self.traces.remove(trace)
            self.emit_trace_data()

    def emit_trace_data(self):
        trace_data = {trace.label: {
            'label': trace.label,
            'color': trace.color,
            'mode': trace.mode,
            'data': trace.data.tolist(),
            'visible': trace.visible,
            'line_thickness': trace.line_thickness,
            'line_style': trace.line_style
        } for trace in self.traces}
        self.traceDataChanged.emit(trace_data)

class TraceDock(QDockWidget):

    traceModeChanged = Signal(str)  # Add this line
    roiPlotEnabled = Signal(bool)

    def __init__(self, parent=None):
        super().__init__("Trace Settings", parent)
        self.setMinimumWidth(200) 
        self.setAllowedAreas(Qt.RightDockWidgetArea)

        self.trace_manager = TraceManager()

        self.dock_widget = QWidget()
        self.dock_layout = QVBoxLayout(self.dock_widget)

        self.plot_mode_combo_box = QComboBox()
        self.plot_mode_combo_box.addItems(["Add", "Replace"])
        self.plot_mode_combo_box.currentIndexChanged.connect(self.on_plot_mode_changed)
        self.dock_layout.addWidget(self.plot_mode_combo_box)

        self.trace_mode_combo_box = QComboBox()
        self.trace_mode_combo_box.addItems(["Group", "Isolate"])
        self.trace_mode_combo_box.currentIndexChanged.connect(self.on_trace_mode_changed)
        self.dock_layout.addWidget(self.trace_mode_combo_box)
        self.trace_mode_combo_box.setCurrentText(self.trace_manager.trace_mode)

        self.roi_plot_toggle = QPushButton("ROI Plot")
        self.roi_plot_toggle.setCheckable(True)
        self.roi_plot_toggle.setChecked(False)
        self.roi_plot_toggle.toggled.connect(self.on_roi_plot_toggled)
        self.dock_layout.addWidget(self.roi_plot_toggle)

        self.trace_parameter_tree = pg.parametertree.ParameterTree()
        self.dock_layout.addWidget(self.trace_parameter_tree)

        self.setWidget(self.dock_widget)

        self.trace_manager.traceDataChanged.connect(self.update_parameter_tree)

    def on_roi_plot_toggled(self, checked):
        self.roiPlotEnabled.emit(checked)

    def on_plot_mode_changed(self, index):
        plot_mode = self.plot_mode_combo_box.itemText(index)
        self.trace_manager.plot_mode = plot_mode
        self.trace_manager.emit_trace_data()

    def on_trace_mode_changed(self, index):
        trace_mode = self.trace_mode_combo_box.itemText(index)
        self.traceModeChanged.emit(trace_mode)  # Update this line
        self.trace_manager.trace_mode = trace_mode  # Add this line

    def update_parameter_tree(self, trace_data):
        self.trace_parameter_tree.clear()
        for trace_id, trace_info in trace_data.items():
            trace_param = pg.parametertree.Parameter.create(name=trace_id, type='group', children=[
                {'name': 'Label', 'type': 'str', 'value': trace_info['label']},
                {'name': 'Visible', 'type': 'bool', 'value': trace_info['visible']},
                {'name': 'Color', 'type': 'color', 'value': trace_info['color']},
                {'name': 'Mode', 'type': 'list', 'limits': ['Group', 'Isolate'], 'value': trace_info['mode']},
                {'name': 'Extra', 'type': 'group', 'expanded': False, 'children': [
                    {'name': 'Line Thickness', 'type': 'float', 'value': trace_info.get('line_thickness', 1.0), 'step': 0.1, 'limits': (0.1, 10.0)},
                    {'name': 'Line Style', 'type': 'list', 'limits': ['Solid', 'Dash', 'Dot', 'Dash-Dot'], 'value': trace_info.get('line_style', 'Solid')}
                ]},
                {'name': 'Delete', 'type': 'action'}
            ])
            trace_param.child('Delete').sigActivated.connect(lambda _, tid=trace_id: self.remove_trace(tid))
            trace_param.child('Label').sigValueChanged.connect(lambda param, val, tid=trace_id: self.update_trace_label(tid, val))
            trace_param.child('Visible').sigValueChanged.connect(lambda param, val, tid=trace_id: self.update_trace_parameter(tid, 'visible', val))
            trace_param.child('Color').sigValueChanged.connect(lambda param, val, tid=trace_id: self.update_trace_parameter(tid, 'color', val))
            trace_param.child('Mode').sigValueChanged.connect(lambda param, val, tid=trace_id: self.update_trace_parameter(tid, 'mode', val))
            trace_param.child('Extra').child('Line Thickness').sigValueChanged.connect(lambda param, val, tid=trace_id: self.update_trace_parameter(tid, 'line_thickness', val))
            trace_param.child('Extra').child('Line Style').sigValueChanged.connect(lambda param, val, tid=trace_id: self.update_trace_parameter(tid, 'line_style', val))
            self.trace_parameter_tree.addParameters(trace_param)

    def update_trace_label(self, trace_id, label):
        for trace in self.trace_manager.traces:
            if trace.label == trace_id:
                trace.label = label
                self.trace_manager.emit_trace_data()
                break

    def update_trace_parameter(self, trace_id, parameter, value):
        for trace in self.trace_manager.traces:
            if trace.label == trace_id:
                setattr(trace, parameter, value)
                if parameter == 'color' and trace.mode == 'Isolate':
                    axis = self.parent().trace_axes.get(trace)  # Access trace_axes from the MainWindow instance
                    if axis is not None:
                        axis.setPen(value)
                self.trace_manager.emit_trace_data()
                break

    def remove_trace(self, trace_id):
        for trace in self.trace_manager.traces:
            if trace.label == trace_id:
                self.trace_manager.remove_trace(trace)
                break
