# PyMetr

PyMetr is a comprehensive Python library for automated instrument control, data acquisition, and test management. It seamlessly integrates a driver framework, test scripting engine, and real-time visualization into a single, powerful platform for laboratory and production environments.

## 🚀 Key Features

### 🧩 **Unified Instrument Control Framework**
- **Multi-Protocol Support:** Seamlessly communicate with instruments via PyVISA, raw sockets, and more.
- **Dynamic Driver Discovery:** Automatically parse and display supported properties and commands.
- **Real-Time Updates:** Instruments emit measurements and traces, which are captured and displayed via the state manager.

### 💡 **Scripting Engine with Built-in Helpers**
- **Minimal Boilerplate:** Rapidly create test scripts using high-level helpers like `create_plot()` and `create_table()`.
- **Live Instrument Control:** Scripts directly update instrument parameters, and results display in real time.
- **Test Recorder (Upcoming):** Automatically generate reusable test scripts from manual workflows.

### 📊 **Dynamic UI and Real-Time Visualizations**
- **View-Driven Architecture:** Auto-generated parameter trees from driver metadata.
- **Live Plots and Tables:** Results update instantly during test execution.
- **Multi-Result Views:** Simultaneously display multiple test results.

### 🗂️ **Test and Data Management**
- **Hierarchical Models:** Organize tests, groups, plots, tables, and results under a unified structure.
- **State-Driven:** Every change updates the application state and reflects in the UI.
- **Integrated Statistics (Planned):** Analyze historical test data and generate confidence-based specifications.

---

## 🛠️ Installation

Install PyMetr directly from GitHub:

```bash
pip install git+https://github.com/Pymetr/Pymetr.git


---

📁 Project Structure

pymetr/
├── engine/         # Test execution engine with built-in script helpers
├── drivers/        # Instrument drivers and connection interfaces
├── views/          # Interactive UI components 
├── models/         # Core data models (Test, Result, Plot, Table, Trace)
└── core/           # Shared utilities (logging, state management, etc.)


---

💻 Example: Test Script

from pymetr.engine import create_result, create_plot, set_test_progress, wait
import numpy as np

def run_test():
    result = create_result("Sine Wave Test")
    plot = create_plot("Sine Wave")
    result.add(plot)

    x = np.linspace(0, 2 * np.pi, 500)
    for frame in range(100):
        y = np.sin(x + frame * 0.1)
        plot.set_trace("Sine", x, y, color="#4CAF50")
        set_test_progress(frame, f"Frame {frame}")
        wait(50)

    return True


---

📈 Future Roadmap

📊 Data Analytics for Historical Tests: Automatically compute statistics from old results.

📉 Spec Generator: Derive performance specifications from confidence intervals in collected datasets.

📝 Test Recorder: Record and replay manual workflows as reusable scripts.



---

📜 License

PyMetr is licensed under the MIT License.

🙌 Authors

Ryan C. 


