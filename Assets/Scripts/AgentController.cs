using UnityEngine;
using System.Threading.Tasks;

public class AgentController : MonoBehaviour
{
    public int agentID = -1;

    void Update()
    {
        // Aquí podrías añadir lógica visual local (luces, ruedas girando, etc.)
    }

    // Método para mover el agente desde Unity y avisar a Python (Bidireccional)
    public async void MoveBy(int dx, int dy)
    {
        Vector3 newPos = transform.position + new Vector3(dx, 0, dy);
        transform.position = newPos;
        if (MesaSync.Instance != null)
        {
            await MesaSync.Instance.SendAgentUpdate(agentID, (int)newPos.x, (int)newPos.z);
        }
    }

    public async void Remove()
    {
        if (MesaSync.Instance != null)
        {
            await MesaSync.Instance.SendAgentRemove(agentID);
        }
        Destroy(gameObject);
    }
}