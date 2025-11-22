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

# === 2. ESTRATEGIA "SUPER FAST" ===
class SuperAggressiveShape(LoadTestShape):
    """
    Sube 10 usuarios cada 2 segundos.
    """
    step_time = 2   # Tiempo del escalón (2 segundos)
    step_load = 10  # Usuarios a agregar (10 usuarios)
    spawn_rate = 10 # Velocidad de aparición (Instantánea)
    time_limit = 60 # Límite de 1 minuto (Suficiente para matarlo)

    def tick(self):
        run_time = self.get_run_time()
        if run_time > self.time_limit:
            return None
        
        # Cálculo del escalón actual
        current_step = run_time // self.step_time + 1
        target_users = int(current_step * self.step_load)
        
        return (target_users, self.spawn_rate)

# === 3. USUARIO DE PRUEBA ===
class OmniDoctor(HttpUser):
    host = f"http://{TARGET_IP}:5002"
    # Sin espera (0 segundos) para máxima presión, o muy baja (0.5s)
    wait_time = constant(0.5) 
    token = None

    def on_start(self):
        # Configuración para evitar cuellos de botella en el cliente
        self.client.keep_alive = False
        adapter = HTTPAdapter(max_retries=Retry(total=1, backoff_factor=0.1))
        self.client.mount("http://", adapter)

        try:
            # Timeout corto (2s) para fallar rápido si el servidor se cuelga
            res = requests.post(LOGIN_URL, json=CREDENTIALS, headers={"Connection": "close"}, timeout=2)
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
            "Connection": "close"
        }

    # --- TAREA DE ESTRÉS ---
    @task
    def stress_cycle(self):
        if not self.token: return

        try:
            # Golpeamos Cita y Vitales seguidos
            self.client.get(f"http://{TARGET_IP}:5001/api/appointments/{TEST_DATA['appointment_id']}", 
                           headers=self.get_headers(), name="Step: Citas")
            
            self.client.get(f"http://{TARGET_IP}:5006/api/vitals", 
                           params={"patient_id": TEST_DATA['patient_id'], "range_hours": 24},
                           headers=self.get_headers(), name="Step: Vitales")
        except:
            pass