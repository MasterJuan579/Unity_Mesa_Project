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

    Dictionary<int, GameObject> unityAgents = new Dictionary<int, GameObject>();

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
            JObject data = JObject.Parse(msg);
            var type = (string)data["type"];
            if (type == "update")
            {
                var agents = (JArray)data["agents"];
                ApplyMesaState(agents);
            }
        });
    }

    private void ApplyMesaState(JArray agents)
    {
        // Marcamos los agentes vistos en esta actualización
        HashSet<int> seen = new HashSet<int>();
        foreach (var a in agents)
        {
            int id = (int)a["id"];
            int x = (int)a["x"];
            int y = (int)a["y"];
            seen.Add(id);

            if (!unityAgents.ContainsKey(id))
            {
                var go = Instantiate(agentPrefab, agentsRoot);
                go.name = "Agent_" + id;
                var ctrl = go.GetComponent<AgentController>();
                if (ctrl != null) ctrl.agentID = id;
                unityAgents[id] = go;
            }
            // Actualizamos posición (Y=0 asumiendo plano)
            // Usamos localPosition para que dependa de dónde pongas el AgentsRoot
            unityAgents[id].transform.localPosition = new Vector3(x, 0f, y);
        }

        // Eliminamos agentes que ya no existen en Mesa
        List<int> toRemove = new List<int>();
        foreach (var kv in unityAgents)
        {
            if (!seen.Contains(kv.Key))
                toRemove.Add(kv.Key);
        }
        foreach (int id in toRemove)
        {
            Destroy(unityAgents[id]);
            unityAgents.Remove(id);
        }
    }

    public async Task SendAgentUpdate(int id, int x, int y)
    {
        JObject payload = new JObject();
        payload["type"] = "update";
        JArray arr = new JArray();
        JObject ag = new JObject();
        ag["id"] = id;
        ag["x"] = x;
        ag["y"] = y;
        arr.Add(ag);
        payload["agents"] = arr;
        string msg = payload.ToString();
        
        if (websocket.State == WebSocketState.Open)
            await websocket.SendText(msg);
    }

    public async Task SendAgentRemove(int id)
    {
        JObject payload = new JObject();
        payload["type"] = "remove";
        JArray arr = new JArray();
        JObject ag = new JObject();
        ag["id"] = id;
        arr.Add(ag);
        payload["agents"] = arr;
        string msg = payload.ToString();
        if (websocket.State == WebSocketState.Open)
            await websocket.SendText(msg);
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
}