import subprocess
import os
import platform
import shlex




if __name__ == '__main__':
    iswin = platform.system() == 'Windows'
    f = open("log.txt", "a")
    def run(command):
        subprocess.run(shlex.split(command), stdout=subprocess.DEVNULL)

    def run_async(command):
        df = subprocess.Popen(shlex.split(command), stderr=f, stdout=subprocess.DEVNULL)
    print("Updating codebase...")
    run("git pull")
    print("Pulling dependencies...")
    
    run("python3 -m venv venv")
    
    run("python -m venv venv")

    slash = '\\' if iswin else "/"
    
    def get_script_path(name):
        if platform.system() == 'Windows':
            return f".\\venv\\Scripts\\{name}.bat"
        else:
            return f"./venv/bin/{name}"
    
    run(f"{get_script_path('pip')} install -r requirements.txt")

    print("Running GUIs...")
    
    run_async(f"{get_script_path('streamlit')} run xirr{slash}gui.py")

    run_async(f"{get_script_path('streamlit')} run aml{slash}gui.py")

    print("Finished!")

