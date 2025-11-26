using UnityEngine;
using System.Threading.Tasks;

public class AgentSpawner : MonoBehaviour
{
    int nextID = 1000; // IDs altos para no chocar con los de Python

    public void SpawnAt(int x, int y)
    {
        var go = Instantiate(MesaSync.Instance.agentPrefab, new Vector3(x,0,y), Quaternion.identity, MesaSync.Instance.agentsRoot);
        var ctrl = go.GetComponent<AgentController>();
        ctrl.agentID = nextID;
        
        // Notificar a Mesa que existe un agente nuevo
        _ = MesaSync.Instance.SendAgentUpdate(nextID, x, y);
        nextID++;
    }
}