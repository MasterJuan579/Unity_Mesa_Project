using UnityEngine;
using NativeWebSocket;
using Newtonsoft.Json.Linq;
using System.Collections.Generic;
using System.Threading.Tasks;

public class MesaSync : MonoBehaviour
{
    public static MesaSync Instance;
    private WebSocket websocket;

    [Header("Prefabs y jerarquía")]
    public GameObject agentPrefab;          // Prefab por defecto para coches (compatibilidad con tu versión actual)
    public Transform agentsRoot;

    [System.Serializable]
    public class CarPrefabEntry
    {
        public string carType;              // p.ej. "sedan", "truck", "sport"
        public GameObject prefab;           // Prefab del coche en Unity
    }

    [Tooltip("Lista opcional de prefabs para distintos tipos de coches, según el campo 'car_type' que venga desde Mesa.")]
    public List<CarPrefabEntry> carPrefabs = new List<CarPrefabEntry>();

    // Mapa interno para buscar rápido el prefab según el tipo
    private Dictionary<string, GameObject> carPrefabMap = new Dictionary<string, GameObject>();

    [Header("Coordenadas Mesa → Unity")]
    public float scaleFactor = 3.0833f;
    public bool swapAxes = false;

    [Header("Debug visual")]
    public bool showLayoutDebug = true;

    [Header("Semáforos")]
    public List<TrafficLightController> trafficLights = new List<TrafficLightController>();

    private List<Vector3[]> debugEdges = new List<Vector3[]>();
    private Dictionary<string, GameObject> unityAgents = new Dictionary<string, GameObject>();
    private List<GameObject> layoutTiles = new List<GameObject>();

    async void Awake()
    {
        Instance = this;

        // Construir mapa de tipos de coche → prefab
        carPrefabMap.Clear();
        foreach (var entry in carPrefabs)
        {
            if (entry != null && entry.prefab != null && !string.IsNullOrEmpty(entry.carType))
            {
                if (!carPrefabMap.ContainsKey(entry.carType))
                {
                    carPrefabMap.Add(entry.carType, entry.prefab);
                }
                else
                {
                    Debug.LogWarning($"CarPrefabEntry duplicado para carType '{entry.carType}'. Se usará el primero que se registró.");
                }
            }
        }

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
        UnityMainThreadDispatcher.Instance().Enqueue(() =>
        {
            try
            {
                JObject data = JObject.Parse(msg);
                var type = (string)data["type"];

                if (type == "update")
                {
                    var agents = (JArray)data["agents"];
                    ApplyMesaState(agents);
                }
                else if (type == "grid")
                {
                    Debug.Log("Received GRID (graph) message from server.");
                    ParseGrid(data);
                }
                else if (type == "layout")
                {
                    Debug.Log("Received LAYOUT (tilemap) message from server.");
                    if (showLayoutDebug)
                    {
                        ParseLayout(data);
                    }
                }
            }
            catch (System.Exception e)
            {
                Debug.LogError("Error parsing message: " + e.Message);
            }
        });
    }

    // ==========================
    // LAYOUT
    // ==========================
    private void ParseLayout(JObject data)
    {
        foreach (var go in layoutTiles)
        {
            if (go != null) Destroy(go);
        }
        layoutTiles.Clear();

        var tiles = (JArray)data["tiles"];
        if (tiles == null) return;

        foreach (var t in tiles)
        {
            float rawX = (float)t["x"];
            float rawY = (float)t["y"];
            int tileType = (int)t["type"];

            float x, z;
            if (swapAxes)
            {
                x = rawY * scaleFactor;
                z = rawX * scaleFactor;
            }
            else
            {
                x = rawX * scaleFactor;
                z = rawY * scaleFactor;
            }

            GameObject tile = GameObject.CreatePrimitive(PrimitiveType.Quad);
            tile.name = $"Tile_{tileType}_{rawX}_{rawY}";
            tile.transform.SetParent(agentsRoot, false);
            tile.transform.localRotation = Quaternion.Euler(90f, 0f, 0f);
            tile.transform.localPosition = new Vector3(x, 0.02f, z);
            tile.transform.localScale = new Vector3(scaleFactor, scaleFactor, 1f);

            var renderer = tile.GetComponent<Renderer>();
            if (renderer != null)
            {
                renderer.material.color = GetColorForTileType(tileType);
            }

            layoutTiles.Add(tile);
        }
        Debug.Log($"Layout: creados {layoutTiles.Count} tiles de debug.");
    }

    private Color GetColorForTileType(int type)
    {
        switch (type)
        {
            case 1: return new Color(0.5f, 0.5f, 0.5f);
            case 0: return new Color(0.3f, 0.25f, 0.2f);
            case 3: return Color.yellow;
            case 5: return Color.green;
            case 6: return Color.red;
            case 4: return Color.white;
            case 2: return new Color(0.6f, 0.3f, 0.8f);
            default: return Color.black;
        }
    }

    // ==========================
    // GRAFO
    // ==========================
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
            if (swapAxes)
            {
                u = new Vector3(uy * scaleFactor, 0, ux * scaleFactor);
                v = new Vector3(vy * scaleFactor, 0, vx * scaleFactor);
            }
            else
            {
                u = new Vector3(ux * scaleFactor, 0, uy * scaleFactor);
                v = new Vector3(vx * scaleFactor, 0, vy * scaleFactor);
            }
            debugEdges.Add(new Vector3[] { u, v });
        }
        Debug.Log($"Received graph with {debugEdges.Count} edges.");
    }

    // ==========================
    // AGENTES (coches y semáforos)
    // ==========================
    private void ApplyMesaState(JArray agents)
    {
        HashSet<string> seen = new HashSet<string>();

        foreach (var a in agents)
        {
            string id = (string)a["id"];
            float rawX = (float)a["x"];
            float rawY = (float)a["y"];

            float x, z;
            if (swapAxes)
            {
                x = rawY * scaleFactor;
                z = rawX * scaleFactor;
            }
            else
            {
                x = rawX * scaleFactor;
                z = rawY * scaleFactor;
            }

            string agentType = (string)a["type"];
            seen.Add(id);

            // COCHES
            if (agentType == "car")
            {
                // Intentamos leer el tipo de coche desde el JSON: "car_type"
                // Si no viene, se queda en null y usaremos el prefab por defecto (agentPrefab).
                string carType = null;
                if (a["car_type"] != null && a["car_type"].Type != JTokenType.Null)
                {
                    carType = (string)a["car_type"];
                }

                if (!unityAgents.ContainsKey(id))
                {
                    GameObject prefabToUse = GetCarPrefab(carType);
                    if (prefabToUse == null)
                    {
                        Debug.LogError($"No se encontró prefab para el coche con id '{id}'. Asegúrate de asignar 'agentPrefab' o la lista 'carPrefabs'.");
                        continue;
                    }

                    var go = Instantiate(prefabToUse, agentsRoot);
                    go.name = string.IsNullOrEmpty(carType) ? $"Agent_{id}" : $"Agent_{id}_{carType}";
                    unityAgents[id] = go;
                }

                if (unityAgents.ContainsKey(id))
                {
                    Vector3 newPos = new Vector3(x, 0f, z);
                    Vector3 oldPos = unityAgents[id].transform.localPosition;

                    Vector3 direction = newPos - oldPos;
                    if (direction.sqrMagnitude > 0.001f)
                    {
                        unityAgents[id].transform.localRotation = Quaternion.LookRotation(direction);
                    }

                    unityAgents[id].transform.localPosition = newPos;
                }
            }
            // SEMÁFOROS
            else if (agentType == "traffic_light")
            {
                string state = (string)a["state"];
                UpdateTrafficLight(id, state);
            }
        }

        // Eliminar agentes que ya no existan
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

    // Devuelve el prefab adecuado para el tipo de coche recibido
    private GameObject GetCarPrefab(string carType)
    {
        // Si viene un tipo y existe en el mapa, lo usamos
        if (!string.IsNullOrEmpty(carType) && carPrefabMap.TryGetValue(carType, out var prefab) && prefab != null)
        {
            return prefab;
        }

        // Si no hay tipo o no está configurado, usamos el prefab general que ya tenías
        if (agentPrefab != null)
        {
            return agentPrefab;
        }

        // Si tampoco hay agentPrefab, devolvemos null y dejamos que el llamador decida
        return null;
    }

    // Método para actualizar un semáforo por ID
    private void UpdateTrafficLight(string id, string state)
    {
        Debug.Log($"[MESA] Recibido semáforo ID: '{id}' Estado: '{state}'");
        
        foreach (var tl in trafficLights)
        {
            if (tl != null)
            {
                Debug.Log($"[UNITY] Comparando con: '{tl.trafficLightId}'");
                if (tl.trafficLightId == id)
                {
                    Debug.Log($"[MATCH] ¡Encontrado! Actualizando {id}");
                    tl.SetState(state);
                    return;
                }
            }
        }
        
        Debug.LogWarning($"[NO MATCH] No se encontró semáforo con ID: {id}");
    }

    public async Task SendAgentUpdate(int id, int x, int y)
    {
        await Task.CompletedTask;
    }

    public async Task SendAgentRemove(int id)
    {
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
            Vector3 p00 = agentsRoot.TransformPoint(new Vector3(0, 0, 0));
            Vector3 p7474 = agentsRoot.TransformPoint(new Vector3(74, 0, 74));
            Vector3 p740 = agentsRoot.TransformPoint(new Vector3(74, 0, 0));
            Vector3 p074 = agentsRoot.TransformPoint(new Vector3(0, 0, 74));

            Gizmos.DrawWireSphere(p00, 1.0f);
            Gizmos.DrawWireSphere(p7474, 1.0f);
            Gizmos.DrawLine(p00, p740);
            Gizmos.DrawLine(p740, p7474);
            Gizmos.DrawLine(p7474, p074);
            Gizmos.DrawLine(p074, p00);

            Gizmos.color = Color.cyan;
            foreach (var edge in debugEdges)
            {
                Vector3 start = agentsRoot.TransformPoint(edge[0]);
                Vector3 end = agentsRoot.TransformPoint(edge[1]);
                Gizmos.DrawLine(start, end);
            }
        }
    }
}
