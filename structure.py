import os

# Set the directory you want to display, e.g., replace with your project directory
project_dir = r'C:\Projekte\LotusGamingDE'

# Function to recursively print directory structure


def print_directory_structure(root_dir, indent_level=0):
    for item in os.listdir(root_dir):
        item_path = os.path.join(root_dir, item)
        indent = ' ' * (indent_level * 4)
        if os.path.isdir(item_path):
            print(f"{indent}- {item}/")
            print_directory_structure(item_path, indent_level + 1)
        else:
            print(f"{indent}- {item}")


# Display the project structure
print("Projektstruktur:")
print_directory_structure(project_dir)
