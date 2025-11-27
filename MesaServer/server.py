# MesaServer/server.py
import asyncio
import websockets
import json
from model import SyncModel

MODEL_WIDTH = 74
MODEL_HEIGHT = 74
WS_HOST = "localhost"
WS_PORT = 8765

# Instanciamos el modelo
model = SyncModel(width=MODEL_WIDTH, height=MODEL_HEIGHT)
connected = set()

async def process_message(message: str):
    """Procesa mensajes JSON desde Unity."""
    try:
        data = json.loads(message)
    except Exception as e:
        print("Error parseando JSON:", e)
        return

    msg_type = data.get("type", "")
    
    if msg_type == "update":
        for ag in data.get("agents", []):
            aid = int(ag["id"])
            x = int(ag["x"])
            y = int(ag["y"])
            
            if aid not in model.agents_dict:
                print(f"Creando agente {aid} en ({x}, {y})")
                model.add_agent(aid, x, y)
            else:
                model.move_agent(aid, x, y)
                
    elif msg_type == "remove":
        for ag in data.get("agents", []):
            aid = int(ag["id"])
            print(f"Eliminando agente {aid}")
            model.remove_agent(aid)

async def broadcast_state():
    """Envía el estado de todos los agentes a Unity."""
    if not connected:
        return
        
    agents_data = model.serialize_grid()
    world_state = {
        "type": "update", 
        "agents": agents_data
    }
    msg = json.dumps(world_state)
    
    # Enviar a todos los clientes conectados
    # websockets 10+ maneja el broadcast de forma eficiente
    await asyncio.gather(*[ws.send(msg) for ws in connected])

async def handler(ws):
    """Maneja la conexión de un cliente (Unity)."""
    print("Unity conectado 🎮")
    connected.add(ws)
    try:
        # Enviar estado inicial
        await broadcast_state()
        
        async for message in ws:
            await process_message(message)
            await broadcast_state()
            
    except websockets.ConnectionClosed:
        print("Unity desconectado ❌")
    finally:
        connected.remove(ws)

async def main():
    async with websockets.serve(handler, WS_HOST, WS_PORT):
        print(f"Servidor Mesa corriendo en ws://{WS_HOST}:{WS_PORT} 🚀")
        await asyncio.Future()  # run forever

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Servidor detenido.")