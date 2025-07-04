# utils/preprocess_pdfs.py
import os
import fitz  # PyMuPDF

PDF_DIR = '../rpg_books'
OUTPUT_FILE = '../rpg_books/compiled_rules.txt'

def extract_text_from_pdfs():
    """Extrai texto de todos os PDFs e compila em um único arquivo de texto."""
    if not os.path.exists(PDF_DIR):
        print(f"Diretório '{PDF_DIR}' não encontrado.")
        return

    all_text = []
    print("Iniciando extração de texto dos PDFs...")

    for filename in os.listdir(PDF_DIR):
        if filename.lower().endswith('.pdf'):
            filepath = os.path.join(PDF_DIR, filename)
            try:
                with fitz.open(filepath) as doc:
                    print(f"Processando '{filename}'...")
                    for page in doc:
                        all_text.append(page.get_text("text"))
            except Exception as e:
                print(f"Erro ao processar '{filename}': {e}")

    if not all_text:
        print("Nenhum texto foi extraído.")
        return

    print(f"\nEscrevendo texto compilado para '{OUTPUT_FILE}'...")
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        f.write("\n\n--- NEW PAGE ---\n\n".join(all_text))

    print("✅ Pré-processamento concluído com sucesso!")

if __name__ == '__main__':
    extract_text_from_pdfs()