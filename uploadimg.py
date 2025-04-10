import os
import json
import requests
from urllib.parse import quote

# Ваш OAuth-токен для Яндекс.Диска (замените на ваш действительный токен)
ACCESS_TOKEN = "y0__xCsl_CJCBi78DYg99Gi5BLcb5vcszMOhMWW6YsWUprfxo-Huw"

def create_folder(disk_folder_path):
    """
    Создает папку на Яндекс.Диске по указанному пути.
    Если папка уже существует (код 409), считается, что всё в порядке.
    """
    headers = {"Authorization": f"OAuth {ACCESS_TOKEN}"}
    encoded_path = quote(disk_folder_path, safe="/")
    url = "https://cloud-api.yandex.net/v1/disk/resources"
    params = {"path": encoded_path}
    response = requests.put(url, params=params, headers=headers)
    if response.status_code in (201, 409):
        return True
    else:
        print(f"Ошибка создания папки {disk_folder_path}: {response.status_code} {response.text}")
        return False

def ensure_remote_folder_exists(disk_folder_path):
    """
    Создает всю вложенную структуру папок на Яндекс.Диске для указанного пути.
    Например, для "/Folder1/Folder2" сначала создаст "/Folder1", затем "/Folder1/Folder2".
    """
    parts = disk_folder_path.strip("/").split("/")
    current_path = ""
    for part in parts:
        current_path += "/" + part
        if not create_folder(current_path):
            print(f"Не удалось создать папку: {current_path}")
            return False
    return True

def upload_file(file_path, disk_path):
    """
    Загружает файл с локального компьютера на Яндекс.Диск,
    публикует его и возвращает публичную ссылку.

    :param file_path: Локальный путь к файлу, например, r"D:\Userprofile\Downlds\foto\scan_img123.jpg"
    :param disk_path: Полный путь на Яндекс.Диске, например, "/Опоры трубопроводов/Категория/Подкатегория/scan_img123.jpg"
    :return: Публичная ссылка или None в случае ошибки.
    """
    headers = {"Authorization": f"OAuth {ACCESS_TOKEN}"}
    encoded_disk_path = quote(disk_path, safe="/")
    
    # 1. Получаем URL для загрузки файла
    upload_url = "https://cloud-api.yandex.net/v1/disk/resources/upload"
    params = {"path": encoded_disk_path, "overwrite": "true"}
    response = requests.get(upload_url, params=params, headers=headers)
    if response.status_code != 200:
        print(f"Ошибка получения ссылки для загрузки ({response.status_code}): {response.text}")
        return None
    data = response.json()
    href = data.get("href")
    if not href:
        print("Не удалось получить URL для загрузки.")
        return None

    # 2. Загружаем файл через PUT
    with open(file_path, "rb") as f:
        upload_response = requests.put(href, data=f)
    if upload_response.status_code not in (200, 201):
        print(f"Ошибка загрузки файла ({upload_response.status_code}): {upload_response.text}")
        return None

    # 3. Публикуем файл (метод publish) для получения публичной ссылки
    publish_url = "https://cloud-api.yandex.net/v1/disk/resources/publish"
    params = {"path": encoded_disk_path}
    pub_response = requests.put(publish_url, headers=headers, params=params)
    if pub_response.status_code != 200:
        print(f"Ошибка публикации файла ({pub_response.status_code}): {pub_response.text}")
        return None

    # 4. Получаем информацию о файле, включая поле "public_url"
    info_url = "https://cloud-api.yandex.net/v1/disk/resources"
    params = {"path": encoded_disk_path}
    info_response = requests.get(info_url, headers=headers, params=params)
    if info_response.status_code != 200:
        print(f"Ошибка получения информации о файле ({info_response.status_code}): {info_response.text}")
        return None
    info_data = info_response.json()
    public_url = info_data.get("public_url")
    return public_url
def upload_all_files_from_directory(root_directory, remote_base, output_json_path, allowed_exts=None):
    """
    Рекурсивно обходит все файлы в заданной локальной директории (и вложенные папки),
    выбирает файлы с указанными расширениями и в которых в имени присутствует подстрока "scan_img"
    (без учета регистра), создает соответствующую структуру папок на Яндекс.Диске,
    загружает файлы и сохраняет результаты в JSON-файл.
    
    В результирующем JSON-словаре ключ – это имя файла (например, "scan_img123.jpg"),
    а значение – публичная ссылка на файл.
    
    :param root_directory: Корневая локальная директория, например, r"D:\Userprofile\Downlds\foto"
    :param remote_base: Базовый путь на Яндекс.Диске, куда будут загружаться файлы, например, "/Опоры трубопроводов"
    :param output_json_path: Путь к JSON-файлу для сохранения результата, например, "uploaded_files.json"
    :param allowed_exts: Список разрешённых расширений файлов (например, [".jpg", ".jpeg", ".png"]). Если None — используются стандартные.
    """
    if allowed_exts is None:
        allowed_exts = [".jpg", ".jpeg", ".png", ".gif", ".bmp", ".tiff"]
    
    results = {}  # Словарь: имя файла -> публичная ссылка

    # Рекурсивно обходим папки в root_directory
    for dirpath, dirnames, filenames in os.walk(root_directory):
        for filename in filenames:
            # Проверяем, содержит ли имя подстроку "scan_img" (без учета регистра)
            if "scan_img" not in filename.lower():
                continue

            ext = os.path.splitext(filename)[1].lower()
            if ext not in allowed_exts:
                continue

            local_file_path = os.path.join(dirpath, filename)
            # Вычисляем относительный путь файла от корневой директории и заменяем обратные слеши на слеши
            rel_path = os.path.relpath(local_file_path, root_directory).replace("\\", "/")
            # Формируем удалённый путь: базовый путь на Яндекс.Диске + относительный путь (с сохранением структуры)
            remote_disk_path = f"{remote_base}/{rel_path}"

            # Создаем удалённую папку, если нужно
            remote_folder = os.path.dirname(remote_disk_path)
            print(f"Создаем (или проверяем) папку на Яндекс.Диске: {remote_folder}")
            if not ensure_remote_folder_exists(remote_folder):
                print(f"Не удалось создать папку: {remote_folder}")
                continue

            print(f"Загружаем файл: {local_file_path}")
            public_url = upload_file(local_file_path, remote_disk_path)
            if public_url:
                # Сохраняем только имя файла как ключ
                results[filename] = public_url
                print(f"Успешно загружено: {filename} -> {public_url}")
            else:
                print(f"Ошибка загрузки файла: {filename}")

    # Сохраняем результат в JSON-файл
    with open(output_json_path, "w", encoding="utf-8") as outfile:
        json.dump(results, outfile, ensure_ascii=False, indent=4)
    print(f"Данные успешно сохранены в: {output_json_path}")

if name == "main":
    # Задайте корневую локальную директорию (используйте raw-строку для Windows)
    root_dir = r"D:\Userprofile\Downlds\foto"
    # Укажите базовый путь на Яндекс.Диске, куда будут загружаться файлы (например, "/Опоры трубопроводов")
    remote_base_path = "/Опоры трубопроводов"
    # Имя JSON-файла, в который будут сохранены результаты
    output_json_file = "uploaded_files.json"
    
    upload_all_files_from_directory(root_dir, remote_base_path, output_json_file)