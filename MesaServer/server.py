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
from agents import VehicleAgent, TrafficLightAgent

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
    model = TrafficModel(num_vehicles=100)
    print("🔄 Modelo de tráfico reiniciado")


async def process_message(message: str):
    """Procesa mensajes JSON desde Unity (si los hubiera)."""
    try:
        data = json.loads(message)
    except Exception as e:
        print("Error parseando JSON:", e)
        return

    # Aquí podrías manejar comandos desde Unity si fuera necesario
    # Por ahora, el modelo corre por su cuenta.
    pass


async def send_graph(ws):
    """
    Envía la estructura del grafo (nodos y aristas) a Unity para depuración.

    OJO: sumamos +0.5 a x,y para que el grafo quede centrado en las celdas,
    igual que los coches y el layout.
    """
    if model is None:
        return

    graph_data = {
        "type": "grid",
        "nodes": [],
        "edges": []
    }

    # Extraer nodos (centrados)
    for node in model.graph.nodes:
        graph_data["nodes"].append({
            "x": float(node[0]) + 0.5,
            "y": float(node[1]) + 0.5
        })

    # Extraer aristas (centradas)
    for u, v in model.graph.edges:
        graph_data["edges"].append({
            "u": {"x": float(u[0]) + 0.5, "y": float(u[1]) + 0.5},
            "v": {"x": float(v[0]) + 0.5, "y": float(v[1]) + 0.5}
        })

    msg = json.dumps(graph_data)
    await ws.send(msg)


async def send_layout(ws):
    """
    Envía un 'tilemap' con los tipos de celda del modelo:
    - ROAD
    - BUILDING
    - PARKING
    - GREEN_ZONE
    - RED_ZONE
    - MEDIAN
    - ROUNDABOUT
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
                continue  # Nos ahorramos mandar celdas vacías

            tiles.append({
                "x": x + 0.5,          # Centro de la celda
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

    # Recolectamos datos de los agentes
    for agent in model.agents_list:
        # Verificamos que el agente tenga posición válida
        if getattr(agent, "pos", None) is None:
            continue

        # Serializamos Vehículos
        if isinstance(agent, VehicleAgent):
            agents_data.append({
                "id": agent.unique_id,
                "x": float(agent.pos[0]),  # Float para movimiento suave
                "y": float(agent.pos[1]),
                "type": "car"
            })
        # Serializamos Semáforos (Opcional, para visualizar estado)
        elif isinstance(agent, TrafficLightAgent):
            agents_data.append({
                "id": agent.unique_id,
                "x": float(agent.pos[0]),
                "y": float(agent.pos[1]),
                "state": agent.state,
                "type": "traffic_light"
            })

    world_state = {
        "type": "update",
        "agents": agents_data
    }
    msg = json.dumps(world_state)

    # Enviar a todos los clientes conectados
    await asyncio.gather(*[ws.send(msg) for ws in connected])


async def simulation_loop():
    """Bucle principal de la simulación."""
    global model
    while True:
        # Solo avanza el modelo si:
        # - Hay al menos un cliente conectado
        # - Ya tenemos un modelo creado (después de reset_model)
        if connected and model is not None:
            model.step()
            await broadcast_state()
        # Controlamos la velocidad de la simulación (aprox 10-20 FPS)
        await asyncio.sleep(0.5)


async def handler(ws):
    """Maneja la conexión de un cliente (Unity)."""
    global connected
    print("Unity conectado 🎮")

    # Detectamos si este es el PRIMER cliente (o sea, cuando le das Play)
    first_client = (len(connected) == 0)
    connected.add(ws)

    if first_client:
        # Solo cuando el primer cliente entra, reiniciamos el modelo
        reset_model()

    try:
        # 1) Enviar layout (calles / edificios / parkings...)
        await send_layout(ws)
        # 2) Enviar grafo para debug visual (calles como líneas cian)
        await send_graph(ws)
        # 3) Enviar estado inicial de agentes
        await broadcast_state()

        async for message in ws:
            await process_message(message)

    except websockets.ConnectionClosed:
        print("Unity desconectado ❌")
    finally:
        connected.remove(ws)
        print("Clientes conectados ahora:", len(connected))


async def main():
    # Iniciamos el bucle de simulación en background
    asyncio.create_task(simulation_loop())

    async with websockets.serve(handler, WS_HOST, WS_PORT):
        print(f"Servidor Mesa corriendo en ws://{WS_HOST}:{WS_PORT} 🚀")
        await asyncio.Future()  # run forever


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Servidor detenido.")
