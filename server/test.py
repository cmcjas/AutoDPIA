from langchain_community.vectorstores import Chroma
from langchain_community.embeddings import OllamaEmbeddings
import os


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
embeddings = OllamaEmbeddings(model="nomic-embed-text")

vectorstore = Chroma(collection_name="context", embedding_function=embeddings, persist_directory=BASE_DIR + "/vectorDB/")

existing_documents = vectorstore.get(where={"usage": "chat"})['ids']

print(existing_documents)