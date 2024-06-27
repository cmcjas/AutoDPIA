import os, uuid, glob
from unstructured.partition.pdf import partition_pdf
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
import ollama, shutil
from langchain_core.documents import Document
from pydantic import BaseModel
from typing import Any


def check_path(path):
    if not os.path.exists(path):
        os.makedirs(path)

def clear_chat_embed(vectorstore, BASE_DIR):

    existing_documents = vectorstore.get(where={"usage": "chat"})['ids']
    DIR_U = os.path.join(BASE_DIR, "uploads", "chat")
    DIR_F = os.path.join(BASE_DIR, "figures", "chat")
    DIR_FD = os.path.join(BASE_DIR, "figures", "description")

    if len(existing_documents) > 0:
        for ids in existing_documents:
            vectorstore.delete(ids)
    
    for directory_path in [DIR_U, DIR_F, DIR_FD]:
        if os.path.exists(directory_path) and os.path.isdir(directory_path):
            shutil.rmtree(directory_path)
            print(f"Removed directory: {directory_path}")
        else:
            print(f"Directory does not exist: {directory_path}")
    

class Element(BaseModel):
    type: str
    text: Any

def partition_process(UP_DIR_C, filename, IMG_DIR_C, IMG_DIR_CD, model, retriever, id_key, file_name, embed_type, usage):
        
        # initial prompt
        prompt_int = """You are an assistant tasked with summarizing tables and text. \
        Give a concise summary of the table or text. Table or text chunk: {element} """
        prompt = ChatPromptTemplate.from_template(prompt_int)

        # Get PDF elements
        pdf_elements = partition_pdf(
            filename=os.path.join(UP_DIR_C, filename),
            # Using pdf format to find embedded image blocks
            extract_images_in_pdf=True,
            # Use layout model (YOLOX) to get bounding boxes (for tables) and find titles
            # Titles are any sub-section of the document
            infer_table_structure=True,
            # Post processing to aggregate text once we have the title
            chunking_strategy="by_title",
            # Chunking params to aggregate text blocks
            # Attempt to create a new chunk 3800 chars
            # Attempt to keep chunks > 2000 chars
            # Hard max on chunks
            max_characters=4000,
            new_after_n_chars=3800,
            combine_text_under_n_chars=2000,
            extract_image_block_output_dir=IMG_DIR_C
        )

        # Create a dictionary to store counts of each type
        category_counts = {}

        for element in pdf_elements:
            category = str(type(element))
            if category in category_counts:
                category_counts[category] += 1
            else:
                category_counts[category] = 1

        # Unique_categories will have unique elements
        unique_categories = set(category_counts.keys())
        category_counts

        # Categorize by type
        categorized_elements = []
        for element in pdf_elements:
            if "unstructured.documents.elements.Table" in str(type(element)):
                categorized_elements.append(Element(type="table", text=str(element)))
            elif "unstructured.documents.elements.CompositeElement" in str(type(element)):
                categorized_elements.append(Element(type="text", text=str(element)))

        # Tables
        table_elements = [e for e in categorized_elements if e.type == "table"]
        print(len(table_elements))

        # Text
        text_elements = [e for e in categorized_elements if e.type == "text"]
        print(len(text_elements))

        chain = {"element": lambda x: x} | prompt | model | StrOutputParser()

        # Apply to text
        texts = [i.text for i in text_elements]
        text_summary = chain.batch(texts, {"max_concurrency": 5})
        # Apply to tables
        tables = [i.text for i in table_elements]
        table_summary = chain.batch(tables, {"max_concurrency": 5})

        # Loop through each image in the directory
        img_name = ""
        for img in os.listdir(IMG_DIR_C):
            if img.endswith(".jpg"):
                # Extract the base name of the image without extension
                img_name = os.path.splitext(img)[0]
        
            # Prepare the message to send to the LLaVA model
            message = {
                'role': 'user',
                'content': 'Describe the image in detail. Be specific about graphs, such as bar plots.',
                'images': [IMG_DIR_C + '/' + img_name + '.jpg']
            }

            # Use the ollama.chat function to send the image and retrieve the description
            description = ollama.chat(
                model="llava:13b",  
                messages=[message]
            )

            # Path to the text file to save the description
            text_file_path = os.path.join(IMG_DIR_CD, f"{img_name}.txt")
            # Write the description to the text file
            with open(text_file_path, 'w') as text_file:
                text_file.write(description['message']['content'])

        # Get all .txt file summaries
        file_paths = glob.glob(os.path.expanduser(os.path.join(IMG_DIR_CD, "*.txt")))

        # Read each file and store its content in a list
        img_summary = []
        for file_path in file_paths:
            with open(file_path, "r") as file:
                img_summary.append(file.read())

        # Add texts
        if texts:
            doc_ids = [str(uuid.uuid4()) for _ in texts]
            summary_texts = [
                Document(page_content=s, metadata={id_key: doc_ids[i], file_name: filename, embed_type: "text", usage: "chat"})
                for i, s in enumerate(text_summary)
            ]
            retriever.vectorstore.add_documents(summary_texts)
            retriever.docstore.mset(list(zip(doc_ids, texts)))

        # Add tables
        if tables:
            table_ids = [str(uuid.uuid4()) for _ in tables]
            summary_tables = [
                Document(page_content=s, metadata={id_key: table_ids[i], file_name: filename, embed_type: "table", usage: "chat"})
                for i, s in enumerate(table_summary)
            ]
            retriever.vectorstore.add_documents(summary_tables)
            retriever.docstore.mset(list(zip(table_ids, tables)))

        # Add image summaries
        if img_summary:
            img_ids = [str(uuid.uuid4()) for _ in img_summary]
            summary_img = [
                Document(page_content=s, metadata={id_key: img_ids[i], file_name: filename, embed_type: "image", usage: "chat"})
                for i, s in enumerate(img_summary)
            ]
            retriever.vectorstore.add_documents(summary_img)
            retriever.docstore.mset(list(zip(img_ids, img_summary)))

        return chain