import os
import ast

def add_module_docstring(filepath):
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
    except UnicodeDecodeError:
        return

    # Check if file is empty
    if not content.strip():
        return

    try:
        tree = ast.parse(content)
    except SyntaxError:
        return

    # Check if there is already a module-level docstring
    if ast.get_docstring(tree) is not None:
        return

    filename = os.path.basename(filepath)
    app_name = os.path.basename(os.path.dirname(filepath)).capitalize()

    docstring = f'"""\n{filename} for the {app_name} app.\n\nThis module contains the {filename.replace(".py", "")} logic for the {app_name} functionality.\n"""\n'

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(docstring + content)
    print(f"Added docstring to {filepath}")

def process_apps(base_dir):
    target_files = {'models.py', 'views.py', 'urls.py', 'services.py', 'selectors.py', 'admin.py'}
    
    for root, dirs, files in os.walk(base_dir):
        for file in files:
            if file in target_files:
                filepath = os.path.join(root, file)
                add_module_docstring(filepath)

if __name__ == "__main__":
    apps_dir = os.path.join(os.path.dirname(__file__), 'apps')
    process_apps(apps_dir)
