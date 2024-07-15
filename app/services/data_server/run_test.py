import subprocess
import time
import sys

def run_tests():
    print("Running tests...")
    result = subprocess.run(["pytest", "-v"], capture_output=True, text=True)
    print(result.stdout)
    if result.returncode != 0:
        print("Tests failed. Exiting.")
        sys.exit(1)
    print("All tests passed.")

def run_server():
    print("Starting Flask server...")
    server_process = subprocess.Popen(["python", "data_server.py"])
    time.sleep(2)  # Give the server a moment to start
    print("Flask server is running.")
    return server_process

if __name__ == "__main__":
    run_tests()
    server_process = run_server()

    try:
        server_process.wait()
    except KeyboardInterrupt:
        print("Stopping server...")
        server_process.terminate()
        server_process.wait()
        print("Server stopped.")