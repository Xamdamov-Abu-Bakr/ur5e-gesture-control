"""Model files are downloaded once into ./models."""
import os, urllib.request
from config import MODEL_DIR


def ensure(name, url):
    os.makedirs(MODEL_DIR, exist_ok=True)
    path = os.path.join(MODEL_DIR, name)
    if not os.path.isfile(path):
        print(f"[model] downloading {name} ...")
        urllib.request.urlretrieve(url, path)
    return path
