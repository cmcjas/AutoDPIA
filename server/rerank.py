import os
from huggingface_hub import snapshot_download
from sentence_transformers import CrossEncoder


def rerank_response(query, documents):
    HUGGINGFACE_KEY = os.environ.get("HUGGINGFACE_KEY")

    model_id = "mixedbread-ai/mxbai-rerank-base-v1"
    snapshot_download(repo_id=model_id, token=HUGGINGFACE_KEY)

    # Load the model, here we use our base sized model
    model = CrossEncoder("mixedbread-ai/mxbai-rerank-base-v1")

    # Lets get the scores
    results = model.rank(query, documents, return_documents=True, top_k=10)
    format_results = [entry['text'] for entry in results]

    del model

    return format_results
    


