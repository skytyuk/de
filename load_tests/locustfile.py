import random

from locust import HttpUser, between, task


class SiteUser(HttpUser):
    wait_time = between(1, 2)

    @task
    def random_scenario(self):
        steps = [self.get_home] + [self.create_role] * 4
        random.shuffle(steps)
        for step in steps:
            step()

    def get_home(self):
        self.client.get("/")

    def create_role(self):
        self.client.post("/load-test/roles/")
