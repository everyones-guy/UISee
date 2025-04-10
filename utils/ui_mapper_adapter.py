import os
import paramiko
from dotenv import load_dotenv
from services.mqtt_service import MQTTService

# Load environment variables from .env file
load_dotenv()

class UIMQTTAdapter:
    def __init__(self, test_creds=None):
        self.client = MQTTService()
        self.client.connect()

        # Pull fallback SSH info from environment
        self.ssh_host = test_creds.get("host") if test_creds else os.getenv("SSH_HOST")
        self.ssh_user = test_creds.get("user") if test_creds else os.getenv("SSH_USER")
        self.ssh_pass = os.getenv("SSH_PASS")
        
    def send_command_and_wait(self, path, value):
        command = f"{path}={value}"
        self.client.publish("exec", command)
        return {"status": "sent", "output": f"Published to exec: {command}"}

    def publish_exec(self, widget_path, value):
        """
        Sends an exec-style MQTT command without waiting for a response.
        Falls back to SSH if MQTT is not connected.
        """
        if self.client.connected:
            payload = {"command": f"{widget_path}={value}"}
            self.client.publish(self.client.topic_exec, payload)
        else:
            return self.send_via_ssh(f"{widget_path}={value}")

    def send_via_ssh(self, command):
        """
        Fallback method to send command over SSH if MQTT is not available.
        """
        if not all([self.ssh_host, self.ssh_user, self.ssh_pass]):
            return {"success": False, "error": "SSH credentials not fully set in environment variables."}

        try:
            ssh = paramiko.SSHClient()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            ssh.connect(self.ssh_host, username=self.ssh_user, password=self.ssh_pass)

            stdin, stdout, stderr = ssh.exec_command(f"ec {command}")
            out = stdout.read().decode().strip()
            err = stderr.read().decode().strip()

            ssh.close()

            if err:
                return {"success": False, "error": err}
            return {"success": True, "response": out}
        except Exception as e:
            return {"success": False, "error": str(e)}

