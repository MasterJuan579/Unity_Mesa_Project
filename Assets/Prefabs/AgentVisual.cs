using UnityEngine;

public class AgentVisual : MonoBehaviour
{
    [Header("Movimiento")]
    public float moveSpeed = 10f;      // Velocidad con la que persigue el target
    public float rotateSpeed = 10f;    // Qué tan rápido gira hacia la dirección

    private Vector3 targetPosition;
    private bool hasTarget = false;

    /// <summary>
    /// Llamado desde TrafficClient cuando llega una nueva posición desde Python.
    /// </summary>
    public void SetTargetPosition(Vector3 worldPos)
    {
        // Primera vez: lo ponemos directo en su lugar
        if (!hasTarget)
        {
            transform.position = worldPos;
            targetPosition = worldPos;
            hasTarget = true;
            return;
        }

        // Siguientes veces: solo actualizamos el target
        targetPosition = worldPos;
    }

    private void Update()
    {
        if (!hasTarget)
            return;

        Vector3 dir = targetPosition - transform.position;
        float dist = dir.magnitude;

        if (dist > 0.001f)
        {
            // --- MOVER ---
            Vector3 step = dir.normalized * moveSpeed * Time.deltaTime;
            if (step.magnitude > dist)
                step = dir; // para no pasarnos

            transform.position += step;

            // --- ROTAR (solo en XZ) ---
            Vector3 flatDir = new Vector3(dir.x, 0, dir.z);
            if (flatDir.sqrMagnitude > 0.0001f)
            {
                Quaternion targetRot = Quaternion.LookRotation(flatDir, Vector3.up);
                transform.rotation = Quaternion.Slerp(
                    transform.rotation,
                    targetRot,
                    rotateSpeed * Time.deltaTime
                );
            }
        }
    }
}
