import mesa
from mesa import Model
from mesa.space import ContinuousSpace, MultiGrid

from mesa.datacollection import DataCollector
import networkx as nx
from agents import VehicleAgent, TrafficLightAgent, TrafficManagerAgent

# --- CONSTANTES DE TIPOS DE CELDA ---
BUILDING = 0
ROAD = 1
ROUNDABOUT = 2
PARKING = 3
EMPTY = -1
MEDIAN = 4 # Used for thick lines in app.py, but here we can use it for logic if needed.
GREEN_ZONE = 5
RED_ZONE = 6

class TrafficModel(Model):
    def __init__(self, num_vehicles=50): 
        super().__init__()
        self.num_vehicles = num_vehicles
        self.vehicles_spawned = 0        
        self.step_count = 0
        
        self.grid = MultiGrid(74, 74, torus=False)
        # self.schedule = RandomActivation(self) # Removed in Mesa 3.0
        self.running = True      # --- CONFIGURACIÓN DE COOLDOWN (ESPERA) ---
        # 30 pasos = 3 segundos reales aprox. (si speed=0.1)
        self.spawn_cooldown = 30 
        self.parking_schedule = {} 
        
        # --- ESPACIO Y AGENTES ---
        # Grid de 25x25
        self.space = ContinuousSpace(x_max=74, y_max=74, torus=False)
        self.agents_list = [] 
        # Inicializamos con EMPTY en lugar de BUILDING
        self.city_layout = [[EMPTY for y in range(74)] for x in range(74)]
        self.graph = nx.DiGraph()
        self.parking_spots = {} 
        self.traffic_lights = [] 
        
        # Construimos el mapa (calles y conexiones)
        self.build_city_graph()
        self.build_city_graph()
        self.build_buildings()
        self.build_static_zones()
        self.median_lines = []
        self.build_median_lines()
        
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
        # m7.activate() # Don't activate all at once
        
        # Link Managers in a Cycle to ensure continuous flow
        m1.set_next(m2)
        m2.set_next(m3)
        m3.set_next(m4)
        m4.set_next(m5)
        m5.set_next(m6)
        m6.set_next(m7)
        m7.set_next(m1)
        
        # Start the cycle
        m1.activate()

        self.agents_list.extend([m1, m2, m3, m4, m5, m6, m7])
        
        # ===================================================
        #       2. SEMÁFOROS FÍSICOS (LUCES)
        # ===================================================
        # Posiciones basadas en los bloques rojos de la imagen
        # (x, y, manager)
        light_position = [
            # Semáforos Verdes
            (1, 4, m2), (2, 4, m2),
            (1, 8, m3), (2, 8, m3),
            (9, 22, m5), (10, 22, m5),
            (11, 3, m7), (12, 3, m7),
            (17, 22, m6), (18, 22, m6), # Split again
            (23, 7, m4), (24, 7, m4), 
            (23, 13, m4), (24, 13, m4),

            # Semáforos Rojos
            (3, 5, m2), (3, 6, m2), # Split again
            (3, 9, m3), (3, 10, m3),
            (8, 23, m5), (8, 24, m5),
            (13, 1, m7), (13, 2, m7),
            (15, 23, m6), (15, 24, m6),
            (22, 5, m1), (22, 6, m1), # Split again
            (22, 11, m4), (22, 12, m4)
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
             13: (4, 4),
             2: (14, 4),
             10: (21, 3),
             17: (8, 7),
             5: (15, 7),
             8: (20, 8),
             12: (4, 13),
             15: (7, 16),
             3: (15, 15),
             7: (20, 13),
             16: (7, 19),
             1: (13, 19),
             11: (22, 17),
             14: (5, 22),
             4: (15, 22),
             6: (19, 20),
             9: (21, 22)
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
        
        # Mesa 3.0: Use agents.shuffle_do("step") instead of schedule.step()
        self.agents.shuffle_do("step")
        
        # for agent in self.agents_list:
        #     agent.step()
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
            max_iters = 100
            iters = 0
            while iters < max_iters:
                node_curr = tuple(curr)
                
                # Añadir nodo actual
                self.graph.add_node(node_curr)
                # Cast to int for grid access
                self.city_layout[int(curr[0])][int(curr[1])] = ROAD
                
                if curr == list(end):
                    break
                    
                next_x = curr[0] + direction[0]
                next_y = curr[1] + direction[1]
                node_next = (next_x, next_y)
                
                # Check bounds
                if not (0 <= next_x < 74 and 0 <= next_y < 74): break
                
                self.graph.add_node(node_next)
                self.graph.add_edge(node_curr, node_next, weight=weight)
                self.city_layout[int(next_x)][int(next_y)] = ROAD
                
                curr[0], curr[1] = next_x, next_y
                iters += 1

        # ===================================================
        #       DEFINICIÓN DE CALLES (Basado en Coordenadas Usuario)
        # ===================================================
        
        # ===================================================
        #       DEFINICIÓN DE CALLES (Unidireccionales)
        # ===================================================
        
        # --- CALLES VERTICALES ---
        # V1: X=1 (Perímetro Izquierdo) -> DOWN
        add_line((1, 23), (1, 1), (0, -1))

        # V2: X=5, X=6 (Entre Edificios 1/3/7 y 2/4/8) -> DOWN (Dos carriles)
        add_line((5, 18), (5, 1), (0, -1))
        add_line((6, 18), (6, 1), (0, -1))

        # V3: X=9 (Entre Edificios 2/4/8 y Glorieta) -> DOWN
        add_line((9, 23), (9, 1), (0, -1))

        # V4: X=12 (Entre Glorieta y Edificios 5/6/10/11) -> UP
        add_line((12, 1), (12, 23), (0, 1))

        # V5: X=17, X=18 (Entre Edificios 10/11 y 12) -> UP (Dos carriles)
        add_line((17, 1), (17, 23), (0, 1))
        add_line((18, 1), (18, 23), (0, 1))

        # V6: X=23 (Perímetro Derecho) -> UP
        add_line((23, 1), (23, 23), (0, 1))


        # --- CALLES HORIZONTALES ---
        # H1: Y=2 (Perímetro Superior) -> LEFT
        add_line((23, 2), (1, 2), (-1, 0))

        # H2: Y=5, Y=6 (Entre Edificios 1/2/5 y 3/4/6) -> LEFT (Dos carriles)
        add_line((23, 5), (1, 5), (-1, 0))
        add_line((23, 6), (1, 6), (-1, 0))

        # H3: Y=9 (Arriba de Glorieta) -> LEFT
        add_line((23, 9), (1, 9), (-1, 0))

        # H4: Y=12 (Abajo de Glorieta) -> RIGHT
        add_line((1, 12), (23, 12), (1, 0))

        # H5: Y=17, Y=18 (Entre Edificios 7/8/10/12 y 9/11) -> RIGHT (Dos carriles)
        add_line((1, 17), (23, 17), (1, 0))
        add_line((1, 18), (23, 18), (1, 0))

        # H6: Y=23 (Perímetro Inferior) -> RIGHT
        add_line((1, 23), (23, 23), (1, 0))

        # ---------------------------------------------------
        # 4. ROTONDA CENTRAL / CRUCE
        # ---------------------------------------------------
        # Coordenadas Usuario: 10,10 - 11,11
        for x in range(10, 12):
            for y in range(10, 12):
                self.city_layout[x][y] = ROUNDABOUT
        
        # Conectar rotonda a calles adyacentes (X=9, X=12, Y=9, Y=12)
        # Esto se hace implícitamente si las calles tocan, pero la rotonda es un obstáculo?
        # En el modelo anterior, la rotonda era transitable o tenía lógica especial?
        # Asumimos que las calles rodean la rotonda.
        # V3 (X=9) toca (9,10) y (9,11).
        # V4 (X=12) toca (12,10) y (12,11).
        # H3 (Y=9) toca (10,9) y (11,9).
        # H4 (Y=12) toca (10,12) y (11,12).
        
        # ---------------------------------------------------
        # 5. CONEXIÓN DE ESTACIONAMIENTOS
        # ---------------------------------------------------
        road_nodes = list(self.graph.nodes)
        for pid, pos in self.parking_spots.items():
            self.graph.add_node(pos)
            self.city_layout[pos[0]][pos[1]] = PARKING
            # Encontrar nodo de calle más cercano
            if road_nodes:
                nearest = min(road_nodes, key=lambda n: (n[0]-pos[0])**2 + (n[1]-pos[1])**2)
                self.graph.add_edge(pos, nearest, weight=1)
                self.graph.add_edge(nearest, pos, weight=1)
    # =======================================================
    #               CONSTRUCCIÓN DE EDIFICIOS
    # =======================================================
    # =======================================================
    #               CONSTRUCCIÓN DE EDIFICIOS
    def build_buildings(self):
        """
        Coloca celdas tipo BUILDING en las zonas ocupadas por edificios.
        Basado en las coordenadas del usuario.
        """
        # Lista de rectángulos (x_min, y_min, x_max, y_max) INCLUSIVOS
        buildings_rects = [
            (3, 3, 4, 4),    # Edificio 1
            (7, 3, 8, 4),    # Edificio 2
            (3, 7, 4, 8),    # Edificio 3
            (7, 7, 8, 8),    # Edificio 4
            (13, 3, 22, 4),  # Edificio 5
            (13, 7, 22, 8),  # Edificio 6
            (3, 13, 4, 16),  # Edificio 7
            (7, 13, 8, 16),  # Edificio 8 (aprox, user said 7,15-16 & 8,13-16)
            (3, 19, 8, 22),  # Edificio 9 (Bloque grande)
            (13, 13, 16, 15),# Edificio 10
            (13, 18, 16, 22),# Edificio 11
            (19, 13, 22, 22) # Edificio 12
        ]

        for (x_min, y_min, x_max, y_max) in buildings_rects:
            for x in range(x_min, x_max + 1):
                for y in range(y_min, y_max + 1):
                    # Solo marcar si no es otra cosa (aunque BUILDING suele ser base)
                    if self.city_layout[x][y] == EMPTY:
                        self.city_layout[x][y] = BUILDING

    # =======================================================
    #               ZONAS ESTÁTICAS (ROJO/VERDE)
    # =======================================================
    def build_static_zones(self):
        # Green Zones (Indices 0-23)
        # User: 1,4; 2,4 -> 0,3; 1,3
        # User: 1,8; 2,8 -> 0,7; 1,7
        # User: 9,22; 10,22 -> 8,21; 9,21
        # User: 11,3; 12,3 -> 10,2; 11,2
        # User: 17,22; 18,22 -> 16,21; 17,21
        # User: 23,7; 24,7 -> 22,6; 23,6
        # User: 23,13; 24,13 -> 22,12; 23,12
        green_coords = [
            (0,3), (1,3),
            (0,7), (1,7),
            (8,21), (9,21),
            (10,2), (11,2),
            (16,21), (17,21),
            (22,6), (23,6),
            (22,12), (23,12)
        ]
        for x, y in green_coords:
            if 0 <= x < 74 and 0 <= y < 74:
                self.city_layout[x][y] = GREEN_ZONE

        # Red Zones (Indices 0-23)
        # User: 3,5; 3,6 -> 2,4; 2,5
        # User: 3,9; 3,10 -> 2,8; 2,9
        # User: 8,23; 8,24 -> 7,22; 7,23
        # User: 13,1; 13,2 -> 12,0; 12,1
        # User: 15,23; 15,24 -> 14,22; 14,23
        # User: 22,5; 22,6 -> 21,4; 21,5
        # User: 22,11; 22,12 -> 21,10; 21,11
        red_coords = [
            (2,4), (2,5),
            (2,8), (2,9),
            (7,22), (7,23),
            (12,0), (12,1),
            (14,22), (14,23),
            (21,4), (21,5),
            (21,10), (21,11)
        ]
        for x, y in red_coords:
            if 0 <= x < 74 and 0 <= y < 74:
                self.city_layout[x][y] = RED_ZONE

    # =======================================================
    #               CAMELLONES (LÍNEAS GRUESAS)
    # =======================================================
    def build_median_lines(self):
        # Vertical lines (x=10.5 -> between col 11 and 12)
        # Segment 1: Row 1 to 9 (y=0 to y=8) -> y range [0, 9]
        self.median_lines.append(((10.5, 0), (10.5, 9)))
        
        # Segment 2: Row 12 to 24 (y=11 to y=23) -> y range [11, 24]
        self.median_lines.append(((10.5, 11), (10.5, 24)))
        
        # Horizontal lines (y=9.5 -> between row 10 and 11)
        # Segment 1: Col 1 to 9 (x=0 to x=8) -> x range [0, 9]
        self.median_lines.append(((0, 9.5), (9, 9.5)))
        
        # Segment 2: Col 12 to 24 (x=11 to x=23) -> x range [11, 24]
        self.median_lines.append(((11, 9.5), (24, 9.5)))
