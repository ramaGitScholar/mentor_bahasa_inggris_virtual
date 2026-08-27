import src.core.env as env

# path dari pathlib memungkinkan kita untuk menyambung path dengan operator slash (/)
from pathlib import Path
from functools import lru_cache
from supabase import Client, create_client

# tidak dikasih maxsize supaya ketika namanya berubah misal ada 2 file yang ingin diload, agent-lead, dengan agent-listeing, masing-masing memiliki cache
@lru_cache
def load_instruction(name: str):
    """Baca file instruksi berdasarkan nama file, contoh: load_instruction('agent-lead')"""
    
    # contoh penyambungan dir dengan operator slash
    path = env.INSTRUCTIONS_DIR / f"{name}.md" # src/agents/instructions/agent-lead.md
    
    if not path.exists():
        raise FileNotFoundError(
            f"File instruksi tidak ditemukan: {path}. \n"
            f"Cek nama file di {env.INSTRUCTIONS_DIR}"
        )
    
    return path.read_text(encoding="utf-8")