using System;
using System.Collections;
using System.Collections.Generic;
using System.Net.WebSockets;
using System.Text;
using System.Threading;
using UnityEngine;

[Serializable]
public class AgentData {
    public string id;
    public string type;   // "vehicle" o "light"
    public float x;
    public float y;
    public float speed;   // solo coches
    public string state;  // solo semáforos: "RED", "GREEN", "YELLOW"
}

[Serializable]
public class WorldState {
    public string type;   // "state"
    public int step;
    public AgentData[] agents;
}

public class TrafficClient : MonoBehaviour
{
    [Header("WebSocket config")]
    public string serverUrl = "ws://localhost:9000";

    [Header("Prefabs")]
    public GameObject vehiclePrefab;
    public GameObject lightPrefab;

    [Header("Escala Mesa -> Unity")]
    [Tooltip("Multiplica las coords de Mesa (0-25) para mapear a Unity")]
    public float scale = 3f;    // 25x25 -> ~75x75 (ajustable)

    [Header("Root / Offset del mapa")]
    [Tooltip("Root del mapa (GameObject padre de la ciudad). Si está asignado, las coords de Mesa se aplican relativas a este.")]
    public Transform mapRoot;

    [Tooltip("Offset manual en caso de no usar mapRoot")]
    public Vector3 manualOffset = Vector3.zero;

    [Header("Visual coches")]
    [Tooltip("Altura Y a la que se dibujan los coches (por si el piso está más arriba)")]
    public float carHeight = 0.0f;

    [Tooltip("Qué tan suave se mueve el coche hacia la nueva posición")]
    public float moveLerpSpeed = 10f;

    [Tooltip("Qué tan rápido rota el coche hacia la dirección de movimiento")]
    public float rotationLerpSpeed = 10f;

    private ClientWebSocket ws;
    private CancellationTokenSource cts;

    // id Mesa -> GameObject en Unity
    private Dictionary<string, GameObject> activeAgents = new Dictionary<string, GameObject>();

    // Para calcular dirección de movimiento de cada coche
    private Dictionary<string, Vector3> lastPositions = new Dictionary<string, Vector3>();

    void Start()
    {
        Application.runInBackground = true;
        cts = new CancellationTokenSource();
        StartCoroutine(ConnectAndListen());
    }

    IEnumerator ConnectAndListen()
    {
        ws = new ClientWebSocket();
        Uri uri = new Uri(serverUrl);

        Debug.Log("Conectando a " + serverUrl);

        var connectTask = ws.ConnectAsync(uri, cts.Token);
        while (!connectTask.IsCompleted)
            yield return null;

        if (ws.State == WebSocketState.Open)
        {
            Debug.Log("✅ CONECTADO AL SERVIDOR (TrafficClient)");
            StartCoroutine(ReceiveLoop());
        }
        else
        {
            Debug.LogError("❌ No se pudo conectar al servidor WebSocket");
        }
    }

    IEnumerator ReceiveLoop()
    {
        Debug.Log("📥 Empezando ReceiveLoop");

        ArraySegment<byte> buffer = new ArraySegment<byte>(new byte[65535]);

        while (ws.State == WebSocketState.Open)
        {
            var receiveTask = ws.ReceiveAsync(buffer, cts.Token);
            while (!receiveTask.IsCompleted)
                yield return null;

            var result = receiveTask.Result;
            if (result.MessageType == WebSocketMessageType.Close)
            {
                Debug.Log("Servidor cerró la conexión");
                yield break;
            }

            int count = result.Count;
            string json = Encoding.UTF8.GetString(buffer.Array, 0, count);

            // Debug del JSON que llega
            Debug.Log("📩 JSON recibido: " + json);

            // Siempre intentamos procesarlo
            ProcessWorld(json);
        }
    }

    void ProcessWorld(string json)
    {
        try
        {
            // 1) Parsear el JSON a WorldState
            WorldState world = JsonUtility.FromJson<WorldState>(json);

            if (world == null)
            {
                Debug.LogWarning("⚠ No se pudo parsear WorldState (world == null)");
                return;
            }

            if (world.type != "state")
            {
                Debug.Log($"ℹ Mensaje ignorado, type = {world.type}");
                return;
            }

            if (world.agents == null)
            {
                Debug.LogWarning("⚠ WorldState sin agents (agents == null)");
                return;
            }

            Debug.Log($"🌍 Step {world.step} | agents recibidos: {world.agents.Length}");

            // Para saber qué agentes siguen existiendo en este step
            HashSet<string> seenThisStep = new HashSet<string>();

            bool loggedMovingCar = false;

            // 2) Recorrer agentes
            foreach (var ag in world.agents)
            {
                if (ag == null || string.IsNullOrEmpty(ag.id))
                    continue;

                seenThisStep.Add(ag.id);

                GameObject prefab = null;
                if (ag.type == "vehicle")
                    prefab = vehiclePrefab;
                else if (ag.type == "light")
                    prefab = lightPrefab;

                // 🧱 Fallback: si no hay prefab asignado, usamos un Cube temporal
                bool tempPrefab = false;
                if (prefab == null)
                {
                    Debug.LogWarning($"⚠ Prefab nulo para agente {ag.id} tipo {ag.type}, usando Cube por defecto");
                    prefab = GameObject.CreatePrimitive(PrimitiveType.Cube);
                    prefab.SetActive(false); // solo como plantilla
                    tempPrefab = true;
                }

                // 3) Obtener o crear GameObject
                if (!activeAgents.TryGetValue(ag.id, out GameObject go) || go == null)
                {
                    go = Instantiate(prefab);
                    go.name = ag.id;
                    activeAgents[ag.id] = go;

                    if (tempPrefab)
                        Destroy(prefab); // destruimos la plantilla temporal

                    Debug.Log($"➕ Instanciado agente {ag.id} tipo {ag.type}");
                }

                // 4) Posición objetivo en coords "de mapa" (locales)
                float localX = ag.x * scale;
                float localZ = ag.y * scale;

                Vector3 localPos;
                if (ag.type == "vehicle")
                    localPos = new Vector3(localX, carHeight, localZ);
                else
                    localPos = new Vector3(localX, 0f, localZ);

                // 4.1 Convertir a mundo usando mapRoot o manualOffset
                Vector3 targetPos;
                if (mapRoot != null)
                {
                    // localPos se interpreta relativo al root del mapa
                    targetPos = mapRoot.TransformPoint(localPos);
                }
                else
                {
                    // fallback: solo offset + posiciones
                    targetPos = localPos + manualOffset;
                }

                // 4.2 Movimiento suave (Lerp) hacia targetPos
                if (moveLerpSpeed > 0f)
                {
                    go.transform.position = Vector3.Lerp(
                        go.transform.position,
                        targetPos,
                        Time.deltaTime * moveLerpSpeed
                    );
                }
                else
                {
                    go.transform.position = targetPos;
                }

                // 4.3 Rotación de coches según dirección de movimiento
                if (ag.type == "vehicle")
                {
                    Vector3 lastPos;
                    if (!lastPositions.TryGetValue(ag.id, out lastPos))
                    {
                        // Primera vez: solo guardamos posición
                        lastPositions[ag.id] = go.transform.position;
                    }
                    else
                    {
                        Vector3 dir = go.transform.position - lastPos;
                        dir.y = 0f; // plano XZ

                        if (dir.sqrMagnitude > 0.0001f)
                        {
                            Quaternion targetRot = Quaternion.LookRotation(dir.normalized);

                            if (rotationLerpSpeed > 0f)
                            {
                                go.transform.rotation = Quaternion.Slerp(
                                    go.transform.rotation,
                                    targetRot,
                                    Time.deltaTime * rotationLerpSpeed
                                );
                            }
                            else
                            {
                                go.transform.rotation = targetRot;
                            }

                            if (!loggedMovingCar && ag.speed > 0.01f)
                            {
                                loggedMovingCar = true;
                                Debug.Log($"🚗 Moving car {ag.id} -> pos: {go.transform.position}, speed={ag.speed}, step={world.step}");
                            }
                        }

                        // Actualizar última posición
                        lastPositions[ag.id] = go.transform.position;
                    }
                }

                // 5) Color de semáforos
                if (ag.type == "light")
                {
                    var r = go.GetComponent<Renderer>();
                    if (r != null)
                    {
                        if (ag.state == "GREEN")       r.material.color = Color.green;
                        else if (ag.state == "YELLOW") r.material.color = Color.yellow;
                        else                           r.material.color = Color.red;
                    }
                }
            }

            // 6) Limpiar agentes que ya NO vienen en el estado (ya llegaron / murieron en Python)
            List<string> toRemove = new List<string>();
            foreach (var kv in activeAgents)
            {
                if (!seenThisStep.Contains(kv.Key))
                    toRemove.Add(kv.Key);
            }

            foreach (var id in toRemove)
            {
                if (activeAgents.TryGetValue(id, out GameObject go))
                {
                    Destroy(go);
                }
                activeAgents.Remove(id);
                lastPositions.Remove(id);
            }
        }
        catch (Exception e)
        {
            Debug.LogError("💥 Error en ProcessWorld: " + e.GetType().Name + " - " + e.Message);
            Debug.LogError(e.StackTrace);
        }
    }

    void OnDestroy()
    {
        if (ws != null)
        {
            try
            {
                cts.Cancel();
                ws.Dispose();
            }
            catch (Exception) { }
        }
    }
}
