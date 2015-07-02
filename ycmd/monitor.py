import time
import sys
import os


st_plugin_pid = int(sys.argv[1])
server_pid = int(sys.argv[2])

while True:
    time.sleep(5)

    try:
        os.kill(st_plugin_pid, 0)
    except OSError:
        os.kill(server_pid, 1)
        sys.exit()
