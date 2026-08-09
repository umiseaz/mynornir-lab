import os
from dotenv import load_dotenv
from nornir import InitNornir
from nornir.core.plugins.inventory import TransformFunctionRegister
from nornir_netmiko.tasks import netmiko_send_command
from nornir_utils.plugins.functions import print_result
from nornir_transform import inject_credentials

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

load_dotenv(os.path.join(BASE_DIR, ".env"))
TransformFunctionRegister.register("inject_credentials", inject_credentials)

# config.yaml paths are CWD-relative
os.chdir(BASE_DIR)
nr = InitNornir(config_file="config.yaml")

def save_config(task):
    task.run(
        task=netmiko_send_command,
        command_string="write memory",
    )
    print(f"[✓] {task.host.name} saved")

print("Saving configs on all routers...")
results = nr.run(task=save_config)