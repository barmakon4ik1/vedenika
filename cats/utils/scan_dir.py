import os

# Служебные директории, которые нужно игнорировать
SKIP_DIRS = {
    ".venv", "venv", "__pycache__", ".idea", ".git",
    ".mypy_cache", ".pytest_cache", ".vs", ".vscode"
}

def scan_folder(root_path):
    folder_tree = []
    all_files = []
    all_dirs = []

    for current_path, dirs, files in os.walk(root_path):
        # Отбрасываем служебные директории
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]

        # Запоминаем директорию
        all_dirs.append(current_path)

        # Формируем уровень вложенности
        depth = current_path.replace(root_path, "").count(os.sep)
        indent = "    " * depth
        folder_tree.append(f"{indent}[DIR]  {os.path.basename(current_path) or current_path}")

        # Записываем файлы
        for f in files:
            all_files.append(os.path.join(current_path, f))
            folder_tree.append(f"{indent}    └── {f}")

    return folder_tree, all_files, all_dirs


if __name__ == "__main__":
    path = input("Укажи путь к папке: ").strip()

    if not os.path.exists(path):
        print("Путь не существует!")
        exit()

    tree, files, dirs = scan_folder(path)

    print("\n====== ДЕРЕВО ПАПКИ (без служебных директорий) ======\n")
    for line in tree:
        print(line)

    print("\nГотово!")
