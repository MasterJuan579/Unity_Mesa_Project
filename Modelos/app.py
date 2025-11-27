import solara
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from matplotlib.collections import PatchCollection
from matplotlib.figure import Figure
import numpy as np
import time
import asyncio

from model import TrafficModel, BUILDING, ROAD, ROUNDABOUT, PARKING, EMPTY, MEDIAN, GREEN_ZONE, RED_ZONE
from agents import VehicleAgent, TrafficLightAgent

# --- CONFIGURATION ---
# --- CONFIGURATION ---
GRID_WIDTH = 74
GRID_HEIGHT = 74

COLOR_MAP = {
    BUILDING: "#4682B4",   # Steel Blue
    ROAD: "#D3D3D3",       # Light Gray
    ROUNDABOUT: "#8B4513", # Saddle Brown
    PARKING: "#FFD700",    # Gold
    EMPTY: "#FFFFFF",      # White
    MEDIAN: "#32CD32",     # Lime Green (Not used for lines, maybe for old medians)
    GREEN_ZONE: "#00B050", # Green Zone (Semáforo)
    RED_ZONE: "#FF0000"    # Red Zone (Semáforo)
}

AGENT_COLORS = {
    "moving": "black",
    "stopped": "red",
    "light_green": "#00FF00",
    "light_yellow": "#FFFF00",
    "light_red": "#FF0000"
}

# --- PRE-LOAD ---
static_model = TrafficModel(num_vehicles=0)
CITY_LAYOUT = static_model.city_layout

# --- STATE ---
model_state = solara.reactive(None)
current_step = solara.reactive(0)
is_playing = solara.reactive(False)
play_speed = solara.reactive(0.1) 
num_vehicles_param = solara.reactive(5)

def initialize_model():
    model_state.value = TrafficModel(num_vehicles=num_vehicles_param.value)
    current_step.value = 0
    is_playing.value = False

def step_model():
    if model_state.value is not None:
        model_state.value.step()
        model_state.value = model_state.value 
        current_step.value += 1

def create_city_visualization(model):
    # Create figure and axis
    fig, ax = plt.subplots(figsize=(8.5, 8.5))
    
    # Draw the grid
    city_data = np.zeros((GRID_WIDTH, GRID_HEIGHT))
    
    # Fill grid with colors based on agent type
    for x in range(GRID_WIDTH):
        for y in range(GRID_HEIGHT):
            cell_contents = model.grid.get_cell_list_contents((x, y))
            # Default to road color
            color_val = 0.2 # Light gray for road
            
            # Check for static layout first
            layout_type = model.city_layout[x][y]
            if layout_type == BUILDING:
                color_val = 0.8 # Blue for buildings
            elif layout_type == ROUNDABOUT:
                color_val = 0.9 # Brown for roundabout
            elif layout_type == GREEN_ZONE:
                color_val = 0.6 # Green for static zone
            elif layout_type == RED_ZONE:
                color_val = 0.7 # Red for static zone
            elif layout_type == EMPTY: # Should be road/empty
                color_val = 0.2
            
            # Check for dynamic agents
            if cell_contents:
                for agent in cell_contents:
                    if isinstance(agent, TrafficLightAgent):
                        if agent.state: # Green
                            color_val = 0.6
                        else: # Red
                            color_val = 0.7
            
            # We'll use a custom colormap, so we just store integers/floats mapping to types
            # Let's use the COLOR_MAP keys directly if possible, or map to them
            # Simplified approach: create an RGB grid directly
            pass

    # Re-implement using imshow with direct colors for simplicity
    # Create an RGB array
    rgb_grid = np.zeros((GRID_WIDTH, GRID_HEIGHT, 3))
    
    vehicle_count = 0 # Initialize vehicle count for the title

    for x in range(GRID_WIDTH):
        for y in range(GRID_HEIGHT):
            # Default background (Road/Empty)
            color_hex = COLOR_MAP[ROAD]
            
            # 1. Draw Static Layout
            layout_type = model.city_layout[x][y]
            if layout_type in COLOR_MAP:
                color_hex = COLOR_MAP[layout_type]
                
            # 2. Draw Agents (override static)
            cell_contents = model.grid.get_cell_list_contents((x, y))
            for agent in cell_contents:
                if isinstance(agent, VehicleAgent): # Changed from CarAgent to VehicleAgent
                    vehicle_count += 1
                    color_hex = AGENT_COLORS["moving"]
                    if agent.speed < 0.01:
                        color_hex = AGENT_COLORS["stopped"]
                elif isinstance(agent, TrafficLightAgent):
                    color_hex = AGENT_COLORS["light_green"] if agent.state == "GREEN" else AGENT_COLORS["light_red"] # Adjusted to use AGENT_COLORS and state string
            
            # Convert hex to rgb
            rgb_grid[x, y] = [int(color_hex[1:3], 16)/255, int(color_hex[3:5], 16)/255, int(color_hex[5:7], 16)/255]

    # Display the grid
    # Note: imshow displays (row, col), so we might need to transpose if x is col and y is row
    # In Mesa: x is usually column, y is row. 
    # Imshow: axis 0 is y (row), axis 1 is x (col).
    # So we transpose to match standard cartesian visualization where x is horizontal
    ax.imshow(np.transpose(rgb_grid, (1, 0, 2)), origin='upper', extent=[0, GRID_WIDTH, GRID_HEIGHT, 0])
    
    # Draw grid lines
    ax.set_xticks(np.arange(0, GRID_WIDTH, 1))
    ax.set_yticks(np.arange(0, GRID_HEIGHT, 1))
    ax.grid(which='both', color='w', linestyle='-', linewidth=1)
    
    # Set tick labels to be 1-based (1 to 25)
    # We want the label to be centered in the cell.
    # The extent is 0 to 25. The centers are 0.5, 1.5, ... 24.5
    ax.set_xticks(np.arange(0.5, GRID_WIDTH, 1))
    ax.set_yticks(np.arange(0.5, GRID_HEIGHT, 1))
    ax.set_xticklabels(range(1, GRID_WIDTH + 1))
    ax.set_yticklabels(range(1, GRID_HEIGHT + 1))
    ax.tick_params(left=False, bottom=False, labeltop=True, labelbottom=False)
    
    ax.set_title(f"Step: {current_step.value} | Vehicles: {vehicle_count}", fontsize=14)
    
    return fig

@solara.component
def StatisticsPanel():
    if model_state.value is None: return
    vehicles = [a for a in model_state.value.agents_list if isinstance(a, VehicleAgent)]
    total = len(vehicles)
    stopped = sum(1 for v in vehicles if v.speed < 0.01)
    avg_speed = model_state.value.get_avg_speed()
    
    with solara.Card("Live Statistics"):
        solara.Markdown(f"**Step:** {current_step.value}")
        solara.Markdown(f"**Vehicles:** {total}")
        solara.Markdown(f"**Stopped:** {stopped}")
        solara.Markdown(f"**Avg Speed:** {avg_speed:.2f}")

@solara.component
def TrafficSimulation():
    if model_state.value is None:
        initialize_model()

    # Definimos el efecto de forma SÍNCRONA
    def run_loop_effect():
        # Definimos la lógica asíncrona dentro
        async def loop_logic():
            while is_playing.value:
                step_model()
                await asyncio.sleep(play_speed.value)

        # Si está reproduciendo, creamos la tarea en segundo plano
        if is_playing.value:
            task = asyncio.create_task(loop_logic())
            
            # Devolvemos una función de limpieza para cancelar la tarea
            def cleanup():
                task.cancel()
            return cleanup
            
        return None 

    # Pasamos la función síncrona al use_effect
    solara.use_effect(run_loop_effect, [is_playing.value])

    with solara.Sidebar():
        solara.Markdown("## 🎮 Controls")
        solara.Button("🔄 Reset", color="primary", on_click=initialize_model, block=True)
        if is_playing.value:
            solara.Button("⏸️ Pause", color="warning", on_click=lambda: is_playing.set(False), block=True)
        else:
            solara.Button("▶️ Play", color="success", on_click=lambda: is_playing.set(True), block=True)
        solara.Button("⏭️ Step +1", color="info", on_click=step_model, disabled=is_playing.value, block=True)
        solara.SliderFloat("Speed", value=play_speed, min=0.01, max=1.0, step=0.05)
        solara.SliderInt("Vehicles", value=num_vehicles_param, min=1, max=50)
        StatisticsPanel()

    with solara.Column(style={"padding": "20px", "align-items": "center"}):
        solara.Markdown("# 🚦 Traffic Jam Simulation")
        if model_state.value is not None:
            fig = create_city_visualization(model_state.value)
            solara.FigureMatplotlib(fig, dependencies=[current_step.value])
            plt.close(fig)

@solara.component
def Page():
    TrafficSimulation()