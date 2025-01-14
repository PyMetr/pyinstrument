# --- core.py ---
import logging
logger = logging.getLogger(__name__)
logging.getLogger('pyvisa').setLevel(logging.CRITICAL)
from pyvisa.constants import BufferType
from PySide6.QtCore import QWaitCondition, QMutex
from enum import Enum
from collections.abc import Iterable
from PySide6.QtCore import QObject, Signal, QThread, QTimer
import sys
import numpy as np
import logging
import pyvisa
import random

from enum import IntFlag
from abc import abstractmethod

class Sources(QObject):
    """
    Handles the management and operation of sources for SCPI instruments.

    Attributes:
        source_changed (Signal): Emitted when the list of active sources changes.
    """

    source_changed = Signal(list)

    def __init__(self, sources):
        """
        Initializes the Sources object with the available sources.

        Args:
            sources (list): List of available sources.
        """
        super().__init__()
        self._sources = [source.value if isinstance(source, Enum) else source for source in sources]
        self._source = []
        logger.info("Sources initialized with: %s", self._sources)

    @property
    def source(self):
        """
        Returns the list of active sources.

        Returns:
            list: Active sources.
        """
        return self._source

    @source.setter
    def source(self, sources):
        """
        Sets the active sources from the available sources.

        Args:
            sources (list): List of sources to set as active.
        """
        self._source = [source for source in sources if source in self._sources]
        logger.debug("Active source set to: %s", self._source)
        self.source_changed.emit(self._source)

    @property
    def sources(self):
        """
        Returns the list of available sources.

        Returns:
            list: Available sources.
        """
        return self._sources

    def add_source(self, source):
        """
        Adds a source to the list of active sources if it's available and not already active.

        Args:
            source (str or Enum): Source to add to the active sources.
        """
        source = source.value if isinstance(source, Enum) else source
        if source in self._sources and source not in self._source:
            self._source.append(source)
            logger.info("Added active source: %s", source)
            self.source_changed.emit(self._source)

    def remove_source(self, source):
        """
        Removes a source from the list of active sources if it's currently active.

        Args:
            source (str or Enum): Source to remove from the active sources.
        """
        source = source.value if isinstance(source, Enum) else source
        if source in self._source:
            self._source.remove(source)
            logger.info("Removed active source: %s", source)
            self.source_changed.emit(self._source)

    def set_sources(self, sources):
        """
        Sets the list of active sources from the available sources.

        Args:
            sources (list): List of sources to set as active.
        """
        self._source = [source.value if isinstance(source, Enum) else source for source in sources if source in self._sources]
        logger.debug("Active sources set to: %s", self._source)
        self.source_changed.emit(self._source)

    @staticmethod
    def source_command(command_template=None, formatter=None, single=False, join_str=', '):
        """
        Decorator for source-related commands.

        The `source_command` decorator is used to handle source-related commands in a flexible manner.
        It allows you to specify a command template, source formatting, and whether to handle sources
        individually or collectively.

        Usage Examples:
            @Sources.source_command(":DIGitize {}", single=True)
            def digitize(self, source):
                # Digitizes the specified source individually.
                pass

            @Sources.source_command(":calculate:measurement {}", formatter="'{}'", join_str=', ')
            def calculate_measurement(self, *sources):
                # Calculates the measurement for the specified sources.
                pass

            @Sources.source_command(single=True)
            def custom_function_single(self, source):
                # Performs a custom operation on each source individually.
                pass

            @Sources.source_command()
            def custom_function_multi(self, *sources):
                # Performs a custom operation on multiple sources.
                pass

        Args:
            command_template (str, optional): Template for the SCPI command. Defaults to None.
            formatter (str, optional): Formatter for the sources. Defaults to None.
            single (bool, optional): Whether to handle sources individually. Defaults to False.
            join_str (str, optional): String to join multiple sources. Defaults to ', '.

        Returns:
            function: Decorated function.
        """
        def decorator(func):
            def wrapper(self, *args, **kwargs):
                sources_to_use = self.sources.source if not args else args

                if isinstance(sources_to_use, Enum):
                    sources_to_use = [sources_to_use]
                elif not isinstance(sources_to_use, Iterable) or isinstance(sources_to_use, str):
                    sources_to_use = [sources_to_use]

                cleaned_sources = [source.value if isinstance(source, Enum) else source for source in sources_to_use]

                if formatter:
                    cleaned_sources = [formatter.format(source) for source in cleaned_sources]

                if command_template:
                    if single:
                        for source in cleaned_sources:
                            command = command_template.format(source)
                            logger.debug(f"Executing command: {command}")
                            self.write(command)
                            func(self, source, **kwargs)
                    else:
                        command = command_template.format(join_str.join(cleaned_sources))
                        logger.debug(f"Executing command: {command}")
                        self.write(command)
                        return func(self, *cleaned_sources, **kwargs)
                else:
                    if single:
                        for source in cleaned_sources:
                            func(self, source, **kwargs)
                    else:
                        return func(self, *cleaned_sources, **kwargs)

            return wrapper
        return decorator

class TraceWorker(QThread):
    def __init__(self, func, instance, *args, **kwargs):
        super().__init__()
        self.func = func
        self.instance = instance
        self.args = args
        self.kwargs = kwargs

    def run(self):
        result = self.func(self.instance, *self.args, **self.kwargs)
        self.instance.trace_data_ready.emit(result)

class Trace:
    def __init__(self, data, x_data=None, z_data=None, label=None, color=None, mode=None, visible=True, line_thickness=1.0, line_style='Solid'):
        """
        Initializes a Trace object to store data and attributes for plotting.

        Args:
        label (str): Label for the trace.
        y_data (list or np.array): Primary data points for the trace.
        x_data (list or np.array, optional): X-axis values if different from default range(len(y_data)).
        z_data (list or np.array, optional): Z-axis values for 3D plotting.
        color (str): Color of the trace in hex format.
        visible (bool): Visibility of the trace in the plot.
        line_thickness (float): Thickness of the line in the plot.
        line_style (str): Style of the line (e.g., 'Solid', 'Dash').
        """
        self.data = np.array(data)
        self.x_data = np.array(x_data) if x_data is not None else None
        self.z_data = np.array(z_data) if z_data is not None else None
        self.color = None
        self.label = label if label else f"Trace {id(self)}"
        self.mode = mode
        self.visible = visible
        self.x_range = None
        self.y_range = None
        self.line_thickness = line_thickness
        self.line_style = line_style

    def update_data(self, y_data, x_data=None, z_data=None):
        """Update the trace data."""
        self.y_data = np.array(y_data)
        if x_data is not None:
            self.x_data = np.array(x_data)
        if z_data is not None:
            self.z_data = np.array(z_data)

class Instrument(QObject):
    """
    A comprehensive class for interacting with scientific and industrial instruments through VISA,
    specifically tailored for devices that support the Standard Commands for Programmable Instruments (SCPI) protocol.
    It simplifies the process of establishing connections, sending commands, reading responses, and managing instrument
    status, whether communicating in ASCII or binary format.

    This class is designed to serve as the foundation for specialized instrument control by providing common SCPI
    command support and direct VISA communication capabilities.
    """

    # Signal needed to emit for plotting
    trace_data_ready = Signal(object)
    trace_data_processed = Signal()  # New signal to notify when trace data has been processed

    def __init__(self, resource_string, sources=None, **kwargs):
        """
        Initializes the instrument connection using the provided VISA resource string.

        Parameters:
            resource_string (str): VISA resource string to identify the instrument.
            timeout (int): Timeout period in milliseconds.
            input_buffer_size (int): Size of the input buffer.
            output_buffer_size (int): Size of the output buffer.
            **kwargs: Additional keyword arguments for PyVISA's open_resource method.
        """
        super().__init__()  # Initialize the QObject base class
        self.resource_string = resource_string
        self.rm = pyvisa.ResourceManager()
        self.sources = Sources(sources) if sources else Sources([])
        self.active_trace_threads = []
        self.instrument = None
        self.continuous_mode = False
        self.timer = QTimer()
        self._data_mode = 'ASCII'  # Default to BINARY
        self._data_type = 'B'  # Default data type (e.g., for binary data)
        self.buffer_size = kwargs.pop('buffer_size', 2 ** 16)  # Default buffer size, can be overridden via kwargs
        self.buffer_type = kwargs.pop('buffer_type', BufferType.io_in | BufferType.io_out)  # Default buffer type, can be overridden
        logger.debug(f"Initializing Instrument with resource_string: {resource_string}")

    def set_continuous_mode(self, enabled):
        self.continuous_mode = enabled

    @staticmethod
    def trace_thread(func):
        """A decorator to run trace-related methods in a thread and handle their lifecycle."""
        def wrapper(instance, *args, **kwargs):
            worker = TraceWorker(func, instance, *args, **kwargs)
            worker.start()
            instance.active_trace_threads.append(worker)
            worker.finished.connect(lambda: instance.active_trace_threads.remove(worker))
            return worker
        return wrapper

    @abstractmethod
    def fetch_trace(self):
        """
        Abstract method designed to fetch trace data from the instrument. Implementations should return data as `Trace` objects,
        which encapsulate the data points, optional range or timestamp information, and other metadata.

        The method should support returning data in a format compatible with 'pyqtgraph' plotting functions, primarily focusing
        on arrays or lists. It should be capable of handling non-linear data points and timestamped data, ensuring flexibility
        in data visualization.

        Returns:
            Trace or List[Trace]: A single `Trace` object or a list of `Trace` objects representing the fetched data.

        Notes:
            - If the instrument provides multiple traces, return a list of `Trace` objects.
            - If the instrument provides a single trace, return a single `Trace` object.

        Example usage:
            def fetch_trace(self):
                # Fetch data from the instrument
                data = self.instrument.query_ascii_values("FETCH?")
                
                # Create a Trace object
                trace = Trace(
                    data=data,
                    label="Channel1",
                    units="V",
                    color="#FF5733"
                )
                
                return trace
        
        Trace object parameters:
            - data (np.array or list): The main data points for plotting. np.array is preferred for performance, but list is also supported.
            - x_data (np.array or list, optional): The x-axis values associated with each data point. If not provided, the default range starts from 0.
            - label (str, optional): Label for the trace, used in legends or axes.
            - color (str, optional): Hex code (e.g., '#FF5733') for trace color. If not provided, a default color is assigned.
            - units (str, optional): Units for the data (e.g., 'V', 'A'). Important for axes labeling and data interpretation.
            - line_thickness (float, optional): Thickness of the trace line. Defaults to 1.0.
            - line_style (str, optional): Style of the trace line. Supported values: 'solid', 'dash', 'dot', 'dash-dot'. Defaults to 'solid'.
        """
        pass

    @property
    def data_mode(self):
        """
        Gets the current data format used for instrument communication.

        Returns:
            str: The data mode, either 'ASCII' or 'BINARY'.
        """
        return self._data_mode

    @data_mode.setter
    def data_mode(self, mode):
        """
        Sets the data mode used for instrument communication.

        Args:
            format (str): The data format to be set. Valid options are 'ASCII' or 'BINARY'.

        Raises:
            ValueError: If an invalid data format is provided.
        """
        if mode.upper() not in ['ASCII', 'BINARY']:
            raise ValueError("Invalid data format. Only 'ASCII' or 'BINARY' are supported.")
        self._data_mode = mode.upper()

    @property
    def data_type(self):
        """
        Gets the current data type used for binary data format.

        Returns:
            str: The data type, corresponding to Python struct module format characters.
        """
        return self._data_type

    @data_type.setter
    def data_type(self, type):
        """
        Sets the data type used for binary data format. This type is aligned with Python's struct module format characters.

        Args:
            type (str): The data type to be set. Valid types are:
                        'B' (unsigned byte), 'b' (signed byte),
                        'H' (unsigned short), 'h' (signed short),
                        'I' (unsigned int), 'i' (signed int),
                        'Q' (unsigned long long), 'q' (signed long long),
                        'f' (float), 'd' (double).

        Raises:
            ValueError: If an invalid data type is provided.
        """
        valid_types = ['B', 'b', 'H', 'h', 'I', 'i', 'Q', 'q', 'f', 'd'] 
        if type not in valid_types:
            raise ValueError(f"Invalid data type. Supported types are: {', '.join(valid_types)}")
        self._data_type = type

    class Status(IntFlag):
        """
        Event Status Register Bits for SCPI Instruments.

        Each bit in the status register represents a specific status or error condition.
        These are defined according to the IEEE 488.2 standard for SCPI instruments.
        """

        OPC = 1 << 0  # Operation Complete
        """Operation complete bit, set when an operation is finished."""

        RQL = 1 << 1  # Request Control
        """Request control bit, indicates a device is requesting control."""

        QYE = 1 << 2  # Query Error
        """Query error bit, set when there is a syntax error in a query command."""

        DDE = 1 << 3  # Device Dependent Error
        """Device dependent error bit, indicates an error specific to the device's operation."""

        EXE = 1 << 4  # Execution Error
        """Execution error bit, set when there is an error in executing a command."""

        CME = 1 << 5  # Command Error
        """Command error bit, set when there is a syntax error in a command."""

        URQ = 1 << 6  # User Request
        """User request bit, set when there is a user request for service."""

        PON = 1 << 7  # Power On
        """Power on bit, set when the device is first powered on or reset."""

    def open(self):
        """
        Opens a connection to the instrument.
        """
        self.instrument = self.rm.open_resource(self.resource_string)
        self.instrument.read_termination = '\n'
        self.instrument.write_termination = '\n'
        self.instrument.timeout = 5000
        logger.debug("Instrument session opened and buffer size set.")

    def close(self):
        """
        Opens a connection to the instrument.
        """
        self.instrument.close()
        logger.debug("Instrument session closed")

    def write(self, command):
        """
        Sends a command to the instrument.
        
        Parameters:
            command (str): The SCPI command to be executed by the instrument.
        """
        try:
            self.instrument.write(command)
            logger.debug(f"Command sent: {command}")
        except (pyvisa.VisaIOError, AttributeError) as e:
            logger.exception(f"Failed to send command '{command}' to the instrument: {e}")
            raise

    def read(self):
        """
        Reads the response from the instrument.
        
        Returns:
            str: The raw response from the instrument.
        """
        try:
            response = self.instrument.read().strip()
            logger.debug(f"Response received: {response}")
            return response
        except pyvisa.VisaIOError as e:
            logger.exception("Failed to read response from the instrument: {e}")
            raise

    def query(self, command):
        """
        Sends a command to the instrument and reads its response.
        
        Parameters:
            command (str): The SCPI command for which a response is expected.
        
        Returns:
            str: The instrument's response to the command.
        """
        self.write(command)
        response = self.read()
        return response
    
    def query_ascii_values(self, command, container=np.array, converter='f', separator=','):
        """
        Sends a command to the instrument and reads its ASCII response, returning the data in the specified container format.
        
        Parameters:
            command (str): The SCPI command for which a response is expected.
            container (type, optional): The type of container to store the ASCII data. Defaults to numpy.array.
            converter (str, callable, optional): Converter used to parse the ASCII data. Defaults to 'f'.
            separator (str, optional): Separator used in the ASCII data. Defaults to ','.
        
        Returns:
            container: The ASCII data read from the instrument, converted into the specified container format.
        """
        response = self.instrument.query_ascii_values(command, container=container, converter=converter, separator=separator)
        logger.debug(f"ASCII query sent: {command}, received: {response[:10]}")
        return response

    def query_binary_values(self, command, datatype='f', is_big_endian=False, container=np.array):
        """
        Sends a command to the instrument and reads a binary response.
        
        Parameters:
            command (str): The SCPI command for which a binary response is expected.
            datatype (str): The type of data to expect ('b', 'h', 'i', 'f', etc.).
            is_big_endian (bool): True for big endian data, False for little endian.
            container (type): The type of container to store the binary data.
        
        Returns:
            container: The binary data read from the instrument.
        """
        try:
            response = self.instrument.query_binary_values(command, datatype=datatype, container=container, is_big_endian=is_big_endian)
            logger.debug(f"Binary query sent: {command}, received: {response[:10]}")
            return response
        except (pyvisa.VisaIOError, ValueError) as e:
            logger.exception(f"Failed to query binary values with '{command}': {e}")
            raise
    
    # TODO: Pull lower level query functions out of the data property and replace with read and write data
    def read_data(self, command, data_format='BINARY', container=np.array):
        """
        Reads data from the instrument using the specified command and format.

        Args:
            command (str): The SCPI command to fetch the data.
            data_format (str, optional): The format of the data ('ASCII' or 'BYTE'). Defaults to 'BYTE'.
            container (type, optional): The container type to store the fetched data, e.g., numpy.array.

        Returns:
            The fetched data, processed into the specified container format.
        """
        if data_format == 'BINARY':
            # For binary data
            data = self.query_binary_values(command, container=container)
        elif data_format == 'ASCII':
            # For ASCII data
            data = self.query_ascii_values(command, container=container)
        else:
            raise ValueError("Unsupported data format specified.")

        return data
    
    def write_data(self, command, data, data_format='BINARY', container=np.array):
        """
        Sends data to the instrument using the specified command and format.

        Args:
            command (str): The SCPI command to send the data.
            data: The data to be sent to the instrument. Could be in various formats (e.g., list, numpy.array).
            data_format (str, optional): The format of the data being sent ('ASCII' or 'BYTE'). Defaults to 'BYTE'.
            container (type, optional): The container type of the data being sent, e.g., numpy.array. This is useful for formatting the data before sending.

        """
        if data_format == 'BINARY':
            # For binary data
            self.write_binary_values(command, data, container=container)
        elif data_format == 'ASCII':
            # For ASCII data
            self.write_ascii_values(command, data, container=container)
        else:
            raise ValueError("Unsupported data format specified.")
        
    def identity(self):
        """
        Sends a request to the instrument to identify itself. This usually includes the manufacturer, 
        model number, serial number, and firmware version. It's like asking, "Who are you?"

        Returns:
            str: The identification string returned by the instrument.
        """
        return self.query("*IDN?")
    
    def status(self):
        """
        Queries the Event Status Register (ESR) to decode and return the current instrument status.
        
        Returns:
            dict: A dictionary representing the status of various ESR bits.
        """
        esr_value = int(self.query("*ESR?"))
        status = {bit.name: bool(esr_value & bit.value) for bit in Instrument.Status}
        logger.debug(f"Instrument status: {status}")
        return status
    
    def clear_status(self):
        """
        Resets the instrument's status and error queue to clear out any errors and get it back to its 
        startup condition. Think of it as the instrument taking a deep breath and starting fresh.
        """
        self.write("*CLS")

    def reset(self):
        """
        Resets the instrument to its factory default settings. It's the control-alt-delete for when you 
        want to wipe the slate clean and start over.
        """
        self.write("*RST")

    def set_service_request(self, mask):
        """
        Configures the instrument to enable certain status events to generate service requests (SRQ). 
        It's like setting up push notifications for the events you actually care about.

        Parameters:
            mask (int): A bit mask that defines which status events will trigger an SRQ.
        """
        self.write(f"*ESE {mask}")

    def get_service_request(self):
        """
        Retrieves the current settings of the Service Request Enable (SRE) register, which determines 
        what events will trigger a service request.

        Returns:
            int: The bit mask of the SRE register's current settings.
        """
        return int(self.query("*ESE?"))

    def get_event_status(self):
        """
        Polls the Event Status Register (ESR) of the instrument to check for any status events that 
        have occurred. It's like checking your notifications to see what's happened.

        Returns:
            int: The bit mask of the ESR, indicating which events have occurred.
        """
        return int(self.query("*ESR?"))

    def operation_complete(self):
        """
        Instructs the instrument to set the Operation Complete (OPC) bit in the Event Status Register 
        once all pending operations have finished. It's a way to tell the instrument, "Hit me up when 
        you're done with what you're doing."
        """
        self.write("*OPC")

    def query_operation_complete(self):
        """
        Asks the instrument if it has finished processing all pending operations. This method queries the 
        Operation Complete (OPC) bit and is useful for synchronization in automated test sequences.

        Returns:
            str: '1' when the instrument has completed all pending operations.
        """
        return self.query("*OPC?")

    def save_setup(self, value):
        """
        Saves the current configuration of the instrument to a specified memory location. It's like 
        taking a snapshot of your current setup so you can return to it later.

        Parameters:
            value (int): The memory location where the instrument's state will be saved.
        """
        self.write(f"*SAV {value}")
    
    @staticmethod
    def list_instruments(query='?*::INSTR'):
        """
        Lists all the connected instruments matching the query filter.

        Parameters:
            query (str): Filter pattern using VISA Resource Regular Expression syntax.

        Returns:
            tuple: A tuple containing a dict of unique instruments keyed by their IDN response,
                and a list of resources that failed to query.
        """
        rm = pyvisa.ResourceManager()
        resources = rm.list_resources(query)
        unique_instruments = {}
        failed_queries = []

        for resource in resources:
            try:
                with rm.open_resource(resource) as inst:
                    idn = inst.query("*IDN?").strip()
                    unique_key = f"{resource}: {idn}"
                    unique_instruments[unique_key] = resource
            except pyvisa.VisaIOError as e:
                failed_queries.append((resource, str(e)))

        return unique_instruments, failed_queries
    
    @staticmethod
    def select_instrument(filter='?*::INSTR'):
        """
        Presents a list of connected instruments filtered by the query and prompts the user to select one.

        Parameters:
            filter (str): Filter pattern to identify the instruments.

        Returns:
            str: The selected resource string of the instrument.
        """
        unique_instruments, failed_queries = Instrument.list_instruments(filter)

        if not unique_instruments:
            logger.error("No instruments found. Check your connections and try again.")
            sys.exit(1)

        print("\nConnected Instruments:")
        for idx, (unique_key, resource) in enumerate(unique_instruments.items(), start=1):
            print(f"{idx}. {unique_key}")

        if failed_queries:
            logger.warning("\nFailed to query some instruments:")
            for resource, error in failed_queries:
                logger.info(f"{resource}: {error}")

        selection = input("\nSelect an instrument by number (or 'exit' to quit): ")
        if selection.lower() == 'exit':
            sys.exit(0)

        try:
            selected_index = int(selection) - 1
            if selected_index < 0 or selected_index >= len(unique_instruments):
                raise ValueError
        except ValueError:
            print("Invalid selection. Please enter a number from the list.")
            return Instrument.select_resources(filter)

        selected_key = list(unique_instruments.keys())[selected_index]
        return unique_instruments[selected_key]
    
class Subsystem:
    """
    Base class for creating instrument subsystems, supporting both simple and indexed instantiation, 
    and enabling nested subsystem command prefix cascading.

    Attributes:
        instr (Instrument): Reference to the parent instrument or subsystem. This attribute 
                              facilitates communication with the parent object.
        cmd_prefix (str): The SCPI command prefix associated with the subsystem. This prefix is 
                          used to construct full SCPI commands for property interactions.
    """

    def __init__(self, instr, cmd_prefix="", index=None):
        """
        Initializes a Subsystem instance.

        Args:
            parent (Instrument or Subsystem): The parent instrument or subsystem this instance belongs to.
            cmd_prefix (str): The command prefix specific to this subsystem. It's used as the base for constructing SCPI commands.
            index (int, optional): If provided, it specifies the index of this instance within an indexed subsystem setup. 
                                   This index is appended to the command prefix.
        """
        self.instr = instr
        logger.debug(f"Initializing subsystem with instrument {instr}, prefix {cmd_prefix}, and index {index}")
        # Handle cascading of command prefixes for nested subsystems
        self.cmd_prefix = f"{instr.cmd_prefix}{cmd_prefix}" if hasattr(instr, 'cmd_prefix') else cmd_prefix
        if index is not None:
            self.cmd_prefix += str(index)

    @classmethod
    def build(cls, instr, cmd_prefix, indices=None):
        """
        Class method to instantiate subsystems. This method simplifies the creation process by automatically handling
        both single and indexed instances of subsystems.

        Args:
            parent (Instrument or Subsystem): The parent object to which the new subsystem instance(s) will belong.
            cmd_prefix (str): The SCPI command prefix for the subsystem being created.
            indices (int, optional): The number of indexed instances to create. If None, a single instance is created without indexing.

        Returns:
            Subsystem or list of Subsystem: A single instance of the subsystem if 'indices' is None, 
                                             or a list of indexed subsystem instances if 'indices' is provided.
        """
        if indices is None:
            logger.debug(f"Build method returning single instance")
            # Creating a single instance without indexing
            return cls(instr, cmd_prefix)
        else:
            # Creating multiple indexed instances
            logger.debug(f"Build method creating {indices} instances")
            return [cls(instr, cmd_prefix, index=idx) for idx in range(1, indices + 1)]
