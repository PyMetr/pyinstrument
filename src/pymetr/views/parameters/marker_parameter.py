from typing import Optional, Any, Tuple
from PySide6.QtWidgets import QWidget, QHBoxLayout, QLabel, QMenu
from PySide6.QtCore import Qt, QPointF
from PySide6.QtGui import QPainter, QColor, QPen
from pyqtgraph.parametertree import Parameter

from .base import ModelParameter, ModelParameterItem, ParameterWidget
from pymetr.core.logging import logger
from pymetr.models import Marker

class MarkerPreviewWidget(ParameterWidget):
    """
    Enhanced widget showing marker info with uncertainty and trace binding.
    """
    def __init__(self, param, parent=None):
        super().__init__(param, parent)
        self._setup_ui()
        
        # Cache for current values
        self._current_x = 0.0
        self._current_y = 0.0
        self._current_color = "#ffffff"
        self._current_symbol = "o"
        self._current_size = 8
        self._current_uncertainty = (None, None)
        self._current_bound = False
        self._current_mode = "linear"
    
    def _setup_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        
        # Position info - shows (x,y) and [computed] for trace binding
        self.position_label = QLabel()
        self.position_label.setStyleSheet("""
            QLabel {
                color: #dddddd;
                padding: 2px 4px;
                min-width: 120px;
            }
        """)
        
        # Symbol preview - shows marker with uncertainty bars
        self.symbol_preview = MarkerSymbolPreview()
        
        # Trace binding indicator
        self.binding_label = QLabel()
        self.binding_label.setStyleSheet("""
            QLabel {
                color: #666666;
                font-style: italic;
                padding: 2px 4px;
            }
        """)
        
        layout.addWidget(self.position_label)
        layout.addWidget(self.symbol_preview)
        layout.addWidget(self.binding_label)
        layout.addStretch()

class MarkerSymbolPreview(QWidget):
    """
    Custom widget showing marker symbol with uncertainty bars.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(60, 20)
        
        self._color = QColor("#ffffff")
        self._symbol = "o"
        self._size = 8
        self._uncertainty = (None, None)
        
        # Symbol drawing functions
        self._symbol_funcs = {
            'o': self._draw_circle,
            's': self._draw_square,
            't': self._draw_triangle,
            'd': self._draw_diamond
        }
    
    def update_style(self, color: str, symbol: str, size: int, 
                    uncertainty: Tuple[Optional[float], Optional[float]]):
        self._color = QColor(color)
        self._symbol = symbol
        self._size = size
        self._uncertainty = uncertainty
        self.update()
    
    def paintEvent(self, event):
        try:
            painter = QPainter(self)
            painter.setRenderHint(QPainter.Antialiasing)
            
            # Center point for symbol
            center = QPointF(30, 10)
            
            # Draw uncertainty bars if enabled
            if self._uncertainty[0] is not None and self._uncertainty[1] is not None:
                painter.setPen(QPen(self._color, 1, Qt.DashLine))
                # Scale uncertainty to widget height
                lower_y = 15  # Bottom of widget
                upper_y = 5   # Top of widget
                painter.drawLine(QPointF(30, lower_y), QPointF(30, upper_y))
                # End caps
                painter.drawLine(QPointF(27, lower_y), QPointF(33, lower_y))
                painter.drawLine(QPointF(27, upper_y), QPointF(33, upper_y))
            
            # Draw symbol
            painter.setPen(QPen(self._color))
            painter.setBrush(self._color)
            
            draw_func = self._symbol_funcs.get(self._symbol, self._draw_circle)
            draw_func(painter, center, self._size)
            
        except Exception as e:
            logger.error(f"Error drawing marker preview: {e}")

class MarkerInfoWidget(ParameterWidget):
    """Widget showing marker info and symbol preview."""
    
    def __init__(self, param, parent=None):
        super().__init__(param, parent)
        self._setup_ui()
    
    def _setup_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        
        self.symbol_preview = MarkerSymbolPreview()
        layout.addWidget(self.symbol_preview)
    
    def _process_pending_update(self):
        """Process position and style updates."""
        updates = self._pending_updates
        self._pending_updates = {}
        
        try:
            # Update symbol style if any style properties changed
            if any(key in updates for key in ['color', 'symbol', 'size']):
                color = updates.get('color', self._current_color)
                symbol = updates.get('symbol', self._current_symbol)
                size = updates.get('size', self._current_size)
                
                self._current_color = color
                self._current_symbol = symbol
                self._current_size = size
                
                self.symbol_preview.update_style(color, symbol, size)
            
            # Update position if x or y changed
            if 'x' in updates or 'y' in updates:
                x = updates.get('x', self._current_x)
                y = updates.get('y', self._current_y)
                
                self._current_x = x
                self._current_y = y
                
                self.symbol_preview.set_position(x, y)
                
        except Exception as e:
            logger.error(f"Error updating marker info: {e}")

class MarkerParameterItem(ModelParameterItem):
    """Parameter item for markers with enhanced preview."""
    
    def makeWidget(self) -> Optional[QWidget]:
        """Create the marker preview widget."""
        try:
            self.widget = MarkerPreviewWidget(self.param)
            return self.widget
        except Exception as e:
            logger.error(f"Error creating marker widget: {e}")
            return None
    
    def updateWidget(self, **kwargs):
        """Update the preview widget with new values."""
        if self.widget:
            self.widget.queue_update(**kwargs)
    
    def addCustomContextActions(self, menu: QMenu):
        """Add marker-specific context actions."""
        # Add reset uncertainty action if enabled
        model = self.param.state.get_model(self.param.model_id)
        if model and model.get_property('uncertainty_visible', False):
            reset_action = menu.addAction("Reset Uncertainty")
            reset_action.triggered.connect(self._handle_reset_uncertainty)
    
    def _handle_reset_uncertainty(self):
        """Reset uncertainty bounds to zero."""
        try:
            self.param.begin_update()
            self.param.set_model_property('uncertainty_upper', 0.0)
            self.param.set_model_property('uncertainty_lower', 0.0)
            self.param.end_update()
        except Exception as e:
            logger.error(f"Error resetting uncertainty: {e}")

    
class MarkerParameter(ModelParameter):
    """
    Enhanced parameter for markers with trace binding and uncertainty support.
    Provides flat structure for common properties with minimal nesting.
    """
    
    itemClass = MarkerParameterItem
    
    def __init__(self, **opts):
        opts['type'] = 'marker'
        super().__init__(**opts)
        
        model = self.state.get_model(self.model_id) if self.state and self.model_id else None
        self.setupParameters(model)
    
    def setupParameters(self, model: Optional[Marker]):
        """Set up marker parameters with flattened structure."""
        def get_prop(name, default):
            return model.get_property(name, default) if model else default
        
        # Top-level parameters for quick access
        params = [
            # Position and identification
            dict(name='x', type='float',
                 value=get_prop('x', 0.0)),
            dict(name='y', type='float',
                 value=get_prop('y', 0.0),
                 enabled=not model.bound_to_trace if model else True),
            dict(name='label', type='str',
                 value=get_prop('label', '')),
            dict(name='visible', type='bool',
                 value=get_prop('visible', True)),
            
            # Visual style
            dict(name='color', type='color',
                 value=get_prop('color', '#ffffff')),
            dict(name='symbol', type='list',
                 value=get_prop('symbol', 'o'),
                 limits=['o', 's', 't', 'd']),
            dict(name='size', type='int',
                 value=get_prop('size', 8),
                 limits=(4, 20)),
                 
            # Interpolation (only shown when trace-bound)
            dict(name='interpolation_mode', type='list',
                 value=get_prop('interpolation_mode', 'linear'),
                 limits=['linear', 'nearest'],
                 visible=model.bound_to_trace if model else False),
            
            # Uncertainty as a subgroup
            {
                'name': 'Uncertainty',
                'type': 'group',
                'children': [
                    dict(name='uncertainty_visible', type='bool',
                         value=get_prop('uncertainty_visible', False)),
                    dict(name='uncertainty_upper', type='float',
                         value=get_prop('uncertainty_upper', 0.0)),
                    dict(name='uncertainty_lower', type='float',
                         value=get_prop('uncertainty_lower', 0.0))
                ]
            }
        ]
        
        # Add all parameters
        for param_opts in params:
            param = Parameter.create(**param_opts)
            self.addChild(param)
            
            # Connect change handlers
            if param.type() == 'group':
                for child in param.children():
                    child.sigValueChanged.connect(self._handle_parameter_change)
            else:
                param.sigValueChanged.connect(self._handle_parameter_change)
    
    def _handle_parameter_change(self, param, value):
        """Handle parameter changes with trace binding awareness."""
        try:
            # Get current model
            model = self.state.get_model(self.model_id)
            if not model:
                return
            
            # Special handling for y-value when trace bound
            if param.name() == 'y' and model.bound_to_trace:
                return  # Ignore y changes when bound to trace
            
            # Handle uncertainty visibility changes
            if param.name() == 'uncertainty_visible':
                uncertainty_group = self.child('Settings').child('Uncertainty')
                for child in uncertainty_group.children():
                    if child.name() != 'uncertainty_visible':
                        child.setOpts(visible=value)
            
            # Normal property update
            self.set_model_property(param.name(), value)
            
        except Exception as e:
            logger.error(f"Error handling parameter change: {e}")
    
    def handle_property_update(self, prop: str, value: Any):
        """Handle model property updates with preview updates."""
        try:
            # Update matching parameter
            settings = self.child('Settings')
            if settings:
                def update_param(parent, name, val):
                    for child in parent.children():
                        if child.name() == name:
                            child.setValue(val)
                            return True
                        if child.type() == 'group':
                            if update_param(child, name, val):
                                return True
                    return False
                
                update_param(settings, prop, value)
            
            # Check if we need to enable/disable y input
            if prop == 'bound_to_trace':
                pos_group = settings.child('Position')
                if pos_group:
                    y_param = pos_group.child('y')
                    if y_param:
                        y_param.setOpts(enabled=not value)
                    # Show/hide interpolation mode
                    interp_param = pos_group.child('interpolation_mode')
                    if interp_param:
                        interp_param.setOpts(visible=value)
            
            # Update preview widget
            if hasattr(self, 'widget'):
                self.widget.queue_update(**{prop: value})
                
        except Exception as e:
            logger.error(f"Error handling property update: {e}")

