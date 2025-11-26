import mesa
from mesa import Model
from mesa.space import ContinuousSpace
from mesa.datacollection import DataCollector
import networkx as nx
from agents import VehicleAgent, TrafficLightAgent, TrafficManagerAgent

# --- CONSTANTES DE TIPOS DE CELDA ---
BUILDING = 0
ROAD = 1
ROUNDABOUT = 2
PARKING = 3
EMPTY = -1
MEDIAN = 4

class TrafficModel(Model):
    def __init__(self, num_vehicles=50): 
        super().__init__()
        self.num_vehicles = num_vehicles 
        self.vehicles_spawned = 0        
        self.step_count = 0
        
        # --- CONFIGURACIÓN DE COOLDOWN (ESPERA) ---
        # 30 pasos = 3 segundos reales aprox. (si speed=0.1)
        self.spawn_cooldown = 30 
        self.parking_schedule = {} 
        
        # --- ESPACIO Y AGENTES ---
        # Grid de 24x24
        self.space = ContinuousSpace(x_max=24, y_max=24, torus=False)
        self.agents_list = [] 
        # Inicializamos con EMPTY en lugar de BUILDING
        self.city_layout = [[EMPTY for y in range(24)] for x in range(24)]
        self.graph = nx.DiGraph()
        self.parking_spots = {} 
        self.traffic_lights = [] 
        
        # Construimos el mapa (calles y conexiones)
        self.build_city_graph()
        self.build_buildings()
        self.build_medians()
        
        # ===================================================
        #       1. GESTORES DE TRÁFICO (CEREBROS)
        # ===================================================
        # Creamos managers para controlar los semáforos
        # (Simplificado: un manager por intersección o grupo)
        
        # Manager 1: Top Right (Col 21, Row 5)
        m1 = TrafficManagerAgent("Manager1", self, green_time=20)
        m1.activate()
        
        # Manager 2: Top Left (Col 3, Row 5)
        m2 = TrafficManagerAgent("Manager2", self, green_time=20)
        m2.activate()
        
        # Manager 3: Center Left (Col 3, Row 9)
        m3 = TrafficManagerAgent("Manager3", self, green_time=20)
        m3.activate()
        
        # Manager 4: Center Right (Col 21, Row 11)
        m4 = TrafficManagerAgent("Manager4", self, green_time=20)
        m4.activate()
        
        # Manager 5: Bottom Left (Col 8, Row 22)
        m5 = TrafficManagerAgent("Manager5", self, green_time=20)
        m5.activate()
        
        # Manager 6: Bottom Right (Col 13, Row 22)
        m6 = TrafficManagerAgent("Manager6", self, green_time=20)
        m6.activate()
        
        # Manager 7: Top Center (Col 12, Row 1)
        m7 = TrafficManagerAgent("Manager7", self, green_time=20)
        m7.activate()

        self.agents_list.extend([m1, m2, m3, m4, m5, m6, m7])
        
        # ===================================================
        #       2. SEMÁFOROS FÍSICOS (LUCES)
        # ===================================================
        # Posiciones basadas en los bloques rojos de la imagen
        # (x, y, manager)
        light_position = [
            (21, 5, m1),
            (3, 5, m2),
            (3, 9, m3),
            (21, 11, m4),
            (8, 22, m5),
            (13, 22, m6),
            (12, 1, m7), (12, 2, m7) # Bloque doble arriba
        ]
        
        for (x, y, manager) in light_position:
            pos = (x + 0.5, y + 0.5)
            tl_agent = TrafficLightAgent(f"TL_{x}_{y}", self, manager)
            self.space.place_agent(tl_agent, pos)
            self.agents_list.append(tl_agent)
            self.traffic_lights.append(tl_agent)

        # ===================================================
        #       3. ESTACIONAMIENTOS (PARKINGS)
        # ===================================================
        # Posiciones basadas en los bloques amarillos de la imagen
        # IDs arbitrarios para mapear
        self.parking_spots = {
             13: (3, 3),
             2: (13, 3),
             10: (20, 3),
             17: (8, 7),
             5: (13, 7),
             8: (19, 8),
             12: (3, 13),
             15: (8, 15),
             3: (14, 15),
             7: (19, 13),
             16: (8, 19),
             1: (13, 19),
             11: (22, 16),
             14: (3, 21),
             4: (13, 21),
             6: (19, 19),
             9: (20, 21)
        }
        
        # Inicializamos historial de uso
        for pid in self.parking_spots:
            self.parking_schedule[pid] = -self.spawn_cooldown
        
        # ===================================================
        #       4. RECOLECCIÓN DE DATOS
        # ===================================================
        self.datacollector = DataCollector(
            model_reporters={
                "Stopped_Cars": lambda m: sum(1 for a in m.agents_list if isinstance(a, VehicleAgent) and a.speed < 0.01),
                "Average_Speed": lambda m: self.get_avg_speed()
            }
        )
        
        # Generación inicial de vehículos
        self.spawn_vehicles()

    # --- MÉTODOS AUXILIARES ---
    def get_avg_speed(self):
        speeds = [a.speed for a in self.agents_list if isinstance(a, VehicleAgent)]
        return sum(speeds) / len(speeds) if speeds else 0
    
    def get_nearest_node(self, pos):
        return min(self.graph.nodes, key=lambda n: (n[0]-pos[0])**2 + (n[1]-pos[1])**2)

    def spawn_vehicles(self):
        """ Genera coches nuevos respetando cooldown y espacio disponible. """
        if self.vehicles_spawned >= self.num_vehicles:
            return

        parking_ids = list(self.parking_spots.keys())
        free_spots = []
        
        for pid in parking_ids:
            # Verificar Cooldown
            last_used_step = self.parking_schedule.get(pid, -999)
            if (self.step_count - last_used_step) < self.spawn_cooldown:
                continue 

            # Verificar Espacio Físico
            pos = self.parking_spots[pid]
            cell_contents = self.space.get_neighbors(pos, radius=0.4, include_center=True)
            is_free = not any(isinstance(agent, VehicleAgent) for agent in cell_contents)
            
            if is_free:
                free_spots.append(pid)

        self.random.shuffle(free_spots) 
        
        for start_id in free_spots:
            if self.vehicles_spawned >= self.num_vehicles:
                break
                
            dest_id = self.random.choice([pid for pid in parking_ids if pid != start_id])
            start_pos = self.parking_spots[start_id]
            dest_pos = self.parking_spots[dest_id]
            start_node = self.get_nearest_node(start_pos)
            dest_node = self.get_nearest_node(dest_pos)
            
            try:
                path_nodes = nx.shortest_path(self.graph, start_node, dest_node, weight='weight')
                vehicle = VehicleAgent(f"Car_{self.vehicles_spawned}", self, start_node, dest_node)
                vehicle.path = [(x + 0.5, y + 0.5) for x, y in path_nodes]
                
                spawn_pos = (start_pos[0] + 0.5, start_pos[1] + 0.5)
                self.space.place_agent(vehicle, spawn_pos)
                self.agents_list.append(vehicle)
                
                self.vehicles_spawned += 1
                self.parking_schedule[start_id] = self.step_count
                
            except nx.NetworkXNoPath:
                continue

    def step(self):
        self.spawn_vehicles()
        
        # Limpieza de agentes que ya llegaron
        self.agents_list = [a for a in self.agents_list if getattr(a, "state", "") != "ARRIVED"]

        self.datacollector.collect(self)
        self.random.shuffle(self.agents_list)
        
        for agent in self.agents_list:
            agent.step()
        for agent in self.agents_list:
            if hasattr(agent, "advance"):
                agent.advance()     
        self.step_count += 1

    # =======================================================
    #               CONSTRUCCIÓN DEL GRAFO VIAL
    # =======================================================
    def build_city_graph(self):
        def add_line(start, end, direction, weight=1):
            curr = list(start)
            # Asegurar que el bucle termine
            max_iters = 100
            iters = 0
            while iters < max_iters:
                node_curr = tuple(curr)
                
                # Añadir nodo actual
                self.graph.add_node(node_curr)
                self.city_layout[curr[0]][curr[1]] = ROAD
                
                if curr == list(end):
                    break
                    
                next_x = curr[0] + direction[0]
                next_y = curr[1] + direction[1]
                node_next = (next_x, next_y)
                
                if not (0 <= next_x < 24 and 0 <= next_y < 24): break
                
                self.graph.add_node(node_next)
                self.graph.add_edge(node_curr, node_next, weight=weight)
                self.city_layout[next_x][next_y] = ROAD
                
                curr[0], curr[1] = next_x, next_y
                iters += 1

        # ---------------------------------------------------
        # 1. PERÍMETRO (Ring Exterior)
        # ---------------------------------------------------
        add_line((23, 0), (0, 0), (-1, 0))   # Top (Left)
        add_line((0, 0), (0, 23), (0, 1))    # Left (Down)
        add_line((0, 23), (23, 23), (1, 0))  # Bottom (Right)
        add_line((23, 23), (23, 0), (0, -1)) # Right (Up)

        # ---------------------------------------------------
        # 2. CARRETERAS VERTICALES
        # ---------------------------------------------------
        add_line((3, 3), (3, 22), (0, 1))    # Col 4 (Down)
        add_line((8, 3), (8, 22), (0, 1))    # Col 9 (Down)
        add_line((11, 3), (11, 22), (0, 1))  # Col 12 (Down)
        add_line((12, 22), (12, 3), (0, -1)) # Col 13 (Up)
        add_line((15, 12), (15, 22), (0, 1)) # Col 16 (Down) - Ajustado inicio
        add_line((20, 3), (20, 22), (0, 1))  # Col 21 (Down)

        # ---------------------------------------------------
        # 3. CARRETERAS HORIZONTALES
        # ---------------------------------------------------
        add_line((23, 5), (0, 5), (-1, 0))   # Row 6 (Left)
        add_line((23, 9), (0, 9), (-1, 0))   # Row 10 (Left)
        add_line((0, 11), (23, 11), (1, 0))  # Row 12 (Right)
        add_line((12, 16), (0, 16), (-1, 0)) # Row 17 Left (Left)
        add_line((0, 17), (12, 17), (1, 0))  # Row 18 Left (Right)

        # ---------------------------------------------------
        # 4. ROTONDA CENTRAL / CRUCE
        # ---------------------------------------------------
        # Cuadro café en (10,9) a (11,10) (Indices)
        # Imagen: x=11-12, y=10-11 -> Indices x=10-11, y=9-10
        for x in range(10, 12):
            for y in range(9, 11):
                self.city_layout[x][y] = ROUNDABOUT
        
        # ---------------------------------------------------
        # 5. CONEXIÓN DE ESTACIONAMIENTOS
        # ---------------------------------------------------
        road_nodes = list(self.graph.nodes)
        for pid, pos in self.parking_spots.items():
            self.graph.add_node(pos)
            self.city_layout[pos[0]][pos[1]] = PARKING
            nearest = min(road_nodes, key=lambda n: (n[0]-pos[0])**2 + (n[1]-pos[1])**2)
            self.graph.add_edge(pos, nearest, weight=1)
            self.graph.add_edge(nearest, pos, weight=1)
    # =======================================================
    #               CONSTRUCCIÓN DE EDIFICIOS
    # =======================================================
    # =======================================================
    #               CONSTRUCCIÓN DE EDIFICIOS
    # =======================================================
    def build_buildings(self):
        # Helper para llenar rectángulos de edificios
        def fill_rect(x1, x2, y1, y2):
            for x in range(x1, x2 + 1):
                for y in range(y1, y2 + 1):
                    # Solo sobrescribir si está vacío (no borrar carreteras)
                    if self.city_layout[x][y] == EMPTY:
                        self.city_layout[x][y] = BUILDING

        # Coordenadas basadas en la imagen (Indices 0-23)
        # --- FILA SUPERIOR ---
        fill_rect(2, 3, 2, 3)     # C3-4, R3-4
        fill_rect(5, 7, 2, 3)     # C6-8, R3-4
        fill_rect(12, 21, 2, 3)   # C13-22, R3-4
        
        # --- FILA SEGUNDA ---
        fill_rect(2, 3, 6, 7)     # C3-4, R7-8
        fill_rect(5, 7, 6, 7)     # C6-8, R7-8
        fill_rect(12, 21, 6, 7)   # C13-22, R7-8
        
        # --- FILA TERCERA ---
        fill_rect(2, 3, 12, 15)   # C3-4, R13-16
        fill_rect(5, 7, 12, 15)   # C6-8, R13-16
        fill_rect(12, 15, 12, 14) # C13-16, R13-15
        fill_rect(17, 21, 12, 21) # C18-22, R13-22 (Gran bloque derecho)
        
        # --- FILA INFERIOR ---
        fill_rect(2, 7, 18, 21)   # C3-8, R19-22 (Gran bloque izquierdo)
        fill_rect(12, 15, 17, 21) # C13-16, R18-22

    # =======================================================
    #               CONSTRUCCIÓN DE CAMELLONES (VERDE)
    # =======================================================
    def build_medians(self):
        def fill_median(x1, x2, y1, y2):
            for x in range(x1, x2 + 1):
                for y in range(y1, y2 + 1):
                    if self.city_layout[x][y] == EMPTY:
                        self.city_layout[x][y] = MEDIAN

        # Coordenadas basadas en la imagen (Indices 0-23)
        fill_median(0, 1, 3, 3)     # C1-2, R4
        fill_median(0, 1, 7, 7)     # C1-2, R8
        fill_median(10, 11, 2, 2)   # C11-12, R3
        fill_median(22, 23, 6, 6)   # C23-24, R7
        fill_median(22, 23, 12, 12) # C23-24, R13
        fill_median(7, 8, 21, 21)   # C8-9, R22
        fill_median(15, 16, 21, 21) # C16-17, R22
