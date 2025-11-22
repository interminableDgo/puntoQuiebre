import requests
from locust import HttpUser, task, constant, LoadTestShape
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# === 1. CONFIGURACIÓN ===
TARGET_IP = "104.248.215.179"
LOGIN_URL = f"http://{TARGET_IP}:5002/api/login"

CREDENTIALS = {
    "login": "carlos.gómez@heartguard.com",
    "password": "123"
}

TEST_DATA = {
    "patient_id": "7199cd3d-47ce-409f-89d5-9d01ca82fd08",
    "appointment_id": "db61d072-67ef-4cad-b396-6f86d13187df"
}

# === 2. ESTRATEGIA NUCLEAR (Hasta 1000 Usuarios) ===
class UltimateStepShape(LoadTestShape):
    step_time = 30  # 30 segundos por nivel
    step_load = 100 # +100 usuarios por nivel
    spawn_rate = 10 # Entran 10 por segundo
    time_limit = 600 # 10 minutos

    def tick(self):
        run_time = self.get_run_time()
        if run_time > self.time_limit:
            return None
        
        current_step = run_time // self.step_time + 1
        target_users = int(current_step * self.step_load)
        
        # Tope de seguridad en 1000 usuarios
        if target_users > 1000:
            target_users = 1000
            
        return (target_users, self.spawn_rate)

# === 3. USUARIO FRENÉTICO ===
class OmniDoctor(HttpUser):
    host = f"http://{TARGET_IP}:5002"
    
    # AQUI ESTA EL TRUCO: 0.1 segundos de espera.
    # Esto genera 10 veces más tráfico por usuario que antes.
    wait_time = constant(0.1) 
    
    token = None

    def on_start(self):
        # Optimizamos la conexión para alto rendimiento
        self.client.keep_alive = True 
        adapter = HTTPAdapter(pool_connections=100, pool_maxsize=100, max_retries=Retry(total=1, backoff_factor=0.1))
        self.client.mount("http://", adapter)

        try:
            # Login rápido
            res = requests.post(LOGIN_URL, json=CREDENTIALS, headers={"Connection": "keep-alive"}, timeout=5)
            if res.status_code == 200:
                self.token = res.json().get("access_token")
            else:
                print(f"🔥 Login Falló: {res.status_code}")
        except:
            pass 

    def get_headers(self):
        return {
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/json",
            # En prueba de estrés real, a veces mantener la conexión viva satura más rápido los sockets
            "Connection": "keep-alive" 
        }

    @task
    def stress_cycle(self):
        if not self.token: return

        try:
            # Solo pedimos Vitales (es la consulta más pesada a BD)
            self.client.get(f"http://{TARGET_IP}:5006/api/vitals", 
                           params={"patient_id": TEST_DATA['patient_id'], "range_hours": 24},
                           headers=self.get_headers(), name="STRESS: Vitales")
        except:
            pass