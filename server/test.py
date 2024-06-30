from langchain_community.embeddings import OllamaEmbeddings
from langchain_community.vectorstores import Chroma
import os


BASE_DIR = os.path.dirname(os.path.abspath(__file__))

embeddings = OllamaEmbeddings(model="nomic-embed-text")

vectorstore = Chroma(collection_name="summary_1", embedding_function=embeddings, persist_directory=BASE_DIR + "/vectorDB/")

print(vectorstore.get())

