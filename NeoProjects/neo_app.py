"""
NEO v6.1 - Local Knowledge Assistant
- Hibrit Arama (Keyword + Vector)
- Otomatik Dosya İzleme (File Watcher)
- Clipboard Watcher (Kod Tekrarı Tespiti)
- Mülakat Modu (STAR Formatı)
- Proje Bazlı Özet
- Günlük Özet Komutu
- Hareketli Düşünme Animasyonu
- Responsive Layout
"""

import sys
import re
import time
import hashlib
from datetime import datetime
from pathlib import Path

# PySide6
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                                QHBoxLayout, QLineEdit, QListWidget, QListWidgetItem,
                                QLabel, QTextEdit, QSystemTrayIcon, QMenu, QSplitter,
                                QPushButton, QGraphicsOpacityEffect, QComboBox, QDialog)
from PySide6.QtCore import Qt, QTimer, QThread, Signal, QPropertyAnimation, QEasingCurve
from PySide6.QtGui import QFont, QIcon, QAction, QPixmap, QPainter, QColor

# Global Hotkey & File Watcher
from pynput import keyboard
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

# Clipboard
import pyperclip

# RAG
import chromadb
import ollama

# ==================== YAPILANDIRMA ====================
DB_PATH = str(Path.home() / "NeoProjects" / "neo_db")
CHAT_MODEL = "qwen2.5:3b"
COLLECTION_NAME = "developer_knowledge"
SNIPPET_COLLECTION = "code_snippets"

WATCH_DIRS = [
    Path.home() / "NeoProjects" / "Mercedes_Demo_Projesi",
    Path.home() / "NeoProjects",
]

ALLOWED_EXTENSIONS = {
    ".py", ".js", ".ts", ".md", ".txt", ".json", ".yml", ".yaml",
    ".html", ".css", ".sql", ".sh", ".bat", ".ps1",
    ".c", ".cpp", ".h", ".hpp", ".java", ".ino", ".cs"
}

EXCLUDE_DIRS = {
    "node_modules", "venv", "env", ".venv", "__pycache__",
    ".git", "dist", "build", "neo_db", ".idea", ".vscode",
    "Euro Truck Simulator 2", "ansel", "AppData"
}

EXCLUDE_FILES = {
    ".env", ".env.local", "config.json", "secrets.json",
    "desktop.ini", "thumbs.db", ".DS_Store", "neo_app.py"
}


# ==================== YARDIMCI FONKSİYONLAR ====================
def normalize_text(text: str) -> str:
    turkish_map = {
        'ı': 'i', 'İ': 'i', 'ş': 's', 'Ş': 's',
        'ğ': 'g', 'Ğ': 'g', 'ü': 'u', 'Ü': 'u',
        'ö': 'o', 'Ö': 'o', 'ç': 'c', 'Ç': 'c'
    }
    text = text.lower()
    for tr, en in turkish_map.items():
        text = text.replace(tr, en)
    text = re.sub(r'[^\w\s]', '', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def stem_turkish(word: str) -> str:
    if len(word) <= 4:
        return word
    suffixes = [
        'larda', 'lerde', 'ta', 'te', 'da', 'de',
        'ları', 'leri', 'lar', 'ler',
        'ında', 'inde', 'unda', 'ünde',
        'ımda', 'imde', 'umda', 'ümde',
        'ımı', 'imi', 'umu', 'ümü',
        'ın', 'in', 'un', 'ün',
        'ım', 'im', 'um', 'üm',
        'ı', 'i', 'u', 'ü',
        'dan', 'den', 'tan', 'ten',
        'la', 'le', 'ca', 'ce', 'ki'
    ]
    for suffix in suffixes:
        if word.endswith(suffix) and len(word) - len(suffix) >= 3:
            return word[:-len(suffix)]
    return word


def extract_query_keywords(query: str) -> list:
    stop_words = {
        'ne', 'var', 'yok', 'için', 'ile', 'gibi', 'hakkında',
        'sorduğum', 'sordum', 'yazıyor', 'bulunuyor', 'bulamadım',
        'bir', 'bu', 'şu', 'o', 'da', 'de', 'ki', 'mi', 'mı',
        'mu', 'mü', 've', 'veya', 'ama', 'fakat', 'ancak',
        'dosyamda', 'dosyanda', 'dosyasında', 'dosyada', 'dosyayı',
        'kodda', 'kodunda', 'projemde', 'projesinde', 'cvimde',
        'cvde', 'notumda', 'notlarda', 'belgede',
        'nedir', 'nasıl', 'hangi', 'kaç', 'neler', 'yazıyor'
    }
    normalized = normalize_text(query)
    words = normalized.split()
    keywords = []
    for word in words:
        if len(word) < 2:
            continue
        if word in stop_words:
            continue
        stemmed = stem_turkish(word)
        if len(stemmed) >= 2:
            keywords.append(stemmed)
    return keywords

# ==================== RAG MOTORU ====================
class NeoRAGEngine:
    def __init__(self):
        self.chroma_client = chromadb.PersistentClient(path=DB_PATH)
        self.collection = self.chroma_client.get_or_create_collection(name=COLLECTION_NAME)
        self.snippet_collection = self.chroma_client.get_or_create_collection(name=SNIPPET_COLLECTION)

    def _keyword_only_search(self, query: str, top_k: int = 15):
        """Kısa sorgular için sadece keyword search (hızlı)."""
        query_normalized = normalize_text(query)
        query_words = [w for w in query_normalized.split() if len(w) >= 2]
        
        matches = []
        try:
            all_data = self.collection.get(include=['documents', 'metadatas'])
            if all_data['documents']:
                for i, doc in enumerate(all_data['documents']):
                    doc_normalized = normalize_text(doc)
                    file_name = all_data['metadatas'][i].get('file_name', '').lower()
                    file_name_normalized = normalize_text(file_name)
                    
                    score = 0
                    for kw in query_words:
                        if kw in doc_normalized:
                            score += 1
                        if kw in file_name_normalized:
                            score += 5  # Dosya adında eşleşme çok önemli
                    
                    if score > 0:
                        matches.append({
                            'id': all_data['ids'][i],
                            'document': doc,
                            'metadata': all_data['metadatas'][i],
                            'score': score
                        })
                
                matches.sort(key=lambda x: x['score'], reverse=True)
        except Exception as e:
            print(f"Keyword arama hatası: {e}")
        
        final_docs = [m['document'] for m in matches[:top_k]]
        final_metas = [m['metadata'] for m in matches[:top_k]]
        
        return {
            'documents': [final_docs],
            'metadatas': [final_metas]
        }

    def search(self, query: str, top_k: int = 15):
        query_keywords = extract_query_keywords(query)
        
        # KISA SORGULAR İÇİN ÖZEL DURUM (cv, stm32, python vb.)
        is_short_query = len(query.strip()) <= 5 and len(query_keywords) <= 2
        
        if is_short_query:
            # Sadece keyword search yap, vector search'ü atla (hızlı!)
            return self._keyword_only_search(query, top_k)
        
        if not query_keywords:
            query_keywords = [w for w in normalize_text(query).split() if len(w) > 2]
        
        keyword_matches = []
        try:
            all_data = self.collection.get(include=['documents', 'metadatas'])
            if all_data['documents']:
                for i, doc in enumerate(all_data['documents']):
                    doc_normalized = normalize_text(doc)
                    file_name = all_data['metadatas'][i].get('file_name', '').lower()
                    file_name_normalized = normalize_text(file_name)

                    keyword_score = 0
                    for kw in query_keywords:
                        if kw in doc_normalized:
                            keyword_score += 1
                        if kw in file_name_normalized:
                            keyword_score += 3

                    if keyword_score > 0:
                        keyword_matches.append({
                            'id': all_data['ids'][i],
                            'document': doc,
                            'metadata': all_data['metadatas'][i],
                            'score': keyword_score
                        })
                keyword_matches.sort(key=lambda x: x['score'], reverse=True)
        except Exception as e:
            print(f"Keyword arama hatası: {e}")

        vector_results = {'documents': [[]], 'metadatas': [[]], 'ids': [[]]}
        try:
            response = ollama.embeddings(model="nomic-embed-text", prompt=query)
            vector_results = self.collection.query(
                query_embeddings=[response['embedding']],
                n_results=top_k
            )
        except Exception as e:
            print(f"Vektör arama hatası: {e}")

        final_docs, final_metas, seen_ids = [], [], set()

        for match in keyword_matches:
            if match['score'] >= 2 and match['id'] not in seen_ids:
                final_docs.append(match['document'])
                final_metas.append(match['metadata'])
                seen_ids.add(match['id'])

        if vector_results['documents'][0]:
            for doc, meta, doc_id in zip(
                vector_results['documents'][0],
                vector_results['metadatas'][0],
                vector_results['ids'][0]
            ):
                if doc_id not in seen_ids and len(final_docs) < top_k:
                    final_docs.append(doc)
                    final_metas.append(meta)
                    seen_ids.add(doc_id)

        for match in keyword_matches:
            if match['id'] not in seen_ids and len(final_docs) < top_k:
                final_docs.append(match['document'])
                final_metas.append(match['metadata'])
                seen_ids.add(match['id'])

        return {
            'documents': [final_docs[:top_k]],
            'metadatas': [final_metas[:top_k]]
        }

    def ask(self, query: str, top_k: int = 15):
        results = self.search(query, top_k)
        if not results or not results['documents'][0]:
            return "Veritabanımda bu konuda bir bilgi bulamadım.", None

        documents = results['documents'][0][:5]
        metadatas = results['metadatas'][0][:5]

        context_text = ""
        for i, (doc, meta) in enumerate(zip(documents, metadatas)):
            file_name = meta.get('file_name', 'unknown')
            context_text += f"[{file_name}]\n{doc[:300]}...\n\n"

        system_prompt = f"""Sen NEO'sun. Kullanıcının sorusunu aşağıdaki dosyalardan cevapla.

Dosyalar:
{context_text}

Soru: {query}

Cevabını kısa ve Türkçe ver."""

        try:
            chat_response = ollama.chat(
                model=CHAT_MODEL,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": query}
                ],
                options={"temperature": 0.2}
            )
            return chat_response['message']['content'].strip(), results
        except Exception as e:
            return f"Hata: {e}", results

    def mulakat_modu(self, proje_adi: str):
        results = self.search(proje_adi, top_k=10)

        if not results or not results['documents'][0]:
            return f"'{proje_adi}' ile ilgili veritabanımda bilgi yok."

        documents = results['documents'][0]
        metadatas = results['metadatas'][0]

        full_context = ""
        for doc, meta in zip(documents, metadatas):
            file_name = meta.get('file_name', '')
            full_context += f"\n[{file_name}]\n{doc[:500]}\n"

        system_prompt = f"""Sen NEO'sun, kullanıcının kariyer koçusun.

Kullanıcı mülakatta "{proje_adi}" projesini anlatmak istiyor.
Aşağıdaki dosyalardan bu projeyi analiz et ve STAR formatında mülakat cevabı hazırla.

STAR FORMATI:
- **S (Situation/Durum):** Proje neden başladı? Hangi problem çözüldü?
- **T (Task/Görev):** Senin rolün neydi?
- **A (Action/Eylem):** Hangi teknolojileri kullandın? Nasıl implement ettin?
- **R (Result/Sonuç):** Ne başardın? Ne öğrendin?

Kurallar:
1. Türkçe cevap ver
2. Her bölüm için 2-3 cümle yaz
3. Somut teknik detaylar ver
4. Mülakatçı etkileyici bulsun

Dosyalar:
{full_context}

Proje: {proje_adi}"""

        try:
            chat_response = ollama.chat(
                model=CHAT_MODEL,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"{proje_adi} projesini STAR formatında anlat"}
                ],
                options={"temperature": 0.3}
            )
            return chat_response['message']['content'].strip()
        except Exception as e:
            return f"Hata: {e}"

    def proje_ozeti(self, proje_adi: str):
        results = self.search(proje_adi, top_k=10)

        if not results or not results['documents'][0]:
            return f"'{proje_adi}' ile ilgili bilgi yok."

        documents = results['documents'][0]
        metadatas = results['metadatas'][0]

        files_by_name = {}
        for doc, meta in zip(documents, metadatas):
            file_name = meta.get('file_name', 'unknown')
            if file_name not in files_by_name:
                files_by_name[file_name] = []
            files_by_name[file_name].append(doc)

        full_context = ""
        for file_name, docs in files_by_name.items():
            full_context += f"\n=== {file_name} ===\n"
            full_context += "\n".join(docs)[:500] + "\n"

        system_prompt = f"""Sen NEO'sun, proje yöneticisisin.

Aşağıdaki dosyalardan "{proje_adi}" projesinin kapsamlı özetini çıkar.

ÖZET ŞABLONU:
1. **Proje Amacı:** Ne yapıyor?
2. **Teknolojiler:** Hangi diller, kütüphaneler, araçlar?
3. **Dosya Yapısı:** Hangi dosyalar var?
4. **Önemli Fonksiyonlar:** Ana bileşenler neler?
5. **Öğrenilen Dersler:** Bu projeden ne çıkarılabilir?

Türkçe, net ve teknik detaylı cevap ver.

Dosyalar:
{full_context}"""

        try:
            chat_response = ollama.chat(
                model=CHAT_MODEL,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"{proje_adi} projesini özetle"}
                ],
                options={"temperature": 0.2}
            )
            return chat_response['message']['content'].strip()
        except Exception as e:
            return f"Hata: {e}"

    def get_daily_summary(self):
        today = datetime.now().date().isoformat()

        try:
            all_data = self.collection.get(include=['metadatas'])
            today_files = []

            for meta in all_data['metadatas']:
                file_path = meta.get('file_path', '')
                if file_path:
                    try:
                        mtime = Path(file_path).stat().st_mtime
                        file_date = datetime.fromtimestamp(mtime).date().isoformat()
                        if file_date == today:
                            today_files.append(meta.get('file_name', ''))
                    except:
                        pass

            snippet_count = self.snippet_collection.count()

            summary = f" **Bugünün Özeti** ({datetime.now().strftime('%d.%m.%Y')})\n\n"
            summary += f"**İndekslenen Dosyalar:** {len(set(today_files))}\n"

            if today_files:
                summary += "\n**Dosyalar:**\n"
                for f in sorted(set(today_files)):
                    summary += f"  - {f}\n"
            else:
                summary += "\nBugün yeni dosya indekslenmedi.\n"

            summary += f"\n**Kaydedilen Snippet'ler:** {snippet_count}\n"

            return summary
        except Exception as e:
            return f"Hata: {e}"

    def save_snippet(self, code: str, source_file: str = ""):
        if len(code) < 20:
            return False

        try:
            code_hash = hashlib.sha256(code[:200].encode()).hexdigest()

            old_data = self.snippet_collection.get(where={"code_hash": code_hash})
            if old_data['ids']:
                return False

            doc_id = f"snippet_{int(time.time())}"
            embedding_resp = ollama.embeddings(model="nomic-embed-text", prompt=code[:500])

            self.snippet_collection.add(
                documents=[code[:2000]],
                metadatas=[{
                    "code_hash": code_hash,
                    "source_file": source_file,
                    "timestamp": datetime.now().isoformat(),
                    "length": len(code)
                }],
                embeddings=[embedding_resp['embedding']],
                ids=[doc_id]
            )
            print(f"💾 Snippet kaydedildi: {code_hash[:16]}...")
            return True
        except Exception as e:
            print(f"Snippet kaydetme hatası: {e}")
            return False

    def search_similar_snippet(self, code: str):
        if len(code) < 30:
            return None

        try:
            code_hash = hashlib.sha256(code[:200].encode()).hexdigest()
            exact_match = self.snippet_collection.get(where={"code_hash": code_hash})

            if exact_match['ids']:
                metadata = exact_match['metadatas'][0]
                print(f"🎯 Exact match bulundu: {metadata.get('source_file', '')}")
                return {
                    'code': exact_match['documents'][0],
                    'source': metadata.get('source_file', 'bilinmiyor'),
                    'timestamp': metadata.get('timestamp', '')
                }

            embedding_resp = ollama.embeddings(model="nomic-embed-text", prompt=code[:500])
            results = self.snippet_collection.query(
                query_embeddings=[embedding_resp['embedding']],
                n_results=3
            )

            if results['documents'][0] and results['distances'][0][0] < 0.5:
                metadata = results['metadatas'][0][0]
                print(f"🔍 Semantic match bulundu: {metadata.get('source_file', '')}")
                return {
                    'code': results['documents'][0][0],
                    'source': metadata.get('source_file', 'bilinmiyor'),
                    'timestamp': metadata.get('timestamp', '')
                }
        except Exception as e:
            print(f"Snippet arama hatası: {e}")

        return None

    def index_file(self, file_path: Path):
        if not file_path.is_file():
            return False
        if file_path.suffix.lower() not in ALLOWED_EXTENSIONS:
            return False
        for part in file_path.parts:
            if part in EXCLUDE_DIRS:
                return False
        if file_path.name in EXCLUDE_FILES:
            return False

        try:
            content = file_path.read_text(encoding="utf-8")
            if not content.strip():
                return False

            old_data = self.collection.get(where={"file_path": str(file_path)})
            if old_data['ids']:
                self.collection.delete(ids=old_data['ids'])

            chunks = []
            chunk_size, overlap = 400, 50
            step = chunk_size - overlap
            for i in range(0, len(content), step):
                chunk = content[i:i + chunk_size]
                if chunk.strip():
                    chunks.append(chunk)

            if not chunks:
                return False

            documents, metadatas, ids = [], [], []
            for i, chunk in enumerate(chunks):
                doc_id = f"{file_path.as_posix()}_{i}"
                documents.append(chunk)
                metadatas.append({
                    "file_path": str(file_path),
                    "file_name": file_path.name,
                    "extension": file_path.suffix
                })
                ids.append(doc_id)

            embeddings = []
            for chunk in documents:
                resp = ollama.embeddings(model="nomic-embed-text", prompt=chunk)
                embeddings.append(resp['embedding'])

            self.collection.add(
                documents=documents,
                metadatas=metadatas,
                embeddings=embeddings,
                ids=ids
            )
            return True
        except Exception as e:
            print(f"İndeksleme hatası ({file_path.name}): {e}")
            return False


# ==================== FILE WATCHER ====================
class FileWatcherThread(QThread):
    file_indexed = Signal(str)
    error_occurred = Signal(str)

    def __init__(self, rag_engine, watch_dirs):
        super().__init__()
        self.rag_engine = rag_engine
        self.watch_dirs = watch_dirs
        self._debounce = {}
        self._running = True

    def run(self):
        class Handler(FileSystemEventHandler):
            def __init__(self, outer):
                self.outer = outer

            def on_created(self, event):
                if not event.is_directory:
                    self.outer._schedule_index(event.src_path)

            def on_modified(self, event):
                if not event.is_directory:
                    self.outer._schedule_index(event.src_path)

            def on_deleted(self, event):
                if not event.is_directory:
                    self.outer._delete_file(event.src_path)

        handler = Handler(self)
        observer = Observer()

        for watch_dir in self.watch_dirs:
            if watch_dir.exists():
                observer.schedule(handler, str(watch_dir), recursive=True)

        observer.start()

        while self._running:
            now = time.time()
            to_process = []

            for file_path, last_change in list(self._debounce.items()):
                if now - last_change > 2.0:
                    to_process.append(file_path)
                    del self._debounce[file_path]

            for file_path in to_process:
                try:
                    success = self.rag_engine.index_file(Path(file_path))
                    if success:
                        self.file_indexed.emit(Path(file_path).name)
                except Exception as e:
                    self.error_occurred.emit(str(e))

            time.sleep(0.5)

        observer.stop()
        observer.join()

    def _schedule_index(self, file_path):
        p = Path(file_path)
        if p.suffix.lower() in ALLOWED_EXTENSIONS:
            self._debounce[file_path] = time.time()

    def _delete_file(self, file_path):
        try:
            old_data = self.rag_engine.collection.get(where={"file_path": file_path})
            if old_data['ids']:
                self.rag_engine.collection.delete(ids=old_data['ids'])
        except:
            pass

    def stop(self):
        self._running = False


# ==================== CLIPBOARD WATCHER ====================
class ClipboardWatcherThread(QThread):
    snippet_found = Signal(str, str)
    new_snippet_saved = Signal(str)

    def __init__(self, rag_engine):
        super().__init__()
        self.rag_engine = rag_engine
        self._last_clipboard = ""
        self._running = True

    def run(self):
        while self._running:
            try:
                current = pyperclip.paste()

                if current and current != self._last_clipboard and len(current) >= 30:
                    self._last_clipboard = current

                    if self._looks_like_code(current):
                        similar = self.rag_engine.search_similar_snippet(current)
                        if similar:
                            self.snippet_found.emit(current[:100], similar['source'])
                        else:
                            if self.rag_engine.save_snippet(current):
                                self.new_snippet_saved.emit(current[:50])

                time.sleep(1.5)
            except Exception as e:
                print(f"Clipboard hatası: {e}")
                time.sleep(2)

    def _looks_like_code(self, text: str) -> bool:
        code_indicators = ['def ', 'class ', 'function ', 'import ', 'from ',
                          '#include', 'int main', 'void ', 'return ', 'if ',
                          'for ', 'while ', 'print(', 'console.log', '{', '}']
        return any(indicator in text for indicator in code_indicators)

    def stop(self):
        self._running = False


# ==================== ARAMA THREAD ====================
class SearchWorker(QThread):
    finished = Signal(str, object)

    def __init__(self, rag_engine, query):
        super().__init__()
        self.rag_engine = rag_engine
        self.query = query

    def run(self):
        cevap, results = self.rag_engine.ask(self.query, top_k=15)
        self.finished.emit(cevap, results)


# ==================== ANA PENCERE ====================
class NeoMainWindow(QMainWindow):
    def __init__(self, rag_engine):
        super().__init__()
        self.rag_engine = rag_engine
        self.worker = None
        self.tray_icon = None
        self.stats = {'questions': 0, 'files_indexed': 0, 'snippets_saved': 0}

        self.setWindowTitle("NEO")
        self.setMinimumSize(800, 500)
        self.resize(1100, 700)
        self.setStyleSheet("QMainWindow { background-color: #0a0a0a; }")

        screen = QApplication.primaryScreen().geometry()
        x = (screen.width() - self.width()) // 2
        y = (screen.height() - self.height()) // 2
        self.move(x, y)

        self.init_ui()

    def init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(12, 12, 12, 12)
        main_layout.setSpacing(10)

        # ÜST BAR
        header_layout = QHBoxLayout()

        title = QLabel("NEO")
        title.setFont(QFont("Segoe UI", 22, QFont.Bold))
        title.setStyleSheet("color: #00d2ff; background: transparent;")
        header_layout.addWidget(title)

        header_layout.addStretch()

        self.stats_label = QLabel("📊 0 soru • 0 dosya • 0 snippet")
        self.stats_label.setFont(QFont("Segoe UI", 9))
        self.stats_label.setStyleSheet("color: #666; background: transparent;")
        header_layout.addWidget(self.stats_label)

        main_layout.addLayout(header_layout)

        # ARAMA ALANI (Konteyner Yöntemi ile İç İçe Tasarım)
        search_layout = QHBoxLayout()

        # 1. Dış Çerçeve (Searchbox ve Butonu birlikte saran kutu)
        search_wrapper = QWidget()
        search_wrapper.setObjectName("SearchWrapper")
        search_wrapper.setStyleSheet("""
            QWidget#SearchWrapper {
                background-color: #151515;
                border: 2px solid #00d2ff;
                border-radius: 8px;
            }
        """)
        
        # İç düzen: Boşluksuz ve bitişik
        wrapper_inner_layout = QHBoxLayout(search_wrapper)
        wrapper_inner_layout.setContentsMargins(0, 0, 0, 0)
        wrapper_inner_layout.setSpacing(0)

        # 2. Gerçek Yazı Alanı (Kenarlıkları kaldırıldı, şeffaf)
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Bir şey sor... (veya 'mülakat: stm32', 'özet: neo')")
        self.search_input.setFont(QFont("Segoe UI", 13))
        self.search_input.setStyleSheet("""
            QLineEdit {
                background-color: transparent;
                color: #fff;
                border: none;
                padding: 12px 14px;
            }
            QLineEdit:focus {
                outline: none; /* Odaklanınca ekstra çerçeve çıkmasın */
            }
        """)
        self.search_input.returnPressed.connect(self.perform_search)
        self.search_input.textChanged.connect(self.toggle_clear_button)
        wrapper_inner_layout.addWidget(self.search_input)

        # 3. Şık Temizleme Butonu (Kutunun içinde, sağda)
        self.clear_btn = QPushButton("✕")
        self.clear_btn.setFixedSize(36, 36) # Kare alan, metin ortada durur
        self.clear_btn.setCursor(Qt.PointingHandCursor) # Fare el işaretine döner
        self.clear_btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                color: #00d2ff; /* NEO Mavisi ile başlar */
                border: none;
                font-size: 18px;
                font-weight: bold;
            }
            QPushButton:hover {
                color: #ff4444; /* Yazı kırmızıya döner */
                background-color: rgba(255, 68, 68, 0.45); /* Yumuşak geçiş için çok hafif kırmızı arka plan */
            }
        """)
        self.clear_btn.setVisible(False) # Başlangıçta gizli
        self.clear_btn.clicked.connect(self.clear_search)
        wrapper_inner_layout.addWidget(self.clear_btn)

        # Wrapper'ı ana arama düzenine ekle
        search_layout.addWidget(search_wrapper)

        # 4. "Ara" Butonu (Ayrı durur)
        self.search_btn = QPushButton("Ara")
        self.search_btn.setFont(QFont("Segoe UI", 11, QFont.Bold))
        self.search_btn.setStyleSheet("""
            QPushButton {
                background-color: #00d2ff;
                color: #000;
                border: none;
                border-radius: 8px;
                padding: 12px 24px;
            }
            QPushButton:hover { background-color: #0055ff; color: #fff; }
            QPushButton:disabled { background-color: #333; color: #666; }
        """)
        self.search_btn.clicked.connect(self.perform_search)
        search_layout.addWidget(self.search_btn)

        main_layout.addLayout(search_layout)

        # ---------------------------------------

        self.search_btn = QPushButton("Ara")
        self.search_btn.setFont(QFont("Segoe UI", 11, QFont.Bold))
        self.search_btn.setStyleSheet("""
            QPushButton {
                background-color: #00d2ff;
                color: #000;
                border: none;
                border-radius: 8px;
                padding: 12px 24px;
            }
            QPushButton:hover { background-color: #0055ff; color: #fff; }
            QPushButton:disabled { background-color: #333; color: #666; }
        """)
        self.search_btn.clicked.connect(self.perform_search)
        search_layout.addWidget(self.search_btn)

        main_layout.addLayout(search_layout)

        # ÖZEL MOD BUTONLARI
        mode_layout = QHBoxLayout()

        self.mulakat_btn = QPushButton("🎤 Mülakat Modu")
        self.mulakat_btn.setStyleSheet("""
            QPushButton {
                background-color: #1a1a1a;
                color: #00d2ff;
                border: 1px solid #00d2ff;
                border-radius: 6px;
                padding: 8px 16px;
            }
            QPushButton:hover { background-color: #00d2ff; color: #000; }
        """)
        self.mulakat_btn.clicked.connect(self.show_mulakat_dialog)
        mode_layout.addWidget(self.mulakat_btn)

        self.ozet_btn = QPushButton("📋 Proje Özeti")
        self.ozet_btn.setStyleSheet("""
            QPushButton {
                background-color: #1a1a1a;
                color: #00d2ff;
                border: 1px solid #00d2ff;
                border-radius: 6px;
                padding: 8px 16px;
            }
            QPushButton:hover { background-color: #00d2ff; color: #000; }
        """)
        self.ozet_btn.clicked.connect(self.show_ozet_dialog)
        mode_layout.addWidget(self.ozet_btn)

        mode_layout.addStretch()
        main_layout.addLayout(mode_layout)

        # AYIRICI
        self.splitter = QSplitter(Qt.Horizontal)

        # SOL: Cevap
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)

        left_label = QLabel("Cevap")
        left_label.setFont(QFont("Segoe UI", 10, QFont.Bold))
        left_label.setStyleSheet("color: #00d2ff;")
        left_layout.addWidget(left_label)

        self.ai_answer = QTextEdit()
        self.ai_answer.setReadOnly(True)
        self.ai_answer.setFont(QFont("Segoe UI", 12))
        self.ai_answer.setStyleSheet("""
            QTextEdit {
                background-color: #151515;
                color: #fff;
                border: 1px solid #2a2a2a;
                border-radius: 8px;
                padding: 15px;
            }
        """)
        self.ai_answer.setPlaceholderText("Sorunu yaz, NEO cevaplasın...")
        left_layout.addWidget(self.ai_answer)

        self.splitter.addWidget(left_widget)

        # SAĞ: Kaynaklar
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)

        right_label = QLabel("Kaynaklar")
        right_label.setFont(QFont("Segoe UI", 10, QFont.Bold))
        right_label.setStyleSheet("color: #00d2ff;")
        right_layout.addWidget(right_label)

        self.sources_list = QListWidget()
        self.sources_list.setFont(QFont("Segoe UI", 10))
        self.sources_list.setStyleSheet("""
            QListWidget {
                background-color: #151515;
                color: #fff;
                border: 1px solid #2a2a2a;
                border-radius: 8px;
            }
            QListWidget::item {
                padding: 8px;
                border-bottom: 1px solid #1f1f1f;
            }
            QListWidget::item:selected {
                background-color: #00d2ff;
                color: #000;
            }
        """)
        self.sources_list.itemClicked.connect(self.show_source_detail)
        right_layout.addWidget(self.sources_list)

        self.source_detail = QTextEdit()
        self.source_detail.setReadOnly(True)
        self.source_detail.setFont(QFont("Consolas", 10))
        self.source_detail.setStyleSheet("""
            QTextEdit {
                background-color: #151515;
                color: #ccc;
                border: 1px solid #2a2a2a;
                border-radius: 8px;
                padding: 10px;
            }
        """)
        self.source_detail.setPlaceholderText("Bir kaynağa tıkla, içeriği gör...")
        self.source_detail.setVisible(False)
        right_layout.addWidget(self.source_detail)

        self.splitter.addWidget(right_widget)
        self.splitter.setSizes([600, 500])

        main_layout.addWidget(self.splitter, 1)

        # DURUM ÇUBUĞU
        self.status_label = QLabel("✅ Hazır • Ctrl+Shift+F • Clipboard aktif")
        self.status_label.setFont(QFont("Segoe UI", 9))
        self.status_label.setStyleSheet("color: #666; padding: 5px;")
        main_layout.addWidget(self.status_label)

        self.current_results = None

        self.opacity_effect = QGraphicsOpacityEffect()
        self.ai_answer.setGraphicsEffect(self.opacity_effect)
        self.opacity_effect.setOpacity(1.0)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, 'splitter'):
            if self.width() < 900:
                self.splitter.setOrientation(Qt.Vertical)
                self.splitter.setSizes([400, 300])
            else:
                self.splitter.setOrientation(Qt.Horizontal)
                self.splitter.setSizes([600, 500])

    def fade_in(self):
        self.opacity_effect.setOpacity(0.0)
        anim = QPropertyAnimation(self.opacity_effect, b"opacity")
        anim.setDuration(400)
        anim.setStartValue(0.0)
        anim.setEndValue(1.0)
        anim.setEasingCurve(QEasingCurve.InOutQuad)
        anim.start()
        self._fade_anim = anim

    def start_thinking_animation(self):
        self._thinking_dots = 0
        self.ai_answer.setText("NEO düşünüyor")
        if not hasattr(self, '_thinking_timer'):
            self._thinking_timer = QTimer()
            self._thinking_timer.timeout.connect(self._update_thinking)
        self._thinking_timer.start(400)

    def _update_thinking(self):
        self._thinking_dots = (self._thinking_dots + 1) % 4
        dots = "." * self._thinking_dots
        self.ai_answer.setText(f"NEO düşünüyor{dots}")

    def stop_thinking_animation(self):
        if hasattr(self, '_thinking_timer'):
            self._thinking_timer.stop()

    def update_stats(self, question=False, file=False, snippet=False):
        if question:
            self.stats['questions'] += 1
        if file:
            self.stats['files_indexed'] += 1
        if snippet:
            self.stats['snippets_saved'] += 1
        self.stats_label.setText(
            f"📊 {self.stats['questions']} soru • {self.stats['files_indexed']} dosya • {self.stats['snippets_saved']} snippet"
        )

    def toggle_clear_button(self, text):
        """Yazı varsa çarpıyı göster, kutu boşsa gizle."""
        self.clear_btn.setVisible(len(text) > 0)

    def clear_search(self):
        """Arama kutusunu temizle ve imleci tekrar kutuya odakla."""
        self.search_input.clear()
        self.search_input.setFocus()

    def perform_search(self):
        query = self.search_input.text().strip()
        if not query:
            return

        if query.lower().startswith("mülakat:") or query.lower().startswith("mulkat:"):
            proje_adi = query.split(":", 1)[1].strip()
            self.run_mulakat(proje_adi)
            return

        if query.lower().startswith("özet:") or query.lower().startswith("ozet:"):
            proje_adi = query.split(":", 1)[1].strip()
            self.run_ozet(proje_adi)
            return

        if query.lower() in ["günlük özet", "gunluk ozet", "bugün ne yaptım", "bugun ne yaptim"]:
            self.run_daily_summary()
            return

        self.start_thinking_animation()
        self.sources_list.clear()
        self.source_detail.setVisible(False)
        self.search_btn.setEnabled(False)
        self.search_input.setEnabled(False)

        self.worker = SearchWorker(self.rag_engine, query)
        self.worker.finished.connect(self.on_search_finished)
        self.worker.start()

    def on_search_finished(self, cevap, results):
        self.stop_thinking_animation()
        self.search_btn.setEnabled(True)
        self.search_input.setEnabled(True)
        self.search_input.setFocus()
        self.update_stats(question=True)

        query = self.search_input.text().strip()
        query_keywords = extract_query_keywords(query)
        is_short_query = len(query_keywords) <= 2

        if is_short_query and results and results['documents'][0]:
            self.current_results = results
            documents = results['documents'][0]
            metadatas = results['metadatas'][0]

            preview_text = ""
            for i, (doc, meta) in enumerate(zip(documents[:3], metadatas[:3])):
                file_name = meta.get('file_name', 'unknown')
                preview_text += f"\n{'='*60}\n"
                preview_text += f"📄 {file_name}\n"
                preview_text += f"{'='*60}\n\n"
                preview_text += doc[:500].strip()
                if len(doc) > 500:
                    preview_text += "\n\n...(devamı var)"
                preview_text += "\n"

            self.ai_answer.setText(preview_text)
        else:
            self.ai_answer.setText(cevap)

        self.fade_in()

        if results and results['documents'][0]:
            self.current_results = results
            documents = results['documents'][0]
            metadatas = results['metadatas'][0]

            self.sources_list.clear()
            seen_files = set()

            for i, (doc, meta) in enumerate(zip(documents, metadatas)):
                file_name = meta.get('file_name', 'unknown')
                if file_name not in seen_files:
                    item_text = f"📄 {file_name}"
                    item = QListWidgetItem(item_text)
                    item.setData(Qt.UserRole, i)
                    item.setToolTip(meta.get('file_path', ''))
                    self.sources_list.addItem(item)
                    seen_files.add(file_name)

            self.status_label.setText(f"✅ {len(seen_files)} kaynak bulundu")
        else:
            self.current_results = None
            self.status_label.setText("❌ Kaynak bulunamadı")

    def show_source_detail(self, item):
        if not self.current_results:
            return

        index = item.data(Qt.UserRole)
        documents = self.current_results['documents'][0]
        metadatas = self.current_results['metadatas'][0]

        if index < len(documents):
            doc = documents[index]
            meta = metadatas[index]

            detail_text = f"📄 {meta.get('file_name', '')}\n"
            detail_text += f"📍 {meta.get('file_path', '')}\n\n"
            detail_text += "═" * 50 + "\n\n"
            detail_text += doc.strip()

            self.source_detail.setText(detail_text)
            self.source_detail.setVisible(True)

    def on_file_indexed(self, file_name):
        self.update_stats(file=True)
        self.status_label.setText(f"📡 Yeni dosya: {file_name}")

    def on_snippet_found(self, code_preview, source):
        print(f"🎯 SNIPPET BULUNDU: {source}")
        print(f" Tray icon var mı? {self.tray_icon is not None}")
        
        self.ai_answer.setText(f"🔔 **Kod Tekrarı Tespit Edildi!**\n\nBu kodu daha önce **'{source}'** dosyasında kullanmıştın!\n\nKod başlangıcı:\n```\n{code_preview}...\n```")
        self.fade_in()
        
        if self.tray_icon:
            try:
                self.tray_icon.showMessage(
                    "NEO - Kod Tekrarı",
                    f"Bu kodu '{source}' dosyasında kullanmıştın!",
                    QSystemTrayIcon.Information,
                    10000
                )
                print("✅ Tray bildirimi gönderildi")
            except Exception as e:
                print(f"❌ Tray bildirimi hatası: {e}")
        else:
            print("️ Tray icon yok!")

    def on_new_snippet_saved(self, code_preview):
        self.update_stats(snippet=True)
        self.status_label.setText(f"💾 Yeni snippet kaydedildi")

    def show_mulakat_dialog(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("Mülakat Modu")
        dialog.setMinimumSize(400, 150)

        layout = QVBoxLayout(dialog)

        label = QLabel("Hangi proje için mülakat cevabı hazırlayayım?")
        label.setFont(QFont("Segoe UI", 11))
        layout.addWidget(label)

        combo = QComboBox()
        combo.setFont(QFont("Segoe UI", 11))
        try:
            all_data = self.rag_engine.collection.get(include=['metadatas'])
            projects = set()
            for meta in all_data['metadatas']:
                name = meta.get('file_name', '')
                if 'stm32' in name.lower() or 'sensor' in name.lower():
                    projects.add('STM32 Sıcaklık Sensörü')
                elif 'cv' in name.lower() or 'ozet' in name.lower():
                    projects.add('CV ve Profil')
                elif 'neo' in name.lower():
                    projects.add('NEO Projesi')
                elif 'mercedes' in name.lower():
                    projects.add('Mercedes Demo')
            combo.addItems(sorted(projects) if projects else ['STM32', 'NEO', 'CV'])
        except:
            combo.addItems(['STM32', 'NEO', 'CV'])

        layout.addWidget(combo)

        btn_layout = QHBoxLayout()
        ok_btn = QPushButton("Hazırla")
        ok_btn.setStyleSheet("""
            QPushButton {
                background-color: #00d2ff;
                color: #000;
                border: none;
                border-radius: 6px;
                padding: 10px 20px;
                font-weight: bold;
            }
        """)
        ok_btn.clicked.connect(dialog.accept)
        btn_layout.addWidget(ok_btn)

        cancel_btn = QPushButton("İptal")
        cancel_btn.clicked.connect(dialog.reject)
        btn_layout.addWidget(cancel_btn)

        layout.addLayout(btn_layout)

        if dialog.exec() == QDialog.Accepted:
            proje_adi = combo.currentText()
            self.run_mulakat(proje_adi)

    def run_mulakat(self, proje_adi):
        self.start_thinking_animation()
        self.sources_list.clear()
        self.source_detail.setVisible(False)

        # Arama yap ve sonuçları sakla
        results = self.rag_engine.search(proje_adi, top_k=10)
        
        if results and results['documents'][0]:
            self.current_results = results
            documents = results['documents'][0]
            metadatas = results['metadatas'][0]

            # Kaynakları göster
            self.sources_list.clear()
            seen_files = set()
            for i, (doc, meta) in enumerate(zip(documents, metadatas)):
                file_name = meta.get('file_name', 'unknown')
                if file_name not in seen_files:
                    item_text = f"📄 {file_name}"
                    item = QListWidgetItem(item_text)
                    item.setData(Qt.UserRole, i)
                    item.setToolTip(meta.get('file_path', ''))
                    self.sources_list.addItem(item)
                    seen_files.add(file_name)

        cevap = self.rag_engine.mulakat_modu(proje_adi)

        self.stop_thinking_animation()
        self.ai_answer.setText(cevap)
        self.fade_in()
        self.status_label.setText(f"✅ Mülakat cevabı hazır: {proje_adi}")
        self.update_stats(question=True)

    def show_ozet_dialog(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("Proje Özeti")
        dialog.setMinimumSize(400, 150)

        layout = QVBoxLayout(dialog)

        label = QLabel("Hangi projenin özetini çıkarayım?")
        label.setFont(QFont("Segoe UI", 11))
        layout.addWidget(label)

        combo = QComboBox()
        combo.setFont(QFont("Segoe UI", 11))
        try:
            all_data = self.rag_engine.collection.get(include=['metadatas'])
            projects = set()
            for meta in all_data['metadatas']:
                name = meta.get('file_name', '')
                if 'stm32' in name.lower():
                    projects.add('STM32')
                elif 'neo' in name.lower():
                    projects.add('NEO')
                elif 'cv' in name.lower():
                    projects.add('CV')
                elif 'mercedes' in name.lower():
                    projects.add('Mercedes Demo')
            combo.addItems(sorted(projects) if projects else ['STM32', 'NEO', 'CV'])
        except:
            combo.addItems(['STM32', 'NEO', 'CV'])

        layout.addWidget(combo)

        btn_layout = QHBoxLayout()
        ok_btn = QPushButton("Özet Çıkar")
        ok_btn.setStyleSheet("""
            QPushButton {
                background-color: #00d2ff;
                color: #000;
                border: none;
                border-radius: 6px;
                padding: 10px 20px;
                font-weight: bold;
            }
        """)
        ok_btn.clicked.connect(dialog.accept)
        btn_layout.addWidget(ok_btn)

        cancel_btn = QPushButton("İptal")
        cancel_btn.clicked.connect(dialog.reject)
        btn_layout.addWidget(cancel_btn)

        layout.addLayout(btn_layout)

        if dialog.exec() == QDialog.Accepted:
            proje_adi = combo.currentText()
            self.run_ozet(proje_adi)

    def run_ozet(self, proje_adi):
        self.start_thinking_animation()
        self.sources_list.clear()
        self.source_detail.setVisible(False)

        # Arama yap ve sonuçları sakla
        results = self.rag_engine.search(proje_adi, top_k=10)
        
        if results and results['documents'][0]:
            self.current_results = results
            documents = results['documents'][0]
            metadatas = results['metadatas'][0]

            # Kaynakları göster
            self.sources_list.clear()
            seen_files = set()
            for i, (doc, meta) in enumerate(zip(documents, metadatas)):
                file_name = meta.get('file_name', 'unknown')
                if file_name not in seen_files:
                    item_text = f"📄 {file_name}"
                    item = QListWidgetItem(item_text)
                    item.setData(Qt.UserRole, i)
                    item.setToolTip(meta.get('file_path', ''))
                    self.sources_list.addItem(item)
                    seen_files.add(file_name)

        cevap = self.rag_engine.proje_ozeti(proje_adi)

        self.stop_thinking_animation()
        self.ai_answer.setText(cevap)
        self.fade_in()
        self.status_label.setText(f"✅ Proje özeti hazır: {proje_adi}")
        self.update_stats(question=True)

    def run_daily_summary(self):
        self.start_thinking_animation()
        self.sources_list.clear()
        self.source_detail.setVisible(False)

        summary = self.rag_engine.get_daily_summary()

        self.stop_thinking_animation()
        self.ai_answer.setText(summary)
        self.fade_in()
        self.status_label.setText("✅ Günlük özet hazır")
        self.update_stats(question=True)


# ==================== ANA UYGULAMA ====================
class NeoTrayApp:
    def __init__(self):
        self.app = QApplication(sys.argv)
        self.app.setQuitOnLastWindowClosed(False)
        self.app.setApplicationName("NEO")

        self.rag_engine = NeoRAGEngine()
        self.main_window = NeoMainWindow(self.rag_engine)

        self.file_watcher = FileWatcherThread(self.rag_engine, WATCH_DIRS)
        self.file_watcher.file_indexed.connect(self.main_window.on_file_indexed)
        self.file_watcher.start()
        print("📡 File Watcher aktif")

        self.clipboard_watcher = ClipboardWatcherThread(self.rag_engine)
        self.clipboard_watcher.snippet_found.connect(self.main_window.on_snippet_found)
        self.clipboard_watcher.new_snippet_saved.connect(self.main_window.on_new_snippet_saved)
        self.clipboard_watcher.start()
        print(" Clipboard Watcher aktif")

        self.setup_tray()
        self.setup_hotkey()
        self.setup_daily_summary()

    def setup_tray(self):
        pixmap = QPixmap(64, 64)
        pixmap.fill(Qt.transparent)
        painter = QPainter(pixmap)
        painter.setBrush(QColor("#00d2ff"))
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(8, 8, 48, 48)
        painter.end()

        icon = QIcon(pixmap)
        self.tray_icon = QSystemTrayIcon(icon, self.app)
        self.tray_icon.setToolTip("NEO")
        self.main_window.tray_icon = self.tray_icon

        menu = QMenu()
        show_action = QAction("Göster", menu)
        show_action.triggered.connect(self.show_main_window)
        menu.addAction(show_action)

        menu.addSeparator()

        quit_action = QAction("Çık", menu)
        quit_action.triggered.connect(self.quit_app)
        menu.addAction(quit_action)

        self.tray_icon.setContextMenu(menu)
        self.tray_icon.show()
        self.tray_icon.activated.connect(self.on_tray_activated)

    def setup_hotkey(self):
        self.hotkey_listener = keyboard.GlobalHotKeys({
            '<ctrl>+<shift>+f': self.toggle_main_window
        })
        self.hotkey_listener.start()
        print("✅ Hotkey: Ctrl+Shift+F")

    def setup_daily_summary(self):
        self.timer = QTimer()
        self.timer.timeout.connect(self.check_daily_summary)
        self.timer.start(60000)

    def check_daily_summary(self):
        now = datetime.now()
        if now.hour == 18 and now.minute == 0:
            stats = self.main_window.stats
            msg = (f"Bugün {stats['questions']} soru sordun, "
                   f"{stats['files_indexed']} dosya indekslendi, "
                   f"{stats['snippets_saved']} snippet kaydedildi.")
            self.tray_icon.showMessage("NEO - Günlük Özet", msg,
                                       QSystemTrayIcon.Information, 8000)

    def show_main_window(self):
        self.main_window.show()
        self.main_window.activateWindow()
        self.main_window.raise_()
        self.main_window.search_input.setFocus()

    def toggle_main_window(self):
        if self.main_window.isVisible():
            self.main_window.hide()
        else:
            self.show_main_window()

    def on_tray_activated(self, reason):
        if reason == QSystemTrayIcon.Trigger:
            self.toggle_main_window()

    def quit_app(self):
        self.file_watcher.stop()
        self.file_watcher.wait(3000)
        self.clipboard_watcher.stop()
        self.clipboard_watcher.wait(3000)
        self.app.quit()

    def run(self):
        print("🚀 NEO v6.1 Başlatıldı")
        print("💡 Ctrl+Shift+F ile aç/kapat")
        print("📋 Clipboard izleniyor")
        self.main_window.show()
        sys.exit(self.app.exec())


if __name__ == "__main__":
    app = NeoTrayApp()
    app.run()