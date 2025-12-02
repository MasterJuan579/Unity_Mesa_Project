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
            } catch (System.Exception e) {
                Debug.LogError("Error parsing message: " + e.Message);
            }
        });
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
                // Usamos localPosition para que dependa de dónde pongas el AgentsRoot
                // Asumimos que Y en Unity es Up, y en Mesa es Z (o plano XZ)
                // Mesa (x, y) -> Unity (x, 0, z) ? O (x, 0, y)?
                // Generalmente Mesa Y -> Unity Z
                unityAgents[id].transform.localPosition = new Vector3(x, 0f, y);
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
        }
    }
}