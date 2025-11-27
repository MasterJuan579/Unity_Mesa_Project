from mesa import Model, Agent
from mesa.space import MultiGrid

class SyncAgent(Agent):
    def __init__(self, unique_id, model):
        super().__init__(model) 
        self.unique_id = unique_id

    def step(self):
        pass

class SyncModel(Model):
    def __init__(self, width=74, height=74):
        super().__init__()
        self.grid = MultiGrid(width, height, torus=False)
        self.agents_dict = {}

        # --- LÍNEA DE PRUEBA ---
        # Esto crea un agente (ID 999) en la coordenada (0,0) de Mesa
        self.add_agent(999, 0, 0) 
        # -----------------------

    def add_agent(self, agent_id: int, x: int, y: int):
        if agent_id in self.agents_dict:
            return
        
        a = SyncAgent(agent_id, self)
        self.agents_dict[agent_id] = a
        self.grid.place_agent(a, (x, y))

    # ... (El resto del código sigue igual: move_agent, remove_agent, etc.)
    def move_agent(self, agent_id: int, x: int, y: int):
        a = self.agents_dict.get(agent_id)
        if a:
            if not self.grid.out_of_bounds((x, y)):
                try:
                    self.grid.move_agent(a, (x, y))
                except Exception:
                    self.grid.place_agent(a, (x, y))

    def remove_agent(self, agent_id: int):
        a = self.agents_dict.pop(agent_id, None)
        if a:
            try:
                self.grid.remove_agent(a)
            except Exception:
                pass
            a.remove() 

    def serialize_grid(self):
        data = []
        for cell_content, (x, y) in self.grid.coord_iter():
            for agent in cell_content:
                data.append({
                    "id": agent.unique_id, 
                    "x": x, 
                    "y": y
                })
        return data

    def step(self):
        self.agents.shuffle().do("step")