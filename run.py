import subprocess
import os
import platform
import shlex



def run(command):
    subprocess.run(shlex.split(command))

def run_async(command, file):
    df = subprocess.Popen(shlex.split(command), stderr=file)

if __name__ == '__main__':
    iswin = platform.system() == 'Windows'
    f = open("log.txt", "a"):
    run("git pull")
    
    run("python3 -m venv venv")
    
    run("python -m venv venv")

    slash = '\\' if iswin else "/"
    
    def get_script_path(name):
        if platform.system() == 'Windows':
            return f".\\venv\\Scripts\\{name}.bat"
        else:
            return f"./venv/bin/{name}"
    
    run(f"{get_script_path('pip')} install -r requirements.txt")
    
    run_async(f"{get_script_path('streamlit')} run xirr{slash}gui.py", f)

    run_async(f"{get_script_path('streamlit')} run aml{slash}gui.py", f)

    a = 0

    while True:
        time.sleep(100)

    

