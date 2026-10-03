from locust import HttpUser, task, between
import random

class CTFUser(HttpUser):
    wait_time = between(1, 3)

    def on_start(self):
        # Create a user session
        self.username = f"locust_user_{random.randint(1000, 999999)}"
        self.password = "password123"
        
        # We need CSRF tokens. This requires parsing the login page
        # to extract the csrf_token from window.csrfToken or form.
        response = self.client.get("/login")
        
        # Simple extraction if token is in html
        self.csrf_token = None
        if "csrf_token" in response.text:
            import re
            match = re.search(r'name="csrf_token" value="(.*?)"', response.text)
            if match:
                self.csrf_token = match.group(1)

        # Login
        if self.csrf_token:
            self.client.post("/login", data={
                "username": self.username,
                "password": self.password,
                "csrf_token": self.csrf_token
            })

    @task(3)
    def visit_dashboard(self):
        self.client.get("/dashboard")

    @task(2)
    def visit_labs(self):
        self.client.get("/labs")

    @task(1)
    def submit_flag(self):
        if not self.csrf_token:
            return
            
        self.client.post("/api/flag", json={
            "lab_id": "lab1",
            "flag": "INVALID_FLAG"
        }, headers={"X-CSRFToken": self.csrf_token})
        
    @task(1)
    def submit_quiz(self):
        if not self.csrf_token:
            return
            
        self.client.post("/api/quiz", json={
            "lab_id": "lab1",
            "mission_id": "lab1_m1",
            "answer": "wrong"
        }, headers={"X-CSRFToken": self.csrf_token})
