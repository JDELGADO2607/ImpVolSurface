import time
import nbformat
from nbclient import NotebookClient

notebook_path = "notebooks/NU_Heston_Autocontenido_Kaggle.ipynb"
print(f"Reading {notebook_path}...")
with open(notebook_path, "r", encoding="utf-8") as f:
    nb = nbformat.read(f, as_version=4)

print("Starting execution of notebook cells in-kernel...")
t0 = time.time()
client = NotebookClient(nb, timeout=600, kernel_name="python3")

try:
    client.execute()
    t1 = time.time()
    print(f"All cells executed successfully in {t1 - t0:.2f} seconds!")
    
    with open(notebook_path, "w", encoding="utf-8") as f:
        nbformat.write(nb, f)
    print("Executed notebook saved with full outputs.")

except Exception as e:
    print(f"Execution failed: {e}")
    # Still write what was executed so far
    with open(notebook_path, "w", encoding="utf-8") as f:
        nbformat.write(nb, f)
    raise e
