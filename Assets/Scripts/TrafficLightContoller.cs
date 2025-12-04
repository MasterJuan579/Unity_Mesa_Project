using UnityEngine;

public class TrafficLightController : MonoBehaviour
{
    [Header("Identificación")]
    public string trafficLightId;  // Debe coincidir con el ID de Python (ej: "TL_0_3")

    [Header("Luces del semáforo")]
    public Light luzRoja;
    public Light luzAmarilla;
    public Light luzVerde;

    [Header("Estado actual")]
    public string currentState = "RED";

    void Start()
    {
        SetState(currentState);
    }

    public void SetState(string state)
    {
        currentState = state;

        if (luzRoja != null) luzRoja.enabled = false;
        if (luzAmarilla != null) luzAmarilla.enabled = false;
        if (luzVerde != null) luzVerde.enabled = false;

        switch (state.ToUpper())
        {
            case "RED":
                if (luzRoja != null) luzRoja.enabled = true;
                break;
            case "YELLOW":
                if (luzAmarilla != null) luzAmarilla.enabled = true;
                break;
            case "GREEN":
                if (luzVerde != null) luzVerde.enabled = true;
                break;
        }
    }
}