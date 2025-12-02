# unity_server.py
import asyncio
import json
import websockets

from model import TrafficModel
from agents import VehicleAgent, TrafficLightAgent

WS_HOST = "localhost"
WS_PORT = 9000

# Simulación algo lenta para que se vea bien
STEP_DELAY = 0.3  # segundos entre steps

# Conexiones activas (Unity)
connected: set[websockets.WebSocketServerProtocol] = set()

# Modelo global. Se reinicia cada vez que se conecta el primer cliente.
model: TrafficModel | None = None


def serialize_world(model: TrafficModel) -> dict:
    """
    Convierte el estado del modelo en un diccionario listo para mandar a Unity.
    Manda vehículos y semáforos con su posición.
    """
    agents_payload = []

    for a in model.agents_list:
        if not hasattr(a, "pos") or a.pos is None:
            continue

        ax, ay = a.pos

        if isinstance(a, VehicleAgent):
            agents_payload.append({
                "id": str(a.unique_id),
                "type": "vehicle",
                "x": float(ax),
                "y": float(ay),
                "speed": float(a.speed),
            })
        elif isinstance(a, TrafficLightAgent):
            agents_payload.append({
                "id": str(a.unique_id),
                "type": "light",
                "x": float(ax),
                "y": float(ay),
                "state": a.state,
            })

    return {
        "type": "state",
        "step": model.step_count,
        "agents": agents_payload,
    }


async def broadcast_state():
    """
    Envía el estado actual del modelo a todos los clientes Unity conectados.
    """
    if not connected:
        return

    if model is None:
        return

    state = serialize_world(model)
    msg = json.dumps(state)
    await asyncio.gather(*[ws.send(msg) for ws in connected])


async def handler(ws):
    """
    Maneja una conexión WebSocket (Unity).
    - Si es el PRIMER cliente (pasamos de 0 a 1), se reinicia el modelo.
    """
    global model

    print("Unity conectado 🎮")

    # ¿Antes de este cliente no había nadie?
    first_client = (len(connected) == 0)

    # Agregamos el nuevo cliente al set
    connected.add(ws)

    # Si es el primer cliente, reiniciamos la simulación completa
    if first_client:
        print("🔁 Reiniciando TrafficModel para nueva sesión Unity")
        model = TrafficModel(num_vehicles=40)  # aquí puedes ajustar el número
        # Enviamos un estado inicial (step 0) antes de que empiece a avanzar
        await broadcast_state()

    try:
        # Mensaje de bienvenida
        await ws.send(json.dumps({
            "type": "hello",
            "message": "Conectado a TrafficModel",
        }))

        # Si en el futuro mandas comandos desde Unity, se procesan aquí
        async for message in ws:
            print("Mensaje desde Unity:", message)

    except websockets.ConnectionClosed:
        print("Unity desconectado ❌")
    finally:
        connected.remove(ws)


async def simulation_loop():
    """
    Loop principal de simulación.

    - Solo avanza el modelo si:
        * hay al menos un cliente conectado, y
        * el modelo existe (ya fue creado al conectar Unity).
    - Cada vez que Unity se conecta siendo el primer cliente,
      el modelo se reinicia desde step 0.
    """
    global model

    while True:
        # Si no hay clientes o aún no hemos creado el modelo: no hacemos nada
        if not connected or model is None:
            await asyncio.sleep(0.1)
            continue

        # Avanzar modelo
        model.step()

        # Debug: cuántos coches se están moviendo
        moving_cars = sum(
            1 for a in model.agents_list
            if isinstance(a, VehicleAgent) and getattr(a, "speed", 0.0) > 0.01
        )
        print(f"[DEBUG PY] step={model.step_count} moving_cars={moving_cars}")

        # Enviar estado a Unity
        await broadcast_state()

        # Esperar un poco para que en Unity se vea fluido
        await asyncio.sleep(STEP_DELAY)


async def main():
    # Levantar servidor WebSocket
    server = await websockets.serve(handler, WS_HOST, WS_PORT)
    print(f"Servidor Unity/Mesa en ws://{WS_HOST}:{WS_PORT} 🚀")

    # Iniciar la simulación en paralelo
    asyncio.create_task(simulation_loop())

    # Mantener el servidor corriendo
    await asyncio.Future()  # run forever


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Servidor detenido.")
