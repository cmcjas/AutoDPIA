import fitz
import textwrap
import os
from langchain.evaluation import load_evaluator
from langchain_community.embeddings import OllamaEmbeddings



embeddings = OllamaEmbeddings(model="mxbai-embed-large")


hf_evaluator = load_evaluator("embedding_distance", embeddings=embeddings)


def extract_text_by_chunks(pdf_path, chunk_size=4500):
    document = fitz.open(pdf_path)
    all_chunks = []

    # Iterate through each page
    for page_num in range(len(document)):
        page = document.load_page(page_num)
        text = page.get_text()

        # Split text into chunks
        chunks = textwrap.wrap(text, chunk_size)
        all_chunks.extend(chunks)

    return all_chunks

def compare_chunks(dpia_chunks, source_chunks):
    mismatches = []
    score = 100
    for i, dpia_chunk in enumerate(dpia_chunks):
        dpia_chunk = dpia_chunks[i]
        for i, source_chunk in enumerate(source_chunks):
            source_chunk = source_chunks[i]
            distance = hf_evaluator.evaluate_strings(prediction=dpia_chunk, reference=source_chunk)['score']

            if distance > 0.3 and distance < 0.4:
                score -= 0.1
                mismatches.append((i, dpia_chunk, source_chunk))
            elif distance > 0.4 and distance < 0.5:
                score -= 0.2
                mismatches.append((i, dpia_chunk, source_chunk))
            elif distance > 0.5 and distance < 0.6:
                score -= 0.3
                mismatches.append((i, dpia_chunk, source_chunk))
            elif distance > 0.6:
                score -= 0.5
                mismatches.append((i, dpia_chunk, source_chunk))

    return mismatches, score


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
pdf_path = os.path.join(BASE_DIR, 'dpias', '1', '1', 'qwen2.1.pdf')
source_path = os.path.join(BASE_DIR, 'uploads', '1', 'test')

dpia_chunks = extract_text_by_chunks(pdf_path)


all_source_chunks = []
i = 0  # Initialize i outside of the loop
for j, source_file in enumerate(os.listdir(source_path)):  # Using enumerate if you need j, otherwise remove it
    if source_file.endswith('.pdf'):
        path = os.path.join(source_path, source_file)
        source_chunks = extract_text_by_chunks(path)
        for source_chunk in source_chunks:
            all_source_chunks.append((i, source_chunk))  # Store i and the chunk together if needed
            i += 1  # Increment i for each chunk


# Compare each DPIA chunk with all source chunks
mismatches = compare_chunks(dpia_chunks, all_source_chunks)

print(mismatches[1])
for i, dpia_chunk, source_chunk in mismatches[0]:
    print(f"Mismatch in DPIA Chunk {i+1}:")
    print("-" * 80)

if not mismatches:
    print("All chunks from the DPIA report match with the source documents.")
else:
    print(f"Score: {mismatches[1]}")

  

        







    

