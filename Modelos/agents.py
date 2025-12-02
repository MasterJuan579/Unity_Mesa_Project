from mesa import Agent
import numpy as np

PARKING = 3

class TrafficManagerAgent(Agent):
    """Agente Cerebro (Sin cambios)"""
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
    """Agente Cuerpo Físico (Sin cambios)"""
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
    Agente vehículo con Sistema Anti-Bloqueo (Anti-Gridlock)
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
        if self.state == "ARRIVED": return

        # --- DATOS DE NAVEGACIÓN ---
        current_pos = np.array(self.pos)
        next_pos = self.path[0] if self.path else None
        
        # Si no hay siguiente paso, no podemos movernos
        if next_pos is None:
            return

        # Vector de dirección deseada
        my_dx = next_pos[0] - current_pos[0]
        my_dy = next_pos[1] - current_pos[1]
        
        # Normalizamos el vector dirección para cálculos precisos
        norm = np.linalg.norm([my_dx, my_dy])
        if norm > 0:
            dir_vector = np.array([my_dx, my_dy]) / norm
        else:
            dir_vector = np.array([0, 0])

        # --- CONTEXTO ---
        cx, cy = int(self.pos[0]), int(self.pos[1])
        is_in_parking = False
        if 0 <= cx < len(self.model.city_layout) and 0 <= cy < len(self.model.city_layout[0]):
            if self.model.city_layout[cx][cy] == PARKING:
                is_in_parking = True

        # Escaneamos el entorno
        neighbors = self.model.space.get_neighbors(self.pos, radius=3.5, include_center=False)
        
        obstacle_ahead = False
        emergency_brake = False
        traffic_light = None
        
        # Variables para la lógica de "Reactivación"
        blocking_car_distance = 999.9

        for agent in neighbors:
            # --- COCHES ---
            if isinstance(agent, VehicleAgent):
                if agent.state == "ARRIVED": continue

                other_pos = np.array(agent.pos)
                vec_to_other = other_pos - current_pos
                dist = np.linalg.norm(vec_to_other)

                # 1. FILTRO DE ÁNGULO (¿Está realmente enfrente?)
                # Usamos el producto punto normalizado. 
                # Si es > 0.7, el coche está en un cono de 45 grados frente a mí.
                # Esto es más preciso que solo dx/dy.
                angle_match = np.dot(dir_vector, vec_to_other / (dist + 0.0001))
                
                if angle_match > 0.7:  # Está en mi carril y enfrente
                    if dist < blocking_car_distance:
                        blocking_car_distance = dist # Registramos al coche más cercano enfrente
                    
                    if dist < 0.9: # Muy cerca
                        emergency_brake = True
                        obstacle_ahead = True
                    elif dist < 1.8: # Cerca
                        obstacle_ahead = True

                # 2. CASO ESPECIAL: SALIDA DE PARKING (Se mantiene la precaución)
                if is_in_parking:
                    # Checamos si el otro coche está en la calle hacia donde voy
                    dist_to_target = np.linalg.norm(other_pos - np.array(next_pos))
                    # Si alguien está bloqueando mi meta (distancia < 1.5), espero
                    if dist_to_target < 1.5: 
                        obstacle_ahead = True
                        emergency_brake = True

            # --- SEMÁFOROS ---
            elif isinstance(agent, TrafficLightAgent):
                # Solo obedecer semáforos en mi celda destino EXACTA
                dist_light = self.model.space.get_distance(agent.pos, next_pos)
                if dist_light < 0.1:
                    traffic_light = agent

        # --- LÓGICA DE DECISIÓN ---
        target_speed = self.max_speed
        
        # Prioridad 1: Semáforo
        light_is_red = False
        if traffic_light:
            if traffic_light.state == "RED":
                target_speed = 0
                light_is_red = True
                self.speed = 0
            elif traffic_light.state == "YELLOW":
                target_speed = self.max_speed * 0.5

        # Prioridad 2: Obstáculos Físicos
        if obstacle_ahead:
            target_speed = 0
            self.state = "BRAKING"
            if emergency_brake:
                self.speed = 0
        
        # --- PRIORIDAD 3: SISTEMA ANTI-BLOQUEO (KICKSTART) ---
        # Si estoy detenido, NO hay semáforo en rojo, y el coche de enfrente 
        # está lejos (o no existe), entonces ¡ARRANCA!
        if self.speed < 0.01 and not light_is_red:
            # Si el coche más cercano enfrente está a más de 1.2 celdas de distancia
            if blocking_car_distance > 1.2:
                target_speed = self.max_speed # Forzamos la intención de movernos
                # Pequeño empujón inicial para romper la inercia del frenado
                self.speed = 0.1 

        # --- FÍSICA ---
        if target_speed > self.speed:
            self.speed += self.acceleration
        elif target_speed < self.speed:
            self.speed -= self.acceleration
            
        if self.speed < 0: self.speed = 0

    def advance(self):
        if self.state == "ARRIVED": return

        if self.speed > 0 and self.path:
            target = self.path[0]
            current = np.array(self.pos)
            
            # Vector hacia el objetivo
            vec_to_target = np.array(target) - current
            dist_to_target = np.linalg.norm(vec_to_target)
            
            # Si estamos muy cerca o nos pasamos, llegamos al nodo
            if dist_to_target < self.speed:
                new_pos = target
                self.path.pop(0)
                self.model.space.move_agent(self, tuple(new_pos))
                if not self.path:
                    self.state = "ARRIVED"
                    self.model.space.remove_agent(self)
            else:
                # Normalizamos el vector para movernos exactamente "speed" unidades
                norm_dir = vec_to_target / dist_to_target
                new_pos = current + norm_dir * self.speed
                self.model.space.move_agent(self, tuple(new_pos))