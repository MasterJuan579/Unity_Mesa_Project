using UnityEngine;
using NativeWebSocket;
using Newtonsoft.Json.Linq;
using System.Collections.Generic;
using System.Threading.Tasks;
using System.Collections.Generic;

public class MesaSync : MonoBehaviour
{
    public static MesaSync Instance;
    private WebSocket websocket;

    [Header("Prefabs y jerarquía")]
    public GameObject agentPrefab;
    public Transform agentsRoot;

    [Header("Coordenadas Mesa → Unity")]
    // Tamaño de una unidad de Mesa en Unity.
    public float scaleFactor = 3.0833f;

    // Si tu mapa está rotado 90° respecto a Mesa
    public bool swapAxes = false;

    [Header("Debug visual")]
    public bool showLayoutDebug = true;

    [Header("Semáforos")]
    public List<GameObject> trafficLightObjects = new List<GameObject>();

    // Estructura para almacenar el grafo de debug (en coords locales Mesa)
    private List<Vector3[]> debugEdges = new List<Vector3[]>();

    // Diccionario para mantener referencia a los GameObjects de los agentes
    private Dictionary<string, GameObject> unityAgents = new Dictionary<string, GameObject>();

    // Lista de tiles del layout (calles, edificios, parkings, etc.)
    private List<GameObject> layoutTiles = new List<GameObject>();

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
                else
                {
                    Debug.Log("Received unknown message type: " + type);
                }
            }
            catch (System.Exception e)
            {
                Debug.LogError("Error parsing message: " + e.Message);
            }
        });
    }

    // ==========================
    // LAYOUT: calles, edificios…
    // ==========================
    private void ParseLayout(JObject data)
    {
        // Limpiar tiles anteriores
        foreach (var go in layoutTiles)
        {
            if (go != null)
                Destroy(go);
        }
        layoutTiles.Clear();

        var tiles = (JArray)data["tiles"];
        if (tiles == null)
            return;

        foreach (var t in tiles)
        {
            float rawX = (float)t["x"];
            float rawY = (float)t["y"];
            int type = (int)t["type"];

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

            // Creamos un Quad para visualizar el tile
            GameObject tile = GameObject.CreatePrimitive(PrimitiveType.Quad);
            tile.name = $"Tile_{type}_{rawX}_{rawY}";
            tile.transform.SetParent(agentsRoot, false);

            // Lo acostamos sobre el plano (que mire hacia arriba)
            tile.transform.localRotation = Quaternion.Euler(90f, 0f, 0f);

            // Ubicación (ligeramente arriba del piso para que no se z-fightee con el terreno)
            tile.transform.localPosition = new Vector3(x, 0.02f, z);

            // Escala: cada celda ≈ scaleFactor
            tile.transform.localScale = new Vector3(scaleFactor, scaleFactor, 1f);

            var renderer = tile.GetComponent<Renderer>();
            if (renderer != null)
            {
                renderer.material.color = GetColorForTileType(type);
            }

            layoutTiles.Add(tile);
        }

        Debug.Log($"Layout: creados {layoutTiles.Count} tiles de debug.");
    }

    private Color GetColorForTileType(int type)
    {
        // Debe coincidir con tus constantes en Python:
        // 0 BUILDING, 1 ROAD, 2 ROUNDABOUT, 3 PARKING,
        // -1 EMPTY, 4 MEDIAN, 5 GREEN_ZONE, 6 RED_ZONE
        switch (type)
        {
            case 1: // ROAD
                return new Color(0.5f, 0.5f, 0.5f); // gris
            case 0: // BUILDING
                return new Color(0.3f, 0.25f, 0.2f); // café/gris oscuro
            case 3: // PARKING
                return Color.yellow;
            case 5: // GREEN_ZONE
                return Color.green;
            case 6: // RED_ZONE
                return Color.red;
            case 4: // MEDIAN
                return Color.white;
            case 2: // ROUNDABOUT
                return new Color(0.6f, 0.3f, 0.8f); // moradito
            default:
                return Color.black;
        }
    }

    // ==========================
    // GRAFO (líneas cian)
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

            string type = (string)a["type"];
            seen.Add(id);

            // COCHES
            if (type == "car")
            {
                if (!unityAgents.ContainsKey(id))
                {
                    var go = Instantiate(agentPrefab, agentsRoot);
                    go.name = "Agent_" + id;
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
            else if (type == "traffic_light")
            {
                string state = (string)a["state"];
                UpdateTrafficLight(id, state);
            }
        }

        // Eliminar agentes que ya no existan en Mesa
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

    // Método para actualizar semáforos
    private void UpdateTrafficLight(string id, string state)
    {
        // Buscar el semáforo por posición o ID
        // Por ahora imprimimos para debug
        // Debug.Log($"Semáforo {id} -> {state}");
        
        // Buscar todos los semáforos en la escena y actualizar sus luces
        foreach (var trafficLight in trafficLightObjects)
        {
            if (trafficLight == null) continue;
            
            // Buscar las luces hijas
            Transform luzRoja = trafficLight.transform.Find("Luz_Roja");
            Transform luzAmarilla = trafficLight.transform.Find("Luz_Amarilla");
            Transform luzVerde = trafficLight.transform.Find("Luz_Verde");
            
            if (luzRoja != null)
            {
                Light lightR = luzRoja.GetComponent<Light>();
                if (lightR != null) lightR.enabled = (state == "RED");
            }
            if (luzAmarilla != null)
            {
                Light lightY = luzAmarilla.GetComponent<Light>();
                if (lightY != null) lightY.enabled = (state == "YELLOW");
            }
            if (luzVerde != null)
            {
                Light lightG = luzVerde.GetComponent<Light>();
                if (lightG != null) lightG.enabled = (state == "GREEN");
            }
        }
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
            // Marco general
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

            // Ejes
            Gizmos.color = Color.red; // X de Mesa
            Vector3 pX = agentsRoot.TransformPoint(new Vector3(20, 0, 0));
            Gizmos.DrawLine(p00, pX);
            Gizmos.DrawSphere(pX, 0.5f);

            Gizmos.color = Color.blue; // Y de Mesa (Z en Unity)
            Vector3 pY = agentsRoot.TransformPoint(new Vector3(0, 0, 20));
            Gizmos.DrawLine(p00, pY);
            Gizmos.DrawSphere(pY, 0.5f);

            // Grafo de caminos
            Gizmos.color = Color.cyan;
            foreach (var edge in debugEdges)
            {
                Vector3 start = agentsRoot.TransformPoint(edge[0]);
                Vector3 end = agentsRoot.TransformPoint(edge[1]);
                Gizmos.DrawLine(start, end);
                Gizmos.DrawSphere(start, 0.3f);
                Gizmos.DrawSphere(end, 0.3f);
            }
        }
    }
}
