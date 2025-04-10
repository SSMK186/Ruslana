LOXPIDRimport os
import json
import requests
from urllib.parse import quote

# Ваш OAuth-токен для Яндекс.Диска
ACCESS_TOKEN = "y0__xCsl_CJCBi78DYg99Gi5BLcb5vcszMOhMWW6YsWUprfxo-Huw"

def create_folder(disk_folder_path):
    """
    Создает папку на Яндекс.Диске по указанному пути.
    Если папка уже существует, возвращает True.
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
    Создает всю вложенную структуру папок на Яндекс.Диске по указанному пути.
    Например, для "/Folder1/Folder2" создаст сначала "/Folder1", затем "/Folder1/Folder2".
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
    
    :param file_path: Локальный путь к файлу, например, "D:\\Userprofile\\Downlds\\foto\\IMG_3474.JPG"
    :param disk_path: Путь на Яндекс.Диске, куда сохранить файл, например, "/Опоры трубопроводов/IMG_3474.JPG"
    :return: Публичная ссылка на файл или None в случае ошибки.
    """
    headers = {"Authorization": f"OAuth {ACCESS_TOKEN}"}
    encoded_disk_path = quote(disk_path, safe="/")
    
    # Запрашиваем URL для загрузки
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
    
    # Загружаем файл
    with open(file_path, "rb") as f:
        upload_response = requests.put(href, data=f)
    if upload_response.status_code not in (200, 201):
        print(f"Ошибка загрузки файла ({upload_response.status_code}): {upload_response.text}")
        return None
    
    # Публикуем файл для получения публичной ссылки
    publish_url = "https://cloud-api.yandex.net/v1/disk/resources/publish"
    params = {"path": encoded_disk_path}
    pub_response = requests.put(publish_url, headers=headers, params=params)
    if pub_response.status_code != 200:
        print(f"Ошибка публикации файла ({pub_response.status_code}): {pub_response.text}")
        return None
    
    # Получаем информацию о файле (public_url)
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
    Рекурсивно обходит все файлы в корневой директории (и вложенные папки),
    выбирает файлы с разрешёнными расширениями (например, .jpg, .png),
    создает соответствующую структуру папок на Яндекс.Диске,
    загружает файлы и сохраняет результаты в JSON-файл.

    В результирующем JSON-словаре ключ – это имя файла, а значение – публичная ссылка.

    Перед загрузкой для каждого файла проверяется, если файл уже загружен (по ключу в JSON).

    :param root_directory: Корневая локальная директория, например, r"D:\\Userprofile\\Downlds\\foto"
    :param remote_base: Базовый путь на Яндекс.Диске, например, "/Опоры трубопроводов"
    :param output_json_path: Путь к JSON-файлу для сохранения результатов, например, "uploaded_files.json"
    :param allowed_exts: Список разрешённых расширений файлов. Если None, используются стандартные.
    """
    if allowed_exts is None:
        allowed_exts = [".jpg", ".jpeg", ".png", ".gif", ".bmp", ".tiff"]
    
    # Если JSON-файл с результатами уже существует, загрузим его,
    # чтобы не загружать повторно уже обработанные файлы.
    if os.path.exists(output_json_path):
        with open(output_json_path, "r", encoding="utf-8") as infile:
            results = json.load(infile)
    else:
        results = {}

    # Рекурсивно обходим директорию
    for dirpath, dirnames, filenames in os.walk(root_directory):
        for filename in filenames:
            ext = os.path.splitext(filename)[1].lower()
            if ext not in allowed_exts:
                continue
            
            # Если файл с таким именем уже загружен, пропустим его
            if filename in results:
                print(f"Файл уже загружен: {filename}")
                continue

            local_file_path = os.path.join(dirpath, filename)
            # Вычисляем относительный путь от root_directory
            rel_path = os.path.relpath(local_file_path, root_directory).replace("\\", "/")
            # Формируем удалённый путь: базовый путь + относительный путь
            remote_disk_path = f"{remote_base}/{rel_path}"
            
            # Создаем удалённую папку (если она еще не создана)
            remote_folder = os.path.dirname(remote_disk_path)
            print(f"Создаем папку на Яндекс.Диске (если необходимо): {remote_folder}")
            if not ensure_remote_folder_exists(remote_folder):
                print(f"Не удалось создать папку: {remote_folder}")
                continue
            
            print(f"Загружаем файл: {local_file_path}")
            public_url = upload_file(local_file_path, remote_disk_path)
            if public_url:
                results[filename] = public_url
                print(f"Успешно загружено: {filename} -> {public_url}")
            else:
                print(f"Ошибка загрузки файла: {filename}")
    
    # Сохраняем результаты в JSON-файл
    with open(output_json_path, "w", encoding="utf-8") as outfile:
        json.dump(results, outfile, ensure_ascii=False, indent=4)
    print(f"Данные успешно сохранены в: {output_json_path}")

if __name__ == "__main__":
    # Корневая локальная директория (используйте raw-строку)
    root_dir = r"D:\Userprofile\Downlds\foto"
    # Базовый путь на Яндекс.Диске, куда будут загружаться файлы
    remote_base_path = "/Опоры трубопроводов"
    # Выходной JSON-файл для сохранения результатов
    output_json_file = "uploaded_files.json"
    
    upload_all_files_from_directory(root_dir, remote_base_path, output_json_file)
