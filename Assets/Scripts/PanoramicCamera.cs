using UnityEngine;

public class PanoramicCamera : MonoBehaviour
{
    [Tooltip("The target object to rotate around (e.g., City Center)")]
    public Transform target;

    [Tooltip("Speed of rotation in degrees per second")]
    public float rotationSpeed = 5f;

    [Tooltip("Distance from the target")]
    public float distance = 40f;

    [Tooltip("Height of the camera above the target")]
    public float height = 20f;

    private float currentAngle = 0f;

    void Start()
    {
        // If no target is assigned, create a temporary one at (0,0,0)
        if (target == null)
        {
            GameObject tempTarget = new GameObject("DefaultCameraTarget");
            tempTarget.transform.position = Vector3.zero;
            target = tempTarget.transform;
            Debug.LogWarning("PanoramicCamera: No target assigned. Created a default target at (0,0,0).");
        }

        // Initialize position
        UpdateCameraPosition();
    }

    void LateUpdate()
    {
        if (target != null)
        {
            currentAngle += rotationSpeed * Time.deltaTime;
            // Keep angle within 0-360 for cleanliness, though not strictly necessary for Euler
            currentAngle %= 360f;
            
            UpdateCameraPosition();
        }
    }

    void UpdateCameraPosition()
    {
        // Calculate rotation based on the current angle
        Quaternion rotation = Quaternion.Euler(0, currentAngle, 0);
        
        // Calculate offset vector (distance back, height up)
        // We start with a vector pointing back (-forward) and up
        Vector3 offset = new Vector3(0, height, -distance);

        // Apply rotation to the offset and add to target position
        transform.position = target.position + rotation * offset;

        // Always look at the target
        transform.LookAt(target);
    }
}
