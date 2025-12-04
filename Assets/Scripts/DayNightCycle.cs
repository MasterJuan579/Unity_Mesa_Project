using UnityEngine;

public class DayNightCycle : MonoBehaviour
{
    [Tooltip("Duration of a full day in seconds")]
    public float dayDuration = 60f; // Default 1 minute per day

    void Update()
    {
        // Rotate around the X axis (World space) to simulate sun movement
        float rotationSpeed = 360f / dayDuration;
        transform.Rotate(Vector3.right * rotationSpeed * Time.deltaTime);
    }
}
