using UnityEngine;

public class TrafficLightController : MonoBehaviour
{
    [Header("Identificación")]
    public string trafficLightId;
    
    [Header("Luces del semáforo (Point Lights en el foco)")]
    public Light luzRoja;
    public Light luzAmarilla;
    public Light luzVerde;
    
    [Header("Luces de calle (Spot Lights hacia el pavimento)")]
    public Light streetLightRed;
    public Light streetLightYellow;
    public Light streetLightGreen;
    
    [Header("Estado actual")]
    public string currentState = "RED";
    
    void Start()
    {
        SetState(currentState);
    }
    
    public void SetState(string state)
    {
        currentState = state;
        
        // Apagar todas las luces del foco
        if (luzRoja != null) luzRoja.enabled = false;
        if (luzAmarilla != null) luzAmarilla.enabled = false;
        if (luzVerde != null) luzVerde.enabled = false;
        
        // Apagar todas las luces de calle
        if (streetLightRed != null) streetLightRed.enabled = false;
        if (streetLightYellow != null) streetLightYellow.enabled = false;
        if (streetLightGreen != null) streetLightGreen.enabled = false;
        
        // Encender según estado
        switch (state.ToUpper())
        {
            case "RED":
                if (luzRoja != null) luzRoja.enabled = true;
                if (streetLightRed != null) streetLightRed.enabled = true;
                break;
            case "YELLOW":
                if (luzAmarilla != null) luzAmarilla.enabled = true;
                if (streetLightYellow != null) streetLightYellow.enabled = true;
                break;
            case "GREEN":
                if (luzVerde != null) luzVerde.enabled = true;
                if (streetLightGreen != null) streetLightGreen.enabled = true;
                break;
        }
    }
}