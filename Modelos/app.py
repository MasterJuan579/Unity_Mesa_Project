import solara
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from matplotlib.collections import PatchCollection
from matplotlib.figure import Figure
import numpy as np
import time
import asyncio

from model import TrafficModel, BUILDING, ROAD, ROUNDABOUT, PARKING, EMPTY, MEDIAN
from agents import VehicleAgent, TrafficLightAgent

# --- CONFIGURATION ---
GRID_WIDTH = 24
GRID_HEIGHT = 24

COLOR_MAP = {
    BUILDING: "#4682B4",   # Steel Blue
    ROAD: "#D3D3D3",       # Light Gray
    ROUNDABOUT: "#8B4513", # Saddle Brown
    PARKING: "#FFD700",    # Gold
    EMPTY: "#FFFFFF",      # White
    MEDIAN: "#32CD32"      # Lime Green
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

def create_city_visualization(model: TrafficModel) -> Figure:
    fig, ax = plt.subplots(figsize=(10, 10))
    
    # 1. DRAW MAP
    rects = []
    colors = []
    for x in range(GRID_WIDTH):
        for y in range(GRID_HEIGHT):
            cell_type = CITY_LAYOUT[x][y]
            # CORRECCIÓN: Usar (x, y) directamente
            rect = patches.Rectangle((x, y), 1, 1)
            rects.append(rect)
            colors.append(COLOR_MAP[cell_type])

    collection = PatchCollection(rects, facecolors=colors, edgecolors='white', linewidths=0.5, zorder=0)
    ax.add_collection(collection)
    
    # 2. DRAW PARKING
    for pid, pos in model.parking_spots.items():
        px, py = pos
        border = patches.Rectangle((px, py), 1, 1, linewidth=2, edgecolor='black', facecolor='none', zorder=5)
        ax.add_patch(border)
        ax.text(px + 0.5, py + 0.5, "P", color='black', fontsize=10, ha='center', va='center', fontweight='bold', zorder=6)

    # 3. DRAW AGENTS
    vehicle_count = 0
    
    for agent in model.agents_list:
        # --- NUEVA PROTECCIÓN ---
        # Los TrafficManagerAgent no tienen posición física.
        # Si intentamos leer agent.pos, daría error. Los saltamos.
        if not hasattr(agent, "pos") or agent.pos is None:
            continue
        
        # Mesa guarda posiciones como (float, float). Ej: (12.5, 3.5)
        x, y = agent.pos
        
        if isinstance(agent, VehicleAgent):
            vehicle_count += 1
            color = AGENT_COLORS["moving"]
            if agent.speed < 0.01:
                color = AGENT_COLORS["stopped"]
            
            circle = patches.Circle((x, y), radius=0.35, facecolor=color, edgecolor='white', linewidth=1, zorder=15)
            ax.add_patch(circle)
            
        elif isinstance(agent, TrafficLightAgent):
            # El agente físico lee el estado de su manager automáticamente aquí
            if agent.state == "GREEN": c = AGENT_COLORS["light_green"]
            elif agent.state == "YELLOW": c = AGENT_COLORS["light_yellow"]
            else: c = AGENT_COLORS["light_red"]
            
            rect = patches.Rectangle(
                (x - 0.5, y - 0.5), 
                1.0, 1.0, 
                facecolor=c, 
                edgecolor='none', 
                alpha=0.6, 
                zorder=20
            )
            ax.add_patch(rect)

    ax.set_aspect("equal")
    ax.set_xlim(0, GRID_WIDTH)
    ax.set_ylim(0, GRID_HEIGHT)
    ax.invert_yaxis()
    
    ax.set_xticks(np.arange(0.5, GRID_WIDTH + 0.5, 1))
    ax.set_yticks(np.arange(0.5, GRID_HEIGHT + 0.5, 1))
    ax.set_xticklabels(range(GRID_WIDTH))
    ax.set_yticklabels(range(GRID_HEIGHT))
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