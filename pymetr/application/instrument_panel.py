#  --- instrument_manager.py ------
import logging
logger = logging.getLogger()
from datetime import datetime
from pyqtgraph.parametertree import Parameter, ParameterTree
from PySide6.QtCore import Signal, Qt, Slot, QTimer
from PySide6.QtWidgets import QVBoxLayout, QDockWidget, QPushButton, QWidget, QApplication

from pymetr.core import Instrument
from pymetr.application.instrument_manager import InstrumentManager

class InstrumentPanel(QDockWidget):
    instrument_connected = Signal(str)
    instrument_disconnected = Signal(str)
    trace_data_ready = Signal(object)
    continuous_mode_changed = Signal(bool)
    plot_update_requested = Signal()

    def __init__(self, instrument_manager, parent=None):
        super().__init__(parent)
        self.instrument_manager = instrument_manager
        self.instrument_manager.parameter_updated.connect(self.handle_parameter_update)
        self.instrument_manager.source_updated.connect(self.handle_source_update)
        self.widget = QWidget()
        self.layout = QVBoxLayout(self.widget)
        self.setWidget(self.widget)
        self.instruments = {}  # Dictionary to store connected instruments
        self.plot_mode = 'Single'
        self.color_palette = ['#5E57FF', '#4BFF36', '#F23CA6', '#FF9535', '#02FEE4', '#2F46FA', '#FFFE13', '#55FC77']
        self.continuous_mode = False
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self.request_plot_update)

    def request_plot_update(self):
        self.plot_update_requested.emit()

    def setup_parameters(self, parameters):
        """
        Receives a parameter tree and displays it within the dock.
        """
        logger.debug(f"Setting up parameters")
        self.parameters = parameters
        self.parameterTree = ParameterTree()
        self.layout.addWidget(self.parameterTree)
        self.parameterTree.setAlternatingRowColors(True)
        self.parameterTree.setParameters(parameters, showTop=True)
        self.parameterTree.setDragEnabled(True)  # Enable drag functionality
        self.parameterTree.setAcceptDrops(True)  # Enable drop functionality

    def add_action_button(self, button_text, handler_function):
        """
        Adds an action button to the instrument dock.

        Args:
            button_text (str): The text to display on the button.
            handler_function (callable): The function to be called when the button is clicked.
        """
        logger.debug(f"Adding action button: {button_text}")
        button = QPushButton(button_text)
        button.clicked.connect(lambda: handler_function())
        self.layout.addWidget(button)

    def setup_parameter_tree(self, instrument, unique_id):
        instr_data = instrument['instr_data']
        self.parameters_dict = instr_data['parameter_tree']
        self.path_map = instrument['path_map']
        self.parameters = Parameter.create(name=unique_id, type='group', children=self.parameters_dict)
        self.setup_parameters(self.parameters)
        self.parameters.sigTreeStateChanged.connect(self.create_parameter_change_handler(unique_id))

        def update_param_attributes(param_dict):
            if 'access' in param_dict:
                param_dict['readonly'] = param_dict['access'] != 'write'
            if 'range' in param_dict:
                param_dict['limits'] = param_dict['range']
            if 'units' in param_dict:
                param_dict['units'] = param_dict['units']
            for child_dict in param_dict.get('children', []):
                update_param_attributes(child_dict)

        for param_dict in self.parameters_dict:
            update_param_attributes(param_dict)

    def setup_method_buttons(self, gui_methods_dict, instr):
        for method_name, method_info in gui_methods_dict.items():
            method_func = getattr(instr, method_name)
            self.add_action_button(method_name, method_func)

    def setup_sources_group(self, sources_list):
        sources_group = {
            'name': 'Sources',
            'type': 'group',
            'children': [{'name': source, 'type': 'bool', 'value': False} for source in sources_list]
        }
        self.parameters_dict.insert(0, sources_group)

    def create_parameter_change_handler(self, unique_id):
        def parameter_changed(param, changes):
            for param, change, data in changes:
                param_name = param.name()
                logger.debug(f"Parameter changed: {param_name}, Change: {change}, Data: {data}")

                # Check if the parameter type is 'action' to handle method execution
                if param.opts.get('type') == 'action':
                    if change == 'activated':  # Ensure the change type is an action activation
                        logger.debug(f"Action parameter activated: {param_name}")
                        # Dynamically find and call the associated method on the instrument
                        if hasattr(self.instrument_manager.connected_instruments[unique_id]['instrument'], param_name):
                            method = getattr(self.instrument_manager.connected_instruments[unique_id]['instrument'], param_name)
                            method()  # Execute the method
                            logger.debug(f"Executed action method: {param_name}")
                        else:
                            logger.error(f"No method found for action parameter: {param_name}")

                # Check if the parameter is in the "Sources" group
                elif param.parent() and param.parent().name() == "Sources":
                    logger.debug(f"Source {param_name} changed to {data}")
                    # Handle the source checkbox state change here
                    if data:
                        self.instrument_manager.instruments[unique_id]['instance'].sources.add_source(param_name)
                    else:
                        self.instrument_manager.instruments[unique_id]['instance'].sources.remove_source(param_name)
                # For non-action parameters, handle them as usual
                else:    
                    full_param_path = self.instrument_manager.construct_parameter_path(param).lstrip(unique_id)
                    full_param_path = full_param_path.lstrip(".")  
                    logger.debug(f"Constructed full parameter path: {full_param_path}")

                    path_map = self.instrument_manager.instruments[unique_id]['path_map']
                    property_path = path_map.get(full_param_path)
                    logger.debug(f"Property path from map: {property_path}")

                    if property_path:
                        # Use existing logic to update the property based on its path
                        self.instrument_manager.update_instrument(property_path, data, unique_id)
                    else:
                        logger.error(f"Property path missing for parameter: {param_name}")
        return parameter_changed

    def handle_parameter_update(self, unique_id, param_path, value):
        # Find and update the parameter in your parameter tree
        param = self.find_parameter_by_path(param_path)
        if param:
            param.setValue(value)

    def find_parameter_by_path(self, param_path):
        # Split path and find parameter based on path elements
        parts = param_path.split('.')
        current_params = self.parameters  # Assuming this is the root of your ParameterTree
        for part in parts:
            current_params = next((p for p in current_params.children() if p.name() == part), None)
            if current_params is None:
                return None
        return current_params
    
    def handle_source_update(self, unique_id, source_name, is_selected):
        # TODO: Fix Oscilloscope here. 
        source_param_path = f"Oscilloscope.Sources.{source_name}"
        param = self.find_parameter_by_path(source_param_path)
        if param:
            param.setValue(is_selected)
            logger.debug(f"Updated source '{source_name}' to state: {is_selected}")
        else:
            logger.error(f"Source parameter '{source_name}' not found in parameter tree")

    def setup_instrument_panel(self, instrument, unique_id):
        logger.debug(f"Setting up instrument panel for {unique_id}")
        self.unique_id = unique_id
        self.setup_method_buttons(instrument['gui_methods'], instrument['instance'])
        self.setup_parameter_tree(instrument, unique_id)
        self.setup_sources_group(instrument['sources'])

        self.acquire_button = QPushButton("Acquire Data")
        self.acquire_button.setStyleSheet(f"background-color: {self.color_palette[0]}; color: #333333; font-weight: bold;")  # Set initial color (blue)
        self.acquire_button.clicked.connect(instrument['instance'].fetch_trace)  # Initially connect to fetch_trace
        logger.debug("Acquire button initially connected to fetch_trace")
        self.layout.addWidget(self.acquire_button)

        syncInstrumentButton = QPushButton(f"Sync Settings")
        syncInstrumentButton.setStyleSheet(f"background-color: {self.color_palette[3]}; color: #333333; font-weight: bold;")  # Set initial color (yellow)
        syncInstrumentButton.clicked.connect(lambda: self.instrument_manager.synchronize_instrument(unique_id))
        self.layout.addWidget(syncInstrumentButton)

        instrument['instance'].trace_data_ready.connect(self.on_trace_data_ready)

    def on_trace_data_ready(self, trace_data):
        logger.debug("Received trace data")
        # QApplication.processEvents()
        self.trace_data_ready.emit(trace_data)  # Emit the trace_data_ready signal

    def toggle_acquisition(self, instrument_instance):
        logger.debug(f"Toggling acquisition for {self.unique_id}")

        self.continuous_mode = not self.continuous_mode
        logger.debug(f"Setting continuous mode to {self.continuous_mode} for instrument {instrument_instance}")

        instrument_instance.set_continuous_mode(self.continuous_mode)
        logger.debug(f"Emitting continuous_mode_changed signal with value {self.continuous_mode}")

        self.continuous_mode_changed.emit(self.continuous_mode)
        self.update_acquire_button(instrument_instance)

        if self.continuous_mode and self.plot_mode == 'Run':
            logger.debug(f"Starting continuous update timer")
            # self.start_continuous_update_timer()
            instrument_instance.fetch_trace()
        else:
            logger.debug(f"Stopping continuous update timer")
            # self.stop_continuous_update_timer()

    def start_continuous_update_timer(self):
        self.update_timer.start(20)  # Update the plot at 50 fps (1000 ms / 50 fps = 20 ms)

    def stop_continuous_update_timer(self):
        self.update_timer.stop()

    def update_acquire_button(self, instrument_instance):
        logger.debug(f"Updating acquire button for {self.unique_id}")
        if self.plot_mode == 'Run':
            logger.debug("Plot mode is 'Run'")
            self.acquire_button.setCheckable(True)
            self.acquire_button.setText("Stop" if self.continuous_mode else "Run")

            # Set the acquire button color and text color based on the text
            if self.continuous_mode:
                self.acquire_button.setStyleSheet(
                    f"background-color: {self.color_palette[2]}; color: #333333; font-weight: bold;"  # Red color, white text
                )
            else:
                self.acquire_button.setStyleSheet(
                    f"background-color: {self.color_palette[1]}; color: #333333; font-weight: bold;"  # Green color, dark gray text
                )

            self.acquire_button.clicked.disconnect()  # Disconnect the previous signal
            logger.debug("Disconnected previous signal from acquire button")
            self.acquire_button.clicked.connect(lambda: self.toggle_acquisition(instrument_instance))
            logger.debug("Connected acquire button to toggle_acquisition")
        else:
            logger.debug("Plot mode is not 'Run'")
            self.acquire_button.setCheckable(False)
            self.acquire_button.setText("Acquire Data")
            self.acquire_button.setStyleSheet(
                f"background-color: {self.color_palette[0]}; color: #333333;"  # Blue color, white text
            )
            self.acquire_button.clicked.disconnect()  # Disconnect the previous signal
            logger.debug("Disconnected previous signal from acquire button")
            self.acquire_button.clicked.connect(instrument_instance.fetch_trace)
            logger.debug("Connected acquire button to fetch_trace")

    @Slot(str)
    def set_plot_mode(self, mode):
        logger.debug(f"Setting plot mode to {mode}")
        self.plot_mode = mode
        instrument_instance = self.instrument_manager.instruments[self.unique_id]['instance']
        self.update_acquire_button(instrument_instance)


if __name__ == "__main__":
    from PySide6.QtWidgets import QApplication, QMainWindow
    from PyMetr import Instrument
    import sys

    class MainWindow(QMainWindow):
        def __init__(self):
            super().__init__()
            self.setWindowTitle("Instrument Control")
            self.setGeometry(100, 100, 800, 600)

            self.instrument_manager = InstrumentManager()
            self.instrument_panel = None

            self.init_ui()

        def init_ui(self):
            resource = Instrument.select_instrument("TCPIP?*::INSTR")
            instrument, unique_id = self.instrument_manager.initialize_instrument(resource)
            if instrument:
                self.instrument_panel = InstrumentPanel(self.instrument_manager)
                self.instrument_panel.setup_instrument_panel(instrument, unique_id)
                self.addDockWidget(Qt.RightDockWidgetArea, self.instrument_panel)

    sys.argv += ['-platform', 'windows:darkmode=2']
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    main_window = MainWindow()
    main_window.show()
    sys.exit(app.exec())