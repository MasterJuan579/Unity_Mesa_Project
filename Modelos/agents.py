from mesa import Agent
import numpy as np

PARKING = 3

class TrafficManagerAgent(Agent):
    """
    Agente 'Cerebro' que controla el ciclo de los semáforos.
    No tiene posición física, solo gestiona el tiempo y la sincronización.
    """
    def __init__(self, unique_id, model, green_time=20, yellow_time=4):
        super().__init__(model)
        self.unique_id = unique_id
        self.green_time = green_time
        self.yellow_time = yellow_time
        self.state = "RED"
        self.time_remaining = 0
        self.next_manager = None 

    def set_next(self, manager_agent):
        self.next_manager = manager_agent

    def activate(self):
        self.state = "GREEN"
        self.time_remaining = self.green_time

    def step(self):
        if self.state == "GREEN":
            self.time_remaining -= 1
            if self.time_remaining <= 0:
                self.state = "YELLOW"
                self.time_remaining = self.yellow_time
        elif self.state == "YELLOW":
            self.time_remaining -= 1
            if self.time_remaining <= 0:
                self.state = "RED"
                if self.next_manager:
                    self.next_manager.activate()

class TrafficLightAgent(Agent):
    """
    Agente físico que representa la luz del semáforo en el mapa.
    Su estado es un reflejo directo de su TrafficManager asignado.
    """
    def __init__(self, unique_id, model, manager):
        super().__init__(model)
        self.unique_id = unique_id
        self.manager = manager

    @property
    def state(self):
        return self.manager.state
    
    @state.setter
    def state(self, value):
        pass

    def step(self):
        pass

    def receive_eta(self, vehicle_id, eta):
        pass

class VehicleAgent(Agent):
    """
    Agente vehículo con lógica de navegación, evasión de obstáculos 
    y reglas de prioridad (Derecho de Paso).
    """
    def __init__(self, unique_id, model, start_node, destination_node):
        super().__init__(model)
        self.unique_id = unique_id
        self.start = start_node
        self.destination = destination_node
        self.velocity = np.array([0.0, 0.0])
        self.speed = 0.0
        self.max_speed = 0.5
        self.acceleration = 0.05
        self.path = []
        self.state = "DRIVING"

    def step(self):
        if self.state == "ARRIVED":
            return

        # --- Contexto: ¿Estoy en un estacionamiento? ---
        cx, cy = int(self.pos[0]), int(self.pos[1])
        is_in_parking = False
        if 0 <= cx < len(self.model.city_layout) and 0 <= cy < len(self.model.city_layout[0]):
            if self.model.city_layout[cx][cy] == PARKING:
                is_in_parking = True

        # 1. Percepción: Radio amplio (5.0) para anticipar tráfico rápido
        neighbors = self.model.space.get_neighbors(self.pos, radius=5.0, include_center=False)
        
        obstacle_ahead = False
        emergency_brake = False
        traffic_light = None
        
        next_step_pos = self.path[0] if self.path else None
        current_pos = np.array(self.pos)
        
        for agent in neighbors:
            # --- Detección de Vehículos ---
            if isinstance(agent, VehicleAgent):
                if agent.state == "ARRIVED": continue

                # Verificar si el otro vehículo está en estacionamiento
                ox, oy = int(agent.pos[0]), int(agent.pos[1])
                other_in_parking = False
                if 0 <= ox < len(self.model.city_layout) and 0 <= oy < len(self.model.city_layout[0]):
                    if self.model.city_layout[ox][oy] == PARKING:
                        other_in_parking = True

                # Regla 1: Prioridad de Avenida
                # Si yo voy por la calle y el otro está en parking, lo ignoro.
                if not is_in_parking and other_in_parking:
                    continue 

                other_pos = np.array(agent.pos)
                dist = np.linalg.norm(other_pos - current_pos)
                
                # Regla 2: Salida segura del estacionamiento
                if is_in_parking and not other_in_parking:
                    # Si está lejos (> 4.5), salir.
                    if dist > 4.5:
                        continue
                        
                    # Si está cerca, verificar si se acerca o se aleja
                    other_next_step = agent.path[0] if agent.path else None
                    is_approaching = True 
                    
                    if other_next_step is not None:
                        dist_now = dist
                        dist_future = np.linalg.norm(np.array(other_next_step) - current_pos)
                        # Si la distancia futura es mayor o igual, el coche ya pasó.
                        if dist_future >= dist_now:
                            is_approaching = False
                    
                    # Solo ceder el paso si el coche se está acercando peligrosamente
                    if is_approaching:
                        obstacle_ahead = True
                        emergency_brake = True
                        continue
                    else:
                        continue

                # Regla 3: Seguimiento normal (Misma vía)
                is_in_front = False
                if next_step_pos is not None:
                    my_direction = np.array(next_step_pos) - current_pos
                    vector_to_other = other_pos - current_pos
                    
                    norm_dir = np.linalg.norm(my_direction)
                    norm_other = np.linalg.norm(vector_to_other)
                    
                    if norm_dir > 0 and norm_other > 0:
                        # Normalize and check angle (approx 25 degrees -> 0.9)
                        dot_product = np.dot(my_direction / norm_dir, vector_to_other / norm_other)
                        if dot_product > 0.9:
                            is_in_front = True

                if is_in_front:
                    if dist < 0.9:
                        emergency_brake = True
                        obstacle_ahead = True
                    elif dist < 1.2:
                        obstacle_ahead = True
            
            # --- Detección de Semáforos ---
            elif isinstance(agent, TrafficLightAgent):
                # Solo obedecer si el semáforo está en mi siguiente paso inmediato
                if next_step_pos is not None:
                    dist_to_light = self.model.space.get_distance(agent.pos, next_step_pos)
                    if dist_to_light < 0.1:
                        traffic_light = agent

        # --- Cálculo de Velocidad ---
        target_speed = self.max_speed
        
        if traffic_light:
            if traffic_light.state == "RED":
                target_speed = 0
                self.speed = 0 
            elif traffic_light.state == "YELLOW":
                target_speed = self.max_speed * 0.5
        
        if obstacle_ahead:
            target_speed = 0
            self.state = "BRAKING"
            if emergency_brake:
                self.speed = 0 
        
        # Física de movimiento
        if target_speed > self.speed:
            self.speed += self.acceleration
        elif target_speed < self.speed:
            self.speed -= self.acceleration
            
        if self.speed < 0: 
            self.speed = 0

    def advance(self):
        if self.state == "ARRIVED":
            return

        if self.speed > 0 and self.path:
            target = self.path[0]
            current = np.array(self.pos)
            direction = np.array(target) - current
            dist = np.linalg.norm(direction)
            
            if dist < self.speed:
                new_pos = target
                self.path.pop(0)
                self.model.space.move_agent(self, tuple(new_pos))

                if not self.path:
                    self.state = "ARRIVED"
                    self.model.space.remove_agent(self)
            else:
                new_pos = current + (direction / dist) * self.speed
                self.model.space.move_agent(self, tuple(new_pos))