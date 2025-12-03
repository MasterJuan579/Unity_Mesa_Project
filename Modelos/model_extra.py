import mesa
from mesa import Model
from mesa.space import ContinuousSpace, MultiGrid
from mesa.datacollection import DataCollector
import networkx as nx
from agents import VehicleAgent, TrafficLightAgent, TrafficManagerAgent
import random

# --- CONSTANTES DE TIPOS DE CELDA ---
BUILDING = 0
ROAD = 1
ROUNDABOUT = 2
PARKING = 3
EMPTY = -1
MEDIAN = 4
GREEN_ZONE = 5
RED_ZONE = 6

class TrafficModel(Model):
    def __init__(self, num_vehicles=50): 
        super().__init__()
        self.num_vehicles = num_vehicles
        self.vehicles_spawned = 0        
        self.step_count = 0
        
        # Grid de 25x25 (0-24)
        self.grid = MultiGrid(25, 25, torus=False)
        self.running = True
        
        # 30 pasos = 3 segundos reales aprox. (si speed=0.1)
        self.spawn_cooldown = 30 
        self.parking_schedule = {} 
        
        # --- ESPACIO Y AGENTES ---
        self.space = ContinuousSpace(x_max=25, y_max=25, torus=False)
        self.agents_list = [] 
        self.city_layout = [[EMPTY for y in range(25)] for x in range(25)]
        self.graph = nx.DiGraph()
        self.parking_spots = {} 
        self.traffic_lights = [] 
        self.median_lines = []

        # ===================================================
        #       3. ESTACIONAMIENTOS (PARKINGS)
        # ===================================================
        # Invertimos Y: Y_new = 24 - Y_old
        self.parking_spots = {
             13: (4, 20),
             2: (14, 20),
             10: (21, 21),
             17: (8, 17),
             5: (15, 17),
             8: (20, 16),
             12: (4, 11),
             15: (7, 8),
             3: (15, 9),
             7: (20, 11),
             16: (7, 5),
             1: (13, 5),
             11: (22, 7),
             14: (5, 2),
             4: (15, 2),
             6: (19, 4),
             9: (21, 2)
        }
        
        for pid in self.parking_spots:
            self.parking_schedule[pid] = -self.spawn_cooldown
        
        # Construimos el mapa (calles y conexiones)
        self.build_city_graph()
        self.build_buildings()
        self.build_static_zones()
        self.build_median_lines()
        
        # ===================================================
        #       1. GESTORES DE TRÁFICO (CEREBROS)
        # ===================================================
        # Manager 1: Top Right (Col 21, Row 5) -> Y=19
        m1 = TrafficManagerAgent("Manager1", self, green_time=20)
        
        # Manager 2: Top Left (Col 3, Row 5) -> Y=19
        m2 = TrafficManagerAgent("Manager2", self, green_time=20)
        
        # Manager 3: Center Left (Col 3, Row 9) -> Y=15
        m3 = TrafficManagerAgent("Manager3", self, green_time=20)
        
        # Manager 4: Center Right (Col 21, Row 11) -> Y=13
        m4 = TrafficManagerAgent("Manager4", self, green_time=20)
        
        # Manager 5: Bottom Left (Col 8, Row 22) -> Y=2
        m5 = TrafficManagerAgent("Manager5", self, green_time=20)
        
        # Manager 6: Bottom Right (Col 13, Row 22) -> Y=2
        m6 = TrafficManagerAgent("Manager6", self, green_time=20)
        
        # Manager 7: Top Center (Col 12, Row 1) -> Y=23
        m7 = TrafficManagerAgent("Manager7", self, green_time=20)
        
        # Link Managers in a Cycle
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
        # Y = 24 - Row (aprox, ajustado a visual)
        light_position = [
            # Semáforos Verdes
            (1, 20, m2), (2, 20, m2),   # Map Row 4 -> Y=20
            (1, 16, m3), (2, 16, m3),   # Map Row 8 -> Y=16
            (9, 2, m5), (10, 2, m5),    # Map Row 22 -> Y=2
            (11, 21, m7), (12, 21, m7), # Map Row 3 -> Y=21
            (17, 2, m6), (18, 2, m6),   # Map Row 22 -> Y=2
            (23, 17, m4), (24, 17, m4), # Map Row 7 -> Y=17
            (23, 11, m4), (24, 11, m4), # Map Row 13 -> Y=11

            # Semáforos Rojos
            (3, 19, m2), (3, 18, m2),   # Map Row 5 -> Y=19, Row 6 -> Y=18
            (3, 15, m3), (3, 14, m3),   # Map Row 9 -> Y=15, Row 10 -> Y=14
            (8, 1, m5), (8, 0, m5),     # Map Row 23 -> Y=1, Row 24 -> Y=0
            (13, 23, m7), (13, 22, m7), # Map Row 1 -> Y=23, Row 2 -> Y=22
            (15, 1, m6), (15, 0, m6),   # Map Row 23 -> Y=1, Row 24 -> Y=0
            (22, 19, m1), (22, 18, m1), # Map Row 5 -> Y=19, Row 6 -> Y=18
            (22, 13, m4), (22, 12, m4)  # Map Row 11 -> Y=13, Row 12 -> Y=12
        ]
        
        for (x, y, manager) in light_position:
            pos = (x + 0.5, y + 0.5)
            tl_agent = TrafficLightAgent(f"TL_{x}_{y}", self, manager)
            self.space.place_agent(tl_agent, pos)
            self.agents_list.append(tl_agent)
            self.traffic_lights.append(tl_agent)


        
        # ===================================================
        #       4. RECOLECCIÓN DE DATOS
        # ===================================================
        self.datacollector = DataCollector(
            model_reporters={
                "Stopped_Cars": lambda m: sum(1 for a in m.agents_list if isinstance(a, VehicleAgent) and a.speed < 0.01),
                "Average_Speed": lambda m: self.get_avg_speed()
            }
        )
        
        self.spawn_vehicles()

    def get_avg_speed(self):
        speeds = [a.speed for a in self.agents_list if isinstance(a, VehicleAgent)]
        return sum(speeds) / len(speeds) if speeds else 0
    
    def get_nearest_node(self, pos):
        return min(self.graph.nodes, key=lambda n: (n[0]-pos[0])**2 + (n[1]-pos[1])**2)

    def spawn_vehicles(self):
        if self.vehicles_spawned >= self.num_vehicles:
            return

        parking_ids = list(self.parking_spots.keys())
        free_spots = []
        
        for pid in parking_ids:
            last_used_step = self.parking_schedule.get(pid, -999)
            if (self.step_count - last_used_step) < self.spawn_cooldown:
                continue 

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
        self.agents_list = [a for a in self.agents_list if getattr(a, "state", "") != "ARRIVED"]
        self.datacollector.collect(self)
        self.random.shuffle(self.agents_list)
        self.agents.shuffle_do("step")
        for agent in self.agents_list:
            if hasattr(agent, "advance"):
                agent.advance()     
        self.step_count += 1

    def build_city_graph(self):
        def add_line(start, end, direction, weight=1):
            curr = list(start)
            max_iters = 100
            iters = 0
            while iters < max_iters:
                node_curr = tuple(curr)
                self.graph.add_node(node_curr)
                self.city_layout[int(curr[0])][int(curr[1])] = ROAD
                
                if curr == list(end):
                    break
                    
                next_x = curr[0] + direction[0]
                next_y = curr[1] + direction[1]
                node_next = (next_x, next_y)
                
                if not (0 <= next_x < 25 and 0 <= next_y < 25): break
                
                self.graph.add_node(node_next)
                self.graph.add_edge(node_curr, node_next, weight=weight)
                self.city_layout[int(next_x)][int(next_y)] = ROAD
                
                curr[0], curr[1] = next_x, next_y
                iters += 1

        # --- CALLES VERTICALES (Y invertido no afecta X, pero sí dirección UP/DOWN) ---
        # V1: X=1 (Perímetro Izquierdo) -> DOWN
        add_line((1, 23), (1, 1), (0, -1))

        # V2: X=5, X=6 -> DOWN
        add_line((5, 18), (5, 1), (0, -1))
        add_line((6, 18), (6, 1), (0, -1))

        # V3: X=9 -> DOWN
        add_line((9, 23), (9, 1), (0, -1))

        # V4: X=12 -> UP
        add_line((12, 1), (12, 23), (0, 1))

        # V5: X=17, X=18 -> UP
        add_line((17, 1), (17, 23), (0, 1))
        add_line((18, 1), (18, 23), (0, 1))

        # V6: X=23 -> UP
        add_line((23, 1), (23, 23), (0, 1))

        # --- CALLES HORIZONTALES (Y invertido) ---
        # H1: Y=0 (Antes Y=24) -> RIGHT
        add_line((1, 0), (23, 0), (1, 0))

        # H2: Y=19, Y=18 (Antes Row 5,6) -> RIGHT
        add_line((1, 19), (23, 19), (1, 0))
        add_line((1, 18), (23, 18), (1, 0))

        # H3: Y=12 (Antes Row 12) -> RIGHT
        add_line((1, 12), (23, 12), (1, 0))

        # H4: Y=15 (Antes Row 9) -> LEFT
        add_line((23, 15), (1, 15), (-1, 0))

        # H5: Y=7, Y=6 (Antes Row 17,18) -> LEFT
        add_line((23, 7), (1, 7), (-1, 0))
        add_line((23, 6), (1, 6), (-1, 0))

        # H6: Y=23 (Antes Row 1) -> LEFT
        add_line((23, 23), (1, 23), (-1, 0))

        # --- ROTONDA CENTRAL (Y=13,14) ---
        r_nodes = [(11,13), (11,14), (10,14), (10,13)]
        for node in r_nodes:
            self.graph.add_node(node)
            self.city_layout[node[0]][node[1]] = ROUNDABOUT

        self.graph.add_edge((11,13), (11,14), weight=1) # Up
        self.graph.add_edge((11,14), (10,14), weight=1) # Left
        self.graph.add_edge((10,14), (10,13), weight=1) # Down
        self.graph.add_edge((10,13), (11,13), weight=1) # Right

        # --- CONEXIONES ROTONDA ---
        # V3 (X=9, Down) -> Entrada (9,14)->(10,14), Salida (10,13)->(9,13)
        self.graph.add_edge((9,14), (10,14), weight=1)
        self.graph.add_edge((10,13), (9,13), weight=1)

        # V4 (X=12, Up) -> Entrada (12,13)->(11,13), Salida (11,14)->(12,14)
        self.graph.add_edge((12,13), (11,13), weight=1)
        self.graph.add_edge((11,14), (12,14), weight=1)

        # H3 (Y=12, Right) -> Entrada (10,12)->(10,13), Salida (11,13)->(11,12)
        self.graph.add_edge((10,12), (10,13), weight=1)
        self.graph.add_edge((11,13), (11,12), weight=1)

        # H4 (Y=15, Left) -> Entrada (11,15)->(11,14), Salida (10,14)->(10,15)
        self.graph.add_edge((11,15), (11,14), weight=1)
        self.graph.add_edge((10,14), (10,15), weight=1)
        
        # --- CONEXIÓN DE ESTACIONAMIENTOS ---
        road_nodes = list(self.graph.nodes)
        for pid, pos in self.parking_spots.items():
            self.graph.add_node(pos)
            self.city_layout[pos[0]][pos[1]] = PARKING
            if road_nodes:
                nearest = min(road_nodes, key=lambda n: (n[0]-pos[0])**2 + (n[1]-pos[1])**2)
                self.graph.add_edge(pos, nearest, weight=1)
                self.graph.add_edge(nearest, pos, weight=1)

    def build_buildings(self):
        # Invert Y: y_new = 24 - y_old
        # Rects: (x_min, y_min, x_max, y_max)
        # Note: If we invert y_min and y_max, y_max becomes smaller than y_min. Swap them.
        buildings_rects = [
            (3, 20, 4, 21),    # Edificio 1 (Before 3,3-4,4 -> 24-4=20, 24-3=21)
            (7, 20, 8, 21),    # Edificio 2
            (3, 16, 4, 17),    # Edificio 3
            (7, 16, 8, 17),    # Edificio 4
            (13, 20, 22, 21),  # Edificio 5
            (13, 16, 22, 17),  # Edificio 6
            (3, 8, 4, 11),     # Edificio 7 (Before 3,13-4,16 -> 24-16=8, 24-13=11)
            (7, 8, 8, 11),     # Edificio 8
            (3, 2, 8, 5),      # Edificio 9 (Before 3,19-8,22 -> 24-22=2, 24-19=5)
            (13, 9, 16, 11),   # Edificio 10 (Before 13,13-16,15 -> 24-15=9, 24-13=11)
            (13, 2, 16, 6),    # Edificio 11 (Before 13,18-16,22 -> 24-22=2, 24-18=6)
            (19, 2, 22, 11)    # Edificio 12 (Before 19,13-22,22 -> 24-22=2, 24-13=11)
        ]

        for (x_min, y_min, x_max, y_max) in buildings_rects:
            for x in range(x_min, x_max + 1):
                for y in range(y_min, y_max + 1):
                    if self.city_layout[x][y] == EMPTY:
                        self.city_layout[x][y] = BUILDING

    def build_static_zones(self):
        # Invert Y for Green/Red zones
        green_coords = [
            (0,21), (1,21), # Before 0,3; 1,3 -> 24-3=21
            (0,17), (1,17), # Before 0,7; 1,7 -> 24-7=17
            (8,3), (9,3),   # Before 8,21; 9,21 -> 24-21=3
            (10,22), (11,22), # Before 10,2; 11,2 -> 24-2=22
            (16,3), (17,3), # Before 16,21; 17,21 -> 24-21=3
            (22,18), (23,18), # Before 22,6; 23,6 -> 24-6=18
            (22,12), (23,12)  # Before 22,12; 23,12 -> 24-12=12
        ]
        for x, y in green_coords:
            if 0 <= x < 25 and 0 <= y < 25:
                self.city_layout[x][y] = GREEN_ZONE

        red_coords = [
            (2,20), (2,19), # Before 2,4; 2,5 -> 24-4=20, 24-5=19
            (2,16), (2,15), # Before 2,8; 2,9 -> 24-8=16, 24-9=15
            (7,2), (7,1),   # Before 7,22; 7,23 -> 24-22=2, 24-23=1
            (12,24), (12,23), # Before 12,0; 12,1 -> 24-0=24, 24-1=23
            (14,2), (14,1), # Before 14,22; 14,23 -> 24-22=2, 24-23=1
            (21,20), (21,19), # Before 21,4; 21,5 -> 24-4=20, 24-5=19
            (21,14), (21,13)  # Before 21,10; 21,11 -> 24-10=14, 24-11=13
        ]
        for x, y in red_coords:
            if 0 <= x < 25 and 0 <= y < 25:
                self.city_layout[x][y] = RED_ZONE

    def build_median_lines(self):
        # Invert Y for median lines
        # Vertical: x=10.5. y range [0, 9] -> [24-9, 24-0] = [15, 24]
        self.median_lines.append(((10.5, 15), (10.5, 24)))
        
        # Segment 2: y range [11, 24] -> [24-24, 24-11] = [0, 13]
        self.median_lines.append(((10.5, 0), (10.5, 13)))
        
        # Horizontal: y=9.5 -> y=24-9.5 = 14.5
        # Segment 1: x range [0, 9]
        self.median_lines.append(((0, 14.5), (9, 14.5)))
        
        # Segment 2: x range [11, 24]
        self.median_lines.append(((11, 14.5), (24, 14.5)))
