import nbformat

with open("notebooks/NU_Heston_Autocontenido_Kaggle.ipynb", "r", encoding="utf-8") as f:
    nb = nbformat.read(f, as_version=4)

code_cells = [c for c in nb.cells if c.cell_type == "code"]
print(f"Total cells: {len(nb.cells)} ({sum(c.cell_type == 'markdown' for c in nb.cells)} md, {len(code_cells)} code)")

has_error = False
for i, c in enumerate(code_cells):
    errs = [o for o in c.get("outputs", []) if o.get("output_type") == "error"]
    if errs:
        has_error = True
        print(f"ERROR in code cell {i}: {errs[0].get('ename')}: {errs[0].get('evalue')}")
    else:
        stream_txt = ""
        for o in c.get("outputs", []):
            if o.get("output_type") == "stream":
                stream_txt += o.get("text", "")
        first_line = stream_txt.strip().split("\n")[0] if stream_txt.strip() else "(display/plots)"
        print(f"Cell {i:02d}: OK ({len(c.get('outputs', []))} outputs) -> {first_line[:80]}")

if has_error:
    print("\nFAIL: Errors found in notebook execution.")
    exit(1)
else:
    print("\nSUCCESS: All cells executed with zero errors!")

print("\n=== Sample Outputs from Key Cells ===")
# Inspect all code cells outputs text
for i, c in enumerate(code_cells):
    stream_txt = "".join(o.get("text", "") for o in c.get("outputs", []) if o.get("output_type") == "stream")
    if stream_txt:
        print(f"\n--- Output of Code Cell {i} ---")
        print(stream_txt.strip())
