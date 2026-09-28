"""
NEO Indexer v4.0 - Profesyonel Veri İndeksleme Motoru
- Duplicate önleme
- Türkçe karakter desteği
- Akıllı chunking
"""

import chromadb
import ollama
from pathlib import Path

# ==================== YAPILANDIRMA ====================
TARGET_DIRECTORIES = [
    Path.home() / "git",
    Path.home() / "source",
    Path.home() / "OneDrive - Ostim Teknik Universitesi",
    Path.home() / "NeoProjects"
]

ALLOWED_EXTENSIONS = {
    ".py", ".js", ".ts", ".md", ".txt", ".json", ".yml", ".yaml",
    ".html", ".css", ".sql", ".sh", ".bat", ".ps1",
    ".c", ".cpp", ".h", ".hpp", ".java", ".ino", ".cs"
}

EXCLUDE_DIRS = {
    "node_modules", "venv", "env", ".venv", "__pycache__",
    ".git", ".svn", ".hg", "dist", "build", ".next", ".nuxt",
    "coverage", ".cache", ".pytest_cache", "migrations",
    "Euro Truck Simulator 2", "ansel", "Application Data",
    "AppData", "Cookies", "Recent", "SendTo", "Start Menu",
    "neo_db", ".idea", ".vscode"
}

EXCLUDE_FILES = {
    ".env", ".env.local", "config.json", "secrets.json",
    "credentials.json", "passwords.txt", "package-lock.json",
    "yarn.lock", "desktop.ini", "thumbs.db", ".DS_Store"
}

DB_PATH = str(Path.home() / "NeoProjects" / "neo_db")
COLLECTION_NAME = "developer_knowledge"
CHUNK_SIZE = 400  # Optimize edilmiş chunk boyutu

# ==================== VERİTABANI ====================
chroma_client = chromadb.PersistentClient(path=DB_PATH)
collection = chroma_client.get_or_create_collection(name=COLLECTION_NAME)

# ==================== YARDIMCI FONKSİYONLAR ====================
def get_text_chunks(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = 50) -> list:
    """Metni, üst üste binen parçalara böler."""
    chunks = []
    step = chunk_size - overlap
    for i in range(0, len(text), step):
        chunk = text[i:i + chunk_size]
        if chunk.strip():
            chunks.append(chunk)
    return chunks

def should_exclude(file_path: Path) -> bool:
    """Dosyanın indekslenip indekslenmeyeceğini kontrol eder."""
    if file_path.name in EXCLUDE_FILES:
        return True
    for part in file_path.parts:
        if part in EXCLUDE_DIRS:
            return True
    try:
        if file_path.stat().st_size > 1_000_000:  # 1MB limit
            return True
    except:
        return True
    return False

# ==================== ANA İNDEKSLEME FONKSİYONU ====================
def index_directory(directory: Path):
    """Belirtilen dizini tarar, dosyaları okur ve vektör veritabanına ekler."""
    if not directory.exists():
        print(f"⚠️ Atlandı (Bulunamadı): {directory}")
        return 0, 0

    print(f"\n Taranıyor: {directory}")
    files_indexed = 0
    files_skipped = 0
    total_chunks = 0

    for file_path in directory.rglob("*"):
        if not file_path.is_file():
            continue
        if file_path.suffix.lower() not in ALLOWED_EXTENSIONS:
            files_skipped += 1
            continue
        if should_exclude(file_path):
            files_skipped += 1
            continue

        try:
            content = file_path.read_text(encoding="utf-8")
            chunks = get_text_chunks(content)

            if not chunks:
                files_skipped += 1
                continue

            # 🔥 DUPLICATE ÖNLEME: Önce eski kayıtları sil
            old_data = collection.get(where={"file_path": str(file_path)})
            if old_data['ids']:
                collection.delete(ids=old_data['ids'])

            documents_to_add = []
            metadatas_to_add = []
            ids_to_add = []

            for i, chunk in enumerate(chunks):
                doc_id = f"{file_path.as_posix()}_{i}"
                documents_to_add.append(chunk)
                metadatas_to_add.append({
                    "file_path": str(file_path),
                    "file_name": file_path.name,
                    "extension": file_path.suffix
                })
                ids_to_add.append(doc_id)

            files_indexed += 1
            if files_indexed % 20 == 0:
                print(f"  ⚙️ İlerleme: {files_indexed} dosya işlendi...")

            # Embedding üret (tek tek - garanti yöntem)
            embeddings_list = []
            for chunk in documents_to_add:
                response = ollama.embeddings(model="nomic-embed-text", prompt=chunk)
                embeddings_list.append(response['embedding'])

            # ChromaDB'ye ekle
            collection.add(
                documents=documents_to_add,
                metadatas=metadatas_to_add,
                embeddings=embeddings_list,
                ids=ids_to_add
            )
            total_chunks += len(chunks)

        except UnicodeDecodeError:
            files_skipped += 1
        except Exception as e:
            print(f"  ⚠️ Hata ({file_path.name}): {e}")
            files_skipped += 1

    print(f"  ✅ Tamamlandı: {files_indexed} dosya eklendi, {files_skipped} atlandı.")
    return files_indexed, total_chunks

# ==================== ANA PROGRAM ====================
if __name__ == "__main__":
    print("🚀 NEO Indexer v4.0 - Profesyonel Veri İndeksleme")
    print("=" * 60)

    grand_total_files = 0
    grand_total_chunks = 0

    for target_dir in TARGET_DIRECTORIES:
        files, chunks = index_directory(target_dir)
        grand_total_files += files
        grand_total_chunks += chunks

    print("\n" + "=" * 60)
    print(" GENEL TOPLAM")
    print(f"📊 İşlenen toplam dosya: {grand_total_files}")
    print(f"📝 Veritabanındaki toplam parça (chunk): {grand_total_chunks}")
    print("=" * 60)