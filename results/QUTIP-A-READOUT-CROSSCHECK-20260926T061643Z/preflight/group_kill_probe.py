
import subprocess, sys, time
child = subprocess.Popen(["/bin/sleep", "60"])  # a small grandchild; the probe tests the kill, not exec size
print("GRANDCHILD", child.pid, flush=True)
time.sleep(60)
