# MesaServer/server.py
import asyncio
import websockets
import json
import sys
import os

# Añadimos el directorio Modelos al path para que model.py pueda importar agents
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../Modelos')))

from model import TrafficModel
from agents import VehicleAgent, TrafficLightAgent

MODEL_WIDTH = 74
MODEL_HEIGHT = 74
WS_HOST = "localhost"
WS_PORT = 8765

# Instanciamos el modelo real
model = TrafficModel(num_vehicles=50)
connected = set()

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

async def broadcast_state():
    """Envía el estado de todos los agentes a Unity."""
    if not connected:
        return
        
    agents_data = []
    
    # Recolectamos datos de los agentes
    for agent in model.agents_list:
        # Verificamos que el agente tenga posición válida
        if agent.pos is None:
            continue

        # Serializamos Vehículos
        if isinstance(agent, VehicleAgent):
            agents_data.append({
                "id": agent.unique_id,
                "x": float(agent.pos[0]), # Float para movimiento suave
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
    while True:
        if connected:
            model.step()
            await broadcast_state()
        # Controlamos la velocidad de la simulación (aprox 10-20 FPS)
        await asyncio.sleep(0.1) 

async def handler(ws):
    """Maneja la conexión de un cliente (Unity)."""
    print("Unity conectado 🎮")
    connected.add(ws)
    try:
        # Enviar estado inicial
        await broadcast_state()
        
        async for message in ws:
            await process_message(message)
            
    except websockets.ConnectionClosed:
        print("Unity desconectado ❌")
    finally:
        connected.remove(ws)

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