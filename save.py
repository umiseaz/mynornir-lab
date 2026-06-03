import os
from nornir import InitNornir
from nornir_netmiko.tasks import netmiko_send_command
from nornir_utils.plugins.functions import print_result

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

nr = InitNornir(
    runner={"plugin": "threaded", "options": {"num_workers": 8}},
    inventory={
        "plugin": "SimpleInventory",
        "options": {
            "host_file": os.path.join(BASE_DIR, "inventory/hosts.yaml"),
            "group_file": os.path.join(BASE_DIR, "inventory/groups.yaml"),
            "defaults_file": os.path.join(BASE_DIR, "inventory/defaults.yaml"),
        }
    }
)

def save_config(task):
    task.run(
        task=netmiko_send_command,
        command_string="write memory",
    )
    print(f"[✓] {task.host.name} saved")

print("Saving configs on all routers...")
results = nr.run(task=save_config)