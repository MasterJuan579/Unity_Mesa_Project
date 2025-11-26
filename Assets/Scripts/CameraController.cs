using UnityEngine;

public class CameraController : MonoBehaviour
{
    public float normalSpeed = 10f;   // Velocidad normal
    public float fastSpeed = 50f;     // Velocidad con Shift presionado
    public float sensitivity = 3f;    // Sensibilidad del mouse

    void Update()
    {
        // -- 1. Movimiento (WASD) --
        // Si mantienes Shift, vas más rápido
        float currentSpeed = Input.GetKey(KeyCode.LeftShift) ? fastSpeed : normalSpeed;
        
        // Leemos las teclas (W, S, A, D)
        float x = Input.GetAxis("Horizontal"); // A y D
        float z = Input.GetAxis("Vertical");   // W y S

        // Mover la cámara
        Vector3 move = transform.right * x + transform.forward * z;
        transform.position += move * currentSpeed * Time.deltaTime;

        // -- 2. Altura (Q y E) --
        if (Input.GetKey(KeyCode.E)) transform.position += Vector3.up * currentSpeed * Time.deltaTime; // Subir
        if (Input.GetKey(KeyCode.Q)) transform.position -= Vector3.up * currentSpeed * Time.deltaTime; // Bajar

        // -- 3. Rotación (Click Derecho presionado) --
        if (Input.GetMouseButton(1))
        {
            float mouseX = Input.GetAxis("Mouse X") * sensitivity;
            float mouseY = Input.GetAxis("Mouse Y") * sensitivity;

            // Rotar la cámara
            Vector3 currentRot = transform.localEulerAngles;
            transform.localRotation = Quaternion.Euler(currentRot.x - mouseY, currentRot.y + mouseX, 0);
        }
    }
}