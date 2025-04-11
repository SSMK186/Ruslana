import os
import json
import time
import requests
import logging
import re
from urllib.parse import quote
from unidecode import unidecode  # импортируем для транслитерации

# Настройка логирования: время, уровень и сообщение
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Ваш OAuth-токен для Яндекс.Диска (замените на действительный)
ACCESS_TOKEN = "y0__xCsl_CJCBi78DYg99Gi5BLcb5vcszMOhMWW6YsWUprfxo-Huw"

def normalize_folder_name(name):
    """
    Преобразует имя папки (или файла) из кириллицы в латиницу, заменяя все символы,
    отличные от букв и цифр, на подчёркивание. Например:
      "Опоры трубопроводов" -> "opory_truboprovodov"
    """
    # Транслитерируем кириллицу в латинские символы
    name = unidecode(name)
    # Заменяем любые последовательности символов, не являющихся буквами или цифрами, на один нижний подчёркивание
    name = re.sub(r'[^A-Za-z0-9]+', '_', name).strip('_')
    # Приводим к нижнему регистру
    return name.lower()

def create_folder(disk_folder_path, max_attempts=5):
    r"""
    Создает папку на Яндекс.Диске по указанному пути.
    Если папка уже существует (код 409), считается, что она создана.
    Пытается выполнить операцию до max_attempts раз.
    """
    headers = {"Authorization": f"OAuth {ACCESS_TOKEN}"}
    encoded_path = quote(disk_folder_path, safe="/")
    url = "https://cloud-api.yandex.net/v1/disk/resources"
    params = {"path": encoded_path}
    
    attempt = 1
    while attempt <= max_attempts:
        try:
            response = requests.put(url, params=params, headers=headers)
        except Exception as e:
            logging.error(f"Exception при создании папки {disk_folder_path} (попытка {attempt}): {e}")
            time.sleep(2)
            attempt += 1
            continue
        if response.status_code in (201, 409):
            logging.info(f"Папка {disk_folder_path} создана или уже существует (попытка {attempt}).")
            return True
        else:
            logging.error(f"Ошибка создания папки {disk_folder_path} (попытка {attempt}): {response.status_code} {response.text}")
            time.sleep(2)
            attempt += 1
    logging.error(f"Не удалось создать папку {disk_folder_path} после {max_attempts} попыток.")
    return False

def ensure_remote_folder_exists(disk_folder_path):
    r"""
    Создает всю вложенную структуру папок на Яндекс.Диске для указанного пути.
    Например, для "/Folder1/Folder2" последовательно создаст "/Folder1", затем "/Folder1/Folder2".
    Для каждого сегмента пути применяется нормализация через normalize_folder_name.
    """
    # Разбиваем путь на сегменты и нормализуем каждый
    segments = [normalize_folder_name(seg) for seg in disk_folder_path.strip("/").split("/")]
    current_path = ""
    for seg in segments:
        current_path += "/" + seg
        if not create_folder(current_path):
            logging.error(f"Не удалось создать папку: {current_path}")
            if not prompt_continue(f"Ошибка создания папки {current_path}. Продолжить загрузку?"):
                exit(1)
            else:
                return False
    return True

def upload_file(file_path, disk_path, max_attempts=5):
    r"""
    Загружает файл с локального компьютера на Яндекс.Диске, публикует его и возвращает публичную ссылку.
    Повторяет операцию до max_attempts раз, если возникают ошибки.
    
    :param file_path: Локальный путь к файлу, например, r"D:\Users\egorlintos\Desktop\ebatchezaparser\Каталог товаров\scan_img123.jpg"
    :param disk_path: Путь на Яндекс.Диске, куда сохранить файл, например, "/опоры_truboprovodov/scan_img123.jpg"
                      (здесь диск путь составлен из нормализованных имен)
    :return: публичная ссылка или None.
    """
    headers = {"Authorization": f"OAuth {ACCESS_TOKEN}"}
    encoded_disk_path = quote(disk_path, safe="/")
    
    attempt = 1
    while attempt <= max_attempts:
        logging.info(f"Попытка {attempt} загрузить файл: {file_path}")
        try:
            upload_url = "https://cloud-api.yandex.net/v1/disk/resources/upload"
            params = {"path": encoded_disk_path, "overwrite": "true"}
            response = requests.get(upload_url, params=params, headers=headers)
        except Exception as e:
            logging.error(f"Exception при получении URL для загрузки для {disk_path} (попытка {attempt}): {e}")
            time.sleep(2)
            attempt += 1
            continue

        if response.status_code != 200:
            logging.error(f"Ошибка получения ссылки для загрузки (попытка {attempt}): {response.status_code} {response.text}")
            time.sleep(2)
            attempt += 1
            continue
        
        data = response.json()
        href = data.get("href")
        if not href:
            logging.error("Не удалось получить URL для загрузки.")
            time.sleep(2)
            attempt += 1
            continue

        try:
            with open(file_path, "rb") as f:
                upload_response = requests.put(href, data=f)
        except Exception as e:
            logging.error(f"Exception при загрузке файла {file_path} (попытка {attempt}): {e}")
            time.sleep(2)
            attempt += 1
            continue

        if upload_response.status_code not in (200, 201):
            logging.error(f"Ошибка загрузки файла (попытка {attempt}): {upload_response.status_code} {upload_response.text}")
            time.sleep(2)
            attempt += 1
            continue

        try:
            publish_url = "https://cloud-api.yandex.net/v1/disk/resources/publish"
            params = {"path": encoded_disk_path}
            pub_response = requests.put(publish_url, headers=headers, params=params)
        except Exception as e:
            logging.error(f"Exception при публикации файла {disk_path} (попытка {attempt}): {e}")
            time.sleep(2)
            attempt += 1
            continue

        if pub_response.status_code != 200:
            logging.error(f"Ошибка публикации файла (попытка {attempt}): {pub_response.status_code} {pub_response.text}")
            time.sleep(2)
            attempt += 1
            continue

        try:
            info_url = "https://cloud-api.yandex.net/v1/disk/resources"
            params = {"path": encoded_disk_path}
            info_response = requests.get(info_url, headers=headers, params=params)
        except Exception as e:
            logging.error(f"Exception при получении информации о файле {disk_path} (попытка {attempt}): {e}")
            time.sleep(2)
            attempt += 1
            continue

        if info_response.status_code != 200:
            logging.error(f"Ошибка получения информации о файле (попытка {attempt}): {info_response.status_code} {info_response.text}")
            time.sleep(2)
            attempt += 1
            continue

        info_data = info_response.json()
        public_url = info_data.get("public_url")
        if public_url:
            logging.info(f"Получена публичная ссылка: {public_url}")
            return public_url
        else:
            logging.error("Public URL не найден в ответе.")
            time.sleep(2)
            attempt += 1
    logging.error(f"Не удалось загрузить файл {file_path} после {max_attempts} попыток.")
    return None

def update_json_file(file_path, data, max_attempts=5):
    """
    Обновляет JSON-файл, записывая туда словарь data.
    Повторяет операцию до max_attempts раз.
    """
    attempt = 1
    while attempt <= max_attempts:
        try:
            with open(file_path, "w", encoding="utf-8") as outfile:
                json.dump(data, outfile, ensure_ascii=False, indent=4)
            logging.info(f"JSON успешно обновлён: {file_path}")
            return True
        except Exception as e:
            logging.error(f"Exception при обновлении JSON-файла {file_path} (попытка {attempt}): {e}")
            time.sleep(2)
            attempt += 1
    logging.error(f"Не удалось обновить JSON-файл {file_path} после {max_attempts} попыток.")
    return False

def upload_all_files_from_directory(root_directory, remote_base, output_json_path, allowed_exts=None):
    r"""
    Рекурсивно обходит все файлы в указанной корневой директории (и вложенные папки),
    выбирает файлы с указанными расширениями и в имени которых содержится "scan_img" (без учета регистра),
    создает соответствующую структуру папок на Яндекс.Диске, загружает файлы и обновляет JSON-файл
    после каждой успешно загруженной записи.

    В результирующем JSON-словаре ключ – это имя файла (например, "scan_img123.jpg"),
    а значение – публичная ссылка на файл.

    :param root_directory: Корневая локальная директория, например, r"C:\Users\egorlintos\Desktop\ebatchezaparser\Каталог товаров"
    :param remote_base: Базовый путь на Яндекс.Диске (без ведущего слэша), например, "Опоры трубопроводов"
    :param output_json_path: Путь к JSON-файлу для сохранения результата, например, "uploaded_files.json"
    :param allowed_exts: Список разрешённых расширений файлов. Если None, используются стандартные.
    """
    if allowed_exts is None:
        allowed_exts = [".jpg", ".jpeg", ".png", ".gif", ".bmp", ".tiff"]

    # Загружаем существующие результаты, если JSON-файл уже есть
    if os.path.exists(output_json_path):
        try:
            with open(output_json_path, "r", encoding="utf-8") as infile:
                results = json.load(infile)
            logging.info(f"Найден существующий JSON: {output_json_path}")
        except Exception as e:
            logging.error(f"Ошибка загрузки существующего JSON-файла: {e}")
            results = {}
    else:
        results = {}

    # Последний сегмент базового пути для устранения дублирования
    last_segment = remote_base.strip("/").split("/")[-1].lower()

    for dirpath, dirnames, filenames in os.walk(root_directory):
        for filename in filenames:
            if "scan_img" not in filename.lower():
                continue

            ext = os.path.splitext(filename)[1].lower()
            if ext not in allowed_exts:
                continue

            if filename in results:
                logging.info(f"Файл уже загружен: {filename}")
                continue

            local_file_path = os.path.join(dirpath, filename)
            rel_path = os.path.relpath(local_file_path, root_directory).replace("\\", "/")
            # Если относительный путь начинается с last_segment, удаляем его
            if rel_path.lower().startswith(last_segment + "/"):
                rel_path = rel_path[len(last_segment)+1:]
            # Нормализуем каждый сегмент пути для удалённого диска
            norm_segments = [normalize_folder_name(seg) for seg in rel_path.split("/")]
            norm_rel_path = "/".join(norm_segments)
            # Формируем удалённый путь: базовый путь (нормализованный) + нормализованный относительный путь
            norm_remote_base = normalize_folder_name(remote_base)
            remote_disk_path = f"/{norm_remote_base}/{norm_rel_path}"

            remote_folder = os.path.dirname(remote_disk_path)
            logging.info(f"Создаем (или проверяем) папку на Яндекс.Диске: {remote_folder}")
            if not ensure_remote_folder_exists(remote_folder):
                logging.error(f"Не удалось создать папку: {remote_folder}.")
                user_input = input(f"Продолжить загрузку после ошибки создания папки {remote_folder}? (Y/n): ").strip().lower()
                if user_input not in ["", "y"]:
                    exit(1)
                else:
                    continue

            logging.info(f"Загружаем файл: {local_file_path} на {remote_disk_path}")
            public_url = upload_file(local_file_path, remote_disk_path)
            if public_url:
                results[filename] = public_url
                logging.info(f"Успешно загружено: {filename} -> {public_url}")
                update_json_file(output_json_path, results)
            else:
                logging.error(f"Ошибка загрузки файла: {filename}")
                user_input = input(f"Продолжить загрузку после ошибки загрузки файла {filename}? (Y/n): ").strip().lower()
                if user_input not in ["", "y"]:
                    exit(1)

    logging.info(f"Итоговые данные сохранены в: {output_json_path}")

if __name__ == "__main__":
    root_dir = r"C:\Users\egorlintos\Desktop\ebatchezaparser\Каталог товаров"
    remote_base_path = "Опоры трубопроводов"
    output_json_file = "uploaded_files.json"
    
    upload_all_files_from_directory(root_dir, remote_base_path, output_json_file)
