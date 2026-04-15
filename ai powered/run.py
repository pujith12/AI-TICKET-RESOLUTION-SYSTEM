import subprocess
import os

def run_app():
    # Set PYTHONPATH to include the 'app' directory
    env = os.environ.copy()
    project_root = os.path.dirname(os.path.abspath(__file__))
    app_dir = os.path.join(project_root, "app")
    
    if "PYTHONPATH" in env:
        env["PYTHONPATH"] = f"{app_dir}{os.pathsep}{env['PYTHONPATH']}"
    else:
        env["PYTHONPATH"] = app_dir

    print(f"Starting Streamlit app from {app_dir}...")
    try:
        subprocess.run(["streamlit", "run", "app/app.py"], env=env, check=True)
    except KeyboardInterrupt:
        print("\nApp stopped.")
    except Exception as e:
        print(f"Error starting app: {e}")

if __name__ == "__main__":
    run_app()
