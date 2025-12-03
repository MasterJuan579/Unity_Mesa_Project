using UnityEngine;

public class TrafficLightController : MonoBehaviour
{
    public GameObject greenLight;
    public GameObject yellowLight;
    public GameObject redLight;

    public void SetState(string state)
    {
        // Apagar todas primero
        if (greenLight) greenLight.SetActive(false);
        if (yellowLight) yellowLight.SetActive(false);
        if (redLight) redLight.SetActive(false);

        // Prender la correcta
        switch (state)
        {
            case "Green":
            case "GREEN":
                if (greenLight) greenLight.SetActive(true);
                break;
            case "Yellow":
            case "YELLOW":
                if (yellowLight) yellowLight.SetActive(true);
                break;
            case "Red":
            case "RED":
                if (redLight) redLight.SetActive(true);
                break;
        }
    }
}
