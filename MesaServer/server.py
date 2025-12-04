# MesaServer/server.py
import asyncio
import websockets
import json
import sys
import os

# Añadimos el directorio Modelos al path para que model.py pueda importar agents
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../Modelos')))

from model import (
    TrafficModel,
    BUILDING,
    ROAD,
    ROUNDABOUT,
    PARKING,
    MEDIAN,
    GREEN_ZONE,
    RED_ZONE,
    EMPTY,
)
from agents import VehicleAgent, TrafficLightAgent, TrafficManagerAgent

MODEL_WIDTH = 74
MODEL_HEIGHT = 74
WS_HOST = "localhost"
WS_PORT = 8765

# Instancia global del modelo (la vamos a reiniciar cuando Unity le dé Play)
model = None
connected = set()


def reset_model():
    """Crea un nuevo modelo desde cero."""
    global model
    model = TrafficModel(num_vehicles=200)
    print("🔄 Modelo de tráfico reiniciado")


async def process_message(message: str):
    """Procesa mensajes JSON desde Unity (si los hubiera)."""
    try:
        data = json.loads(message)
    except Exception as e:
        print("Error parseando JSON:", e)
        return
    pass


async def send_graph(ws):
    """
    Envía la estructura del grafo (nodos y aristas) a Unity para depuración.
    """
    if model is None:
        return

    graph_data = {
        "type": "grid",
        "nodes": [],
        "edges": []
    }

    for node in model.graph.nodes:
        graph_data["nodes"].append({
            "x": float(node[0]) + 0.5,
            "y": float(node[1]) + 0.5
        })

    for u, v in model.graph.edges:
        graph_data["edges"].append({
            "u": {"x": float(u[0]) + 0.5, "y": float(u[1]) + 0.5},
            "v": {"x": float(v[0]) + 0.5, "y": float(v[1]) + 0.5}
        })

    msg = json.dumps(graph_data)
    await ws.send(msg)


async def send_layout(ws):
    """
    Envía un 'tilemap' con los tipos de celda del modelo.
    """
    if model is None:
        return

    tiles = []
    width = len(model.city_layout)
    height = len(model.city_layout[0])

    for x in range(width):
        for y in range(height):
            cell_type = model.city_layout[x][y]
            if cell_type == EMPTY:
                continue

            tiles.append({
                "x": x + 0.5,
                "y": y + 0.5,
                "type": int(cell_type)
            })

    msg = json.dumps({
        "type": "layout",
        "tiles": tiles
    })
    await ws.send(msg)


async def broadcast_state():
    """Envía el estado de todos los agentes a Unity."""
    if not connected or model is None:
        return

    agents_data = []

    for agent in model.agents_list:
        # Vehículos
        if isinstance(agent, VehicleAgent):
            if getattr(agent, "pos", None) is None:
                continue
            agents_data.append({
                "id": agent.unique_id,
                "x": float(agent.pos[0]),
                "y": float(agent.pos[1]),
                "type": "car"
            })
        
        # Traffic Managers (grupos de semáforos)
        elif isinstance(agent, TrafficManagerAgent):
            agents_data.append({
                "id": agent.unique_id,  # "Manager1.1", "Manager1.2", etc.
                "x": 0,
                "y": 0,
                "state": agent.state,  # "GREEN", "YELLOW", o "RED"
                "type": "traffic_light"
            })

    world_state = {
        "type": "update",
        "agents": agents_data
    }
    msg = json.dumps(world_state)

    await asyncio.gather(*[ws.send(msg) for ws in connected])


async def simulation_loop():
    """Bucle principal de la simulación."""
    global model
    while True:
        if connected and model is not None:
            model.step()
            await broadcast_state()
        await asyncio.sleep(0.5)


async def handler(ws):
    """Maneja la conexión de un cliente (Unity)."""
    global connected
    print("Unity conectado 🎮")

    first_client = (len(connected) == 0)
    connected.add(ws)

    if first_client:
        reset_model()

    try:
        await send_layout(ws)
        await send_graph(ws)
        await broadcast_state()

        async for message in ws:
            await process_message(message)

    except websockets.ConnectionClosed:
        print("Unity desconectado ❌")
    finally:
        connected.remove(ws)
        print("Clientes conectados ahora:", len(connected))


async def main():
    asyncio.create_task(simulation_loop())

    async with websockets.serve(handler, WS_HOST, WS_PORT):
        print(f"Servidor Mesa corriendo en ws://{WS_HOST}:{WS_PORT} 🚀")
        await asyncio.Future()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Servidor detenido.")
