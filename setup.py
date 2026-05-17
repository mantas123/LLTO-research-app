import os
import sys
import subprocess
import shutil

def run_cmd(args):
    print(f"\n[INFO] Vykdoma: {' '.join(args)}")
    try:
        subprocess.check_call(args)
        return True
    except subprocess.CalledProcessError as e:
        print(f"[KLAIDA] Komanda nepavyko su klaidos kodu {e.returncode}")
        return False

def check_nvidia_gpu():
    # Greitas patikrinimas ar yra NVIDIA GPU tvarkyklė sistemoje
    return shutil.which("nvidia-smi") is not None

def main():
    print("=========================================================")
    print("      LLTO Comprehensive App - Aplinkos Paruošimas       ")
    print("=========================================================\n")
    
    # 1. Atnaujiname pip ir setuptools virtualioje aplinkoje
    print("[1/5] Atnaujinamas pip ir pagrindiniai įrankiai...")
    python_exe = sys.executable
    run_cmd([python_exe, "-m", "pip", "install", "--upgrade", "pip", "setuptools", "wheel"])

    # 2. Klausiame apie NVIDIA GPU pagreitinimą
    print("\n[2/5] PyTorch (AI analizės variklio) diegimas...")
    gpu_detected = check_nvidia_gpu()
    if gpu_detected:
        print("[APTIKTA] Jūsų sistemoje aptikta NVIDIA vaizdo plokštė!")
        ans = input("Ar norite įdiegti NVIDIA GPU (CUDA) palaikymą greitesnei SEM analizei? (t/n) [t]: ").strip().lower()
        use_gpu = ans != 'n'
    else:
        print("[PASTABA] NVIDIA vaizdo plokštė nerasta arba neaktyvuota.")
        ans = input("Ar norite bandyti diegti su NVIDIA GPU (CUDA) palaikymu? (t/n) [n]: ").strip().lower()
        use_gpu = ans == 't'

    if use_gpu:
        print("\n--> Diegiamas PyTorch su CUDA 12.1 palaikymu...")
        # Naudojame oficialią PyTorch CUDA whl saugyklą
        success = run_cmd([python_exe, "-m", "pip", "install", "torch", "torchvision", "--index-url", "https://download.pytorch.org/whl/cu121"])
    else:
        print("\n--> Diegiamas PyTorch (tik CPU režimas)...")
        success = run_cmd([python_exe, "-m", "pip", "install", "torch", "torchvision"])

    if not success:
        print("[ĮSPĖJIMAS] Nepavyko įdiegti specifinės PyTorch versijos. Bandoma standartinė versija...")
        run_cmd([python_exe, "-m", "pip", "install", "torch", "torchvision"])

    # 3. Diegiame kitus reikalavimus iš requirements.txt
    print("\n[3/5] Diegiamos pagrindinės bibliotekos (PyEIS, PyVista, PyQt6 ir kt.)...")
    req_path = os.path.join(os.path.dirname(__file__), "requirements.txt")
    if os.path.exists(req_path):
        run_cmd([python_exe, "-m", "pip", "install", "-r", req_path])
    else:
        # Jei requirements.txt netyčia dingo, įdiegiame rankiniu būdu
        libs = ["numpy", "pandas", "matplotlib", "scipy", "lmfit", "pyvista", "pyvistaqt", "PyQt6", "opencv-python", "scikit-image", "openpyxl", "huggingface-hub"]
        run_cmd([python_exe, "-m", "pip", "install"] + libs)

    # 4. Diegiame SAM 2 (Segment Anything)
    print("\n[4/5] Diegiamas SAM 2 (Segment Anything 2.1)...")
    # Naudojame tiesioginį ZIP archyvą, kad veiktų net jei sistemoje nėra įdiegtas GIT!
    sam2_url = "https://github.com/facebookresearch/sam2/archive/refs/heads/main.zip"
    print("--> Siunčiamas ir diegiamas SAM 2 paketas tiesiai iš GitHub ZIP...")
    success = run_cmd([python_exe, "-m", "pip", "install", sam2_url])
    
    if not success:
        print("\n[Bandymai] Nepavyko tiesioginis ZIP diegimas. Bandoma įdiegti naudojant git (jei git yra įdiegtas)...")
        run_cmd([python_exe, "-m", "pip", "install", "git+https://github.com/facebookresearch/sam2.git"])

    # 5. Patvirtinimas
    print("\n[5/5] Tikrinama aplinka...")
    try:
        import torch
        import pyvista as pv
        import sam2
        print("\n=========================================================")
        print("          SĖKMĖ: Aplinka pilnai paruošta darbui!         ")
        print("=========================================================")
        print(f"PyTorch versija: {torch.__version__}")
        print(f"Ar CUDA aktyvi (GPU pagreitinimas): {torch.cuda.is_available()}")
        if torch.cuda.is_available():
            print(f"Naudojama plokštė: {torch.cuda.get_device_name(0)}")
        print("---------------------------------------------------------")
        print("Norėdami paleisti programą, naudokite sukurtą 'run.bat' failą.")
        print("=========================================================\n")
    except Exception as e:
        print(f"\n[DĖMESIO] Kai kurios bibliotekos nebuvo įdiegtos teisingai: {e}")
        print("Prašome peržiūrėti viršuje esančius pranešimus dėl klaidų.")

if __name__ == "__main__":
    main()
