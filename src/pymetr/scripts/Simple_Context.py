import numpy as np

def run_test(test):
    """
    Minimal test with single plot and few updates
    """
    # Create result container
    result = test.create_result("Simple Plot Test")
    result.show()
    
    # Create a single plot
    plot = test.create_plot("Simple Sine Wave")
    plot.x_label = "Time"
    plot.y_label = "Amplitude"
    result.add(plot)
    
    # Create x points
    x = np.linspace(0, 10, 5000)
    
    # Only do 3 updates
    for i in range(100):
        # Simple sine wave with changing phase
        y = np.sin(x + i)
        plot.set_trace("Sine", x, y, color="#4CAF50")
        
        # Longer wait to see each update clearly
        test.wait(10)  # 10 ms between updates
        result.progress = ((i+1) * 33)
    
    result.progress = 100
    result.status = "Pass"
    return True