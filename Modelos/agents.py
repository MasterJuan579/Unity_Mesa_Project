from mesa import Agent

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


class VehicleAgent(Agent):
    """
    Agente vehículo simplificado - movimiento discreto (1 celda por step)
    """
    def __init__(self, unique_id, model, start_node, destination_node):
        super().__init__(model)
        self.unique_id = unique_id
        self.start = start_node
        self.destination = destination_node
        self.path = []
        self.state = "DRIVING"

    def is_in_roundabout(self):
        """Verifica si el vehículo está dentro de la rotonda"""
        return self.pos in self.model.roundabout_ring

    def count_vehicles_in_roundabout(self):
        """Cuenta vehículos actualmente en la rotonda"""
        count = 0
        for agent in self.model.agents_list:
            if isinstance(agent, VehicleAgent) and agent is not self:
                if agent.state != "ARRIVED" and agent.pos in self.model.roundabout_ring:
                    count += 1
        return count

    def should_yield_at_roundabout(self):
        """Determina si debe ceder el paso antes de entrar a la rotonda"""
        if self.pos not in self.model.roundabout_entries:
            return False
        
        # Regla 1: Capacidad máxima
        if self.count_vehicles_in_roundabout() >= self.model.roundabout_capacity:
            return True
        
        # Regla 2: Ceder a vehículos circulando dentro
        for agent in self.model.agents_list:
            if agent is self or not isinstance(agent, VehicleAgent):
                continue
            if agent.state == "ARRIVED":
                continue
            if agent.is_in_roundabout():
                # Si el otro está cerca de mi entrada
                if agent.path:
                    dist = abs(agent.pos[0] - self.pos[0]) + abs(agent.pos[1] - self.pos[1])
                    if dist <= 2:
                        return True
        return False

    def can_move_to(self, next_pos):
        """Verifica si puede moverse a la siguiente celda"""
        # 1. Verificar semáforos
        cell_contents = self.model.grid.get_cell_list_contents([next_pos])
        for agent in cell_contents:
            if isinstance(agent, TrafficLightAgent) and agent.state == "RED":
                return False
        
        # 2. Verificar si hay otro vehículo
        for agent in cell_contents:
            if isinstance(agent, VehicleAgent) and agent.state != "ARRIVED":
                return False
        
        return True

    def step(self):
        if self.state == "ARRIVED":
            return
        
        # ¿Llegamos al destino?
        if not self.path:
            self.state = "ARRIVED"
            self.model.grid.remove_agent(self)
            return
        
        next_pos = self.path[0]
        
        # Verificar yield en rotonda
        if self.should_yield_at_roundabout():
            return
        
        # Verificar si podemos avanzar
        if not self.can_move_to(next_pos):
            return
        
        # Mover
        self.model.grid.move_agent(self, next_pos)
        self.path.pop(0)
        
        # Verificar si llegamos
        if not self.path:
            self.state = "ARRIVED"
            self.model.grid.remove_agent(self)