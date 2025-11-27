import sys
import os

# Add paths to sys.path
sys.path.append('/home/sgamborino/Documents/source/unity/Unity_Mesa_Project/Modelos')
sys.path.append('/home/sgamborino/Documents/source/unity/Unity_Mesa_Project/MesaServer')

try:
    from model import TrafficModel
    tm = TrafficModel(num_vehicles=0)
    print(f"TrafficModel Grid: {tm.grid.width}x{tm.grid.height}")
    print(f"TrafficModel Space: {tm.space.x_max}x{tm.space.y_max}")
except Exception as e:
    print(f"Error loading TrafficModel: {e}")

try:
    # Need to rename or handle import conflict if both are named model.py
    # But since we appended paths, let's try importing SyncModel directly if possible
    # or use importlib
    import importlib.util
    spec = importlib.util.spec_from_file_location("MesaServerModel", "/home/sgamborino/Documents/source/unity/Unity_Mesa_Project/MesaServer/model.py")
    mesa_server_model = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mesa_server_model)
    
    sm = mesa_server_model.SyncModel()
    print(f"SyncModel Grid: {sm.grid.width}x{sm.grid.height}")
except Exception as e:
    print(f"Error loading SyncModel: {e}")

try:
    spec_app = importlib.util.spec_from_file_location("AppModel", "/home/sgamborino/Documents/source/unity/Unity_Mesa_Project/Modelos/app.py")
    app_module = importlib.util.module_from_spec(spec_app)
    spec_app.loader.exec_module(app_module)
    print(f"App Grid: {app_module.GRID_WIDTH}x{app_module.GRID_HEIGHT}")
except Exception as e:
    print(f"Error loading App: {e}")
