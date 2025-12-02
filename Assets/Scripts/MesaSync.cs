using UnityEngine;
using NativeWebSocket;
using Newtonsoft.Json.Linq;
using System.Collections.Generic;
using System.Threading.Tasks;

public class MesaSync : MonoBehaviour
{
    public static MesaSync Instance;
    private WebSocket websocket;
    public GameObject agentPrefab;
    public Transform agentsRoot;
    
    // Factor de escala para adaptar coordenadas de Mesa (0-24) a Unity (0-74)
    // 74 / 24 = 3.08333...
    public float scaleFactor = 3.0833f;
    
    // Opción para intercambiar ejes si la orientación está rotada 90 grados
    public bool swapAxes = false;

    // Estructura para almacenar el grafo de debug
    private List<Vector3[]> debugEdges = new List<Vector3[]>();

    // Diccionario para mantener referencia a los GameObjects de los agentes
    Dictionary<string, GameObject> unityAgents = new Dictionary<string, GameObject>();

    async void Awake()
    {
        Instance = this;
        websocket = new WebSocket("ws://localhost:8765");

        websocket.OnOpen += () =>
        {
            Debug.Log("Connected to Mesa WebSocket.");
        };

        websocket.OnMessage += (bytes) =>
        {
            var msg = System.Text.Encoding.UTF8.GetString(bytes);
            HandleMessage(msg);
        };

        websocket.OnError += (e) =>
        {
            Debug.Log("WebSocket Error: " + e);
        };

        websocket.OnClose += (e) =>
        {
            Debug.Log("WebSocket closed.");
        };

        await websocket.Connect();
    }

    private void HandleMessage(string msg)
    {
        // Ejecutamos esto en el hilo principal usando el Dispatcher
        UnityMainThreadDispatcher.Instance().Enqueue(() => {
            try {
                JObject data = JObject.Parse(msg);
                var type = (string)data["type"];
                if (type == "update")
                {
                    var agents = (JArray)data["agents"];
                    ApplyMesaState(agents);
                }
                else if (type == "grid")
                {
                    Debug.Log("Received GRID message from server.");
                    ParseGrid(data);
                }
                else 
                {
                    Debug.Log("Received unknown message type: " + type);
                }
            } catch (System.Exception e) {
                Debug.LogError("Error parsing message: " + e.Message);
            }
        });
    }

    private void ParseGrid(JObject data)
    {
        debugEdges.Clear();
        var edges = (JArray)data["edges"];
        foreach (var edge in edges)
        {
            float ux = (float)edge["u"]["x"];
            float uy = (float)edge["u"]["y"];
            float vx = (float)edge["v"]["x"];
            float vy = (float)edge["v"]["y"];

            Vector3 u, v;
            if (swapAxes) {
                u = new Vector3(uy * scaleFactor, 0, ux * scaleFactor);
                v = new Vector3(vy * scaleFactor, 0, vx * scaleFactor);
            } else {
                u = new Vector3(ux * scaleFactor, 0, uy * scaleFactor);
                v = new Vector3(vx * scaleFactor, 0, vy * scaleFactor);
            }
            debugEdges.Add(new Vector3[] { u, v });
        }
        Debug.Log($"Received graph with {debugEdges.Count} edges.");
    }

    private void ApplyMesaState(JArray agents)
    {
        // Marcamos los agentes vistos en esta actualización
        HashSet<string> seen = new HashSet<string>();
        
        foreach (var a in agents)
        {
            string id = (string)a["id"];
            // Aplicamos el factor de escala
            float rawX = (float)a["x"];
            float rawY = (float)a["y"];
            
            float x, y;
            if (swapAxes) {
                x = rawY * scaleFactor;
                y = rawX * scaleFactor;
            } else {
                x = rawX * scaleFactor;
                y = rawY * scaleFactor;
            }

            string type = (string)a["type"];
            
            seen.Add(id);

            if (!unityAgents.ContainsKey(id))
            {
                // Solo instanciamos coches por ahora
                if (type == "car") {
                    var go = Instantiate(agentPrefab, agentsRoot);
                    go.name = "Agent_" + id;
                    // var ctrl = go.GetComponent<AgentController>();
                    // if (ctrl != null) ctrl.agentID = id; // ID string issue?
                    unityAgents[id] = go;
                }
            }

            // Actualizamos posición si existe
            if (unityAgents.ContainsKey(id)) {
                // Interpolación simple o movimiento directo
                Vector3 newPos = new Vector3(x, 0f, y);
                Vector3 oldPos = unityAgents[id].transform.localPosition;
                
                // Calculamos dirección para rotar el coche
                Vector3 direction = newPos - oldPos;
                if (direction.sqrMagnitude > 0.001f) // Solo rotar si se mueve
                {
                    // Usamos LookRotation relativo al padre (AgentsRoot)
                    // Pero LookRotation funciona en espacio mundial o local?
                    // Transform.rotation es mundial. Transform.localRotation es local.
                    // La dirección calculada es en espacio local de AgentsRoot.
                    // Para aplicar rotación local correcta:
                    unityAgents[id].transform.localRotation = Quaternion.LookRotation(direction);
                }

                unityAgents[id].transform.localPosition = newPos;
            }
        }

        // Eliminamos agentes que ya no existen en Mesa (si salieron del mapa)
        List<string> toRemove = new List<string>();
        foreach (var kv in unityAgents)
        {
            if (!seen.Contains(kv.Key))
                toRemove.Add(kv.Key);
        }
        foreach (string id in toRemove)
        {
            Destroy(unityAgents[id]);
            unityAgents.Remove(id);
        }
    }

    public async Task SendAgentUpdate(int id, int x, int y)
    {
        // Deprecated for now as Mesa drives the simulation
        await Task.CompletedTask;
    }

    public async Task SendAgentRemove(int id)
    {
         // Deprecated
        await Task.CompletedTask;
    }

    void Update()
    {
        if (websocket != null)
            websocket.DispatchMessageQueue();
    }

    private async void OnApplicationQuit()
    {
        if (websocket != null)
            await websocket.Close();
    }

    void OnDrawGizmos()
    {
        if (agentsRoot != null)
        {
            Gizmos.color = Color.yellow;
            // Puntos clave de Mesa (0,0) y (74,74)
            Vector3 p00 = agentsRoot.TransformPoint(new Vector3(0, 0, 0));
            Vector3 p7474 = agentsRoot.TransformPoint(new Vector3(74, 0, 74));
            Vector3 p740 = agentsRoot.TransformPoint(new Vector3(74, 0, 0));
            Vector3 p074 = agentsRoot.TransformPoint(new Vector3(0, 0, 74));

            // Esferas en las esquinas
            Gizmos.DrawWireSphere(p00, 1.0f); // Origen
            Gizmos.DrawWireSphere(p7474, 1.0f); // Opuesto

            // Marco del Grid
            Gizmos.DrawLine(p00, p740);
            Gizmos.DrawLine(p740, p7474);
            Gizmos.DrawLine(p7474, p074);
            Gizmos.DrawLine(p074, p00);

            // Ejes para orientación
            Gizmos.color = Color.red; // Eje X de Mesa
            Vector3 pX = agentsRoot.TransformPoint(new Vector3(20, 0, 0));
            Gizmos.DrawLine(p00, pX);
            Gizmos.DrawSphere(pX, 0.5f);

            Gizmos.color = Color.blue; // Eje Y de Mesa (Z en Unity)
            Vector3 pY = agentsRoot.TransformPoint(new Vector3(0, 0, 20));
            Gizmos.DrawLine(p00, pY);
            Gizmos.DrawSphere(pY, 0.5f);

            // Dibujar grafo de caminos (Road Network)
            Gizmos.color = Color.cyan;
            foreach (var edge in debugEdges)
            {
                Vector3 start = agentsRoot.TransformPoint(edge[0]);
                Vector3 end = agentsRoot.TransformPoint(edge[1]);
                Gizmos.DrawLine(start, end);
                // Dibujar nodos (extremos de las líneas)
                Gizmos.DrawSphere(start, 0.3f);
                Gizmos.DrawSphere(end, 0.3f);
            }
        }
    }
}