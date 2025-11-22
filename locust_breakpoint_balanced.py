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

# === 2. ESTRATEGIA EQUILIBRADA (Recomendada) ===
class BalancedStepShape(LoadTestShape):
    """
    Sube 5 usuarios cada 10 segundos.
    Rápido para ver resultados, lento para ver el detalle.
    """
    step_time = 10  # Cada escalón dura 10 segundos
    step_load = 5   # Agregamos 5 usuarios por escalón
    spawn_rate = 5  # Entran los 5 de golpe al inicio del escalón
    time_limit = 120 # 2 minutos máximo (suficiente para romperlo)

    def tick(self):
        run_time = self.get_run_time()
        if run_time > self.time_limit:
            return None
        
        current_step = run_time // self.step_time + 1
        target_users = int(current_step * self.step_load)
        
        return (target_users, self.spawn_rate)

# === 3. USUARIO ===
class OmniDoctor(HttpUser):
    host = f"http://{TARGET_IP}:5002"
    # Espera de 1 segundo: Carga constante pero no "spam masivo"
    wait_time = constant(1) 
    token = None

    def on_start(self):
        self.client.keep_alive = False
        adapter = HTTPAdapter(max_retries=Retry(total=2, backoff_factor=0.1))
        self.client.mount("http://", adapter)

        try:
            res = requests.post(LOGIN_URL, json=CREDENTIALS, headers={"Connection": "close"}, timeout=5)
            if res.status_code == 200:
                self.token = res.json().get("access_token")
            else:
                print(f"⚠️ Login Falló: {res.status_code}")
        except:
            pass 

    def get_headers(self):
        return {
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/json",
            "Connection": "close"
        }

    @task
    def stress_cycle(self):
        if not self.token: return

        try:
            # Cita
            self.client.get(f"http://{TARGET_IP}:5001/api/appointments/{TEST_DATA['appointment_id']}", 
                           headers=self.get_headers(), name="Step: Citas")
            # Vitales
            self.client.get(f"http://{TARGET_IP}:5006/api/vitals", 
                           params={"patient_id": TEST_DATA['patient_id'], "range_hours": 24},
                           headers=self.get_headers(), name="Step: Vitales")
        except:
            pass