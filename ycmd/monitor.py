import time
import sys
import os


st_plugin_pid = int(sys.argv[1])
server_pid = int(sys.argv[2])


def is_pid_alive(pid):
    try:
        os.kill(pid, 0)
        return True
    except Exception:
        return False


while True:
    time.sleep(5)

    if not is_pid_alive(st_plugin_pid):
        os.kill(server_pid, 1)
        sys.exit()
    if not is_pid_alive(server_pid):
        return
