import os, uuid, glob
from unstructured.partition.pdf import partition_pdf
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
import ollama, shutil
from langchain_core.documents import Document
from pydantic import BaseModel
from typing import Any
from langchain_community.vectorstores import Chroma
from langchain.retrievers.multi_vector import MultiVectorRetriever

from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Table, TableStyle, Paragraph, SimpleDocTemplate, Spacer, Frame, PageTemplate
from modal import Template
from langchain_community.document_loaders import TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain.retrievers import ParentDocumentRetriever

from langchain.storage import LocalFileStore
from langchain.storage._lc_store import create_kv_docstore


def check_path(path):
    if not os.path.exists(path):
        os.makedirs(path)

def clear_chat_embed(vectorstore, user_id, BASE_DIR):

    existing_documents = vectorstore.get(where={"usage": "chat"})['ids']
    
    DIR_U = os.path.join(BASE_DIR, "uploads", str(user_id), "chat")
    DIR_F = os.path.join(BASE_DIR, "figures", str(user_id), "chat")
    DIR_FD = os.path.join(BASE_DIR, "figures", str(user_id), "chatDescription")
    DIR_P = os.path.join(BASE_DIR, "vectorDB", "parentData", str(user_id), "chat")

    if len(existing_documents) > 0:
        for ids in existing_documents:
            vectorstore.delete(ids)
    
    for directory_path in [DIR_U, DIR_F, DIR_FD, DIR_P]:
        if os.path.exists(directory_path) and os.path.isdir(directory_path):
            shutil.rmtree(directory_path)
            print(f"Removed directory: {directory_path}")
        else:
            print(f"Directory does not exist: {directory_path}")

def create_template(base_dir, session):
    prepopulated_format = ""
    # Open the file and read its content
    with open(base_dir + '/template/uk_gov.txt', 'r') as file:
        prepopulated_format = file.read()
    
    # Create a Template object
    template_entry = Template(tempID=1, userID=0, tempName="UK GOV (Default)", tempData=prepopulated_format)
    # Add the entry to the session and commit
    try:
        session.add(template_entry)
        session.commit()
    except:
        pass
    # Close the session
    session.close()

def create_chatData(BASE_DIR, embeddings, msg):
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    file_path = os.path.join(BASE_DIR, f"chatData", "data.txt")

    loaders = [
        TextLoader(file_path),
    ]
    docs = []
    for loader in loaders:
        docs.extend(loader.load())
    content = [Document(page_content=docs[0].page_content, metadata={"doc_id": "chatData"})]

    # This text splitter is used to create the parent documents
    parent_splitter = RecursiveCharacterTextSplitter(chunk_size=2000)
    # This text splitter is used to create the child documents
    # It should create documents smaller than the parent
    child_splitter = RecursiveCharacterTextSplitter(chunk_size=400)
    # The vectorstore to use to index the child chunks
    vectorstore = Chroma(
        collection_name="chatData", embedding_function=embeddings, persist_directory=BASE_DIR + "/chatData/"
    )
    existing_documents = vectorstore.get()['ids']

    # The storage layer for the parent documents
    # store = InMemoryStore()
    fs = LocalFileStore(BASE_DIR + "/chatData/" + "parentData")
    store = create_kv_docstore(fs)

    retriever = ParentDocumentRetriever(
        vectorstore=vectorstore,
        docstore=store,
        id_key="doc_id",
        child_splitter=child_splitter,
        parent_splitter=parent_splitter,
        search_kwargs={'k': 8}
    )
    if len(existing_documents) == 0:
        retriever.add_documents(content)
        retriever.docstore.mset(list(zip("chatData", content)))

    context = retriever.invoke(msg)
    page_content = [doc.page_content for doc in context]
    return page_content


def chat_dict(chatMessage):
    chat_history_dict = {}
    for i, message in enumerate(chatMessage):
        role, text = message.split(": ", 1)
        chat_history_dict[f"message_{i}"] = {"role": role, "text": text}
    return chat_history_dict
        
class Element(BaseModel):
    type: str
    text: Any

def partition_process(UP_DIR, user_id, project_id, filenames, IMG_DIR_C, IMG_DIR_CD, model, embeddings, filter, id_key, file_name, embed_type, usage, mode):
        
        BASE_DIR = os.path.dirname(os.path.abspath(__file__))
        # initial prompt
        prompt_int = """You are an assistant tasked with summarizing tables and text. \
        Give a concise summary of the table or text. Table or text chunk: {element} """
        prompt = ChatPromptTemplate.from_template(prompt_int)

        vectorstore = Chroma(collection_name=f"summary_{user_id}", embedding_function=embeddings, persist_directory=BASE_DIR + "/vectorDB/")

        print('TEST', filenames)
        doc_filter = [{'file_name': f} for f in filenames]  

        for filename in filenames:

            if mode == "chat":
                existing_documents = vectorstore.get(where={"usage": "chat"})['ids']
                fs = LocalFileStore(BASE_DIR + "/vectorDB/" + "parentData/" + user_id + '/chat/' + filename)
                # The storage layer for the parent documents
                store = create_kv_docstore(fs)

                retriever = MultiVectorRetriever(
                    vectorstore=vectorstore,
                    docstore=store,
                    id_key=id_key,
                    file_name=file_name,
                    embed_type=embed_type,
                    usage=usage,
                    search_kwargs={'k': 8, 'filter': filter},
                )
            else:
                existing_documents = vectorstore.get(where={
                    "$and": [
                        {"file_name": filename},
                        {"usage": f"project_{project_id}"}
                    ]
                    })['ids']
                fs = LocalFileStore(BASE_DIR + "/vectorDB/" + "/parentData/" + '/' + user_id + '/' + project_id + '/' + filename)
                # The storage layer for the parent documents
                store = create_kv_docstore(fs)

                retriever = MultiVectorRetriever(
                    vectorstore=vectorstore,
                    docstore=store,
                    id_key=id_key,
                    file_name=file_name,
                    embed_type=embed_type,
                    usage=usage,
                    search_kwargs={'k': 8, 'filter': {
                        "$and": [
                            {"$or": doc_filter },
                            {"usage": f"project_{project_id}"}
                        ]
                    }},
                )

            if len(existing_documents) == 0:

                # Get PDF elements
                pdf_elements = partition_pdf(
                filename=os.path.join(UP_DIR, filename),
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

                summary_chain = {"element": lambda x: x} | prompt | model | StrOutputParser()

                # Apply to text
                texts = [i.text for i in text_elements]
                text_summary = summary_chain.batch(texts, {"max_concurrency": 5})
                # Apply to tables
                tables = [i.text for i in table_elements]
                table_summary = summary_chain.batch(tables, {"max_concurrency": 5})

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
                        model="llava",  
                        messages=[message]
                    )

                    # Path to the text file to save the description
                    text_file_path = os.path.join(IMG_DIR_CD, f"{img_name}.txt")
                    check_path(IMG_DIR_CD)
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
                        Document(page_content=s, metadata={id_key: doc_ids[i], file_name: filename, embed_type: "text", usage: mode})
                        for i, s in enumerate(text_summary)
                    ]
                    texts = [Document(page_content=t, metadata={id_key: doc_ids, file_name: filename, embed_type: "text", usage: mode}) for t in texts]
                    retriever.vectorstore.add_documents(summary_texts)
                    retriever.docstore.mset(list(zip(doc_ids, texts)))

                # Add tables
                if tables:
                    table_ids = [str(uuid.uuid4()) for _ in tables]
                    summary_tables = [
                        Document(page_content=s, metadata={id_key: table_ids[i], file_name: filename, embed_type: "table", usage: mode})
                        for i, s in enumerate(table_summary)
                    ]
                    tables = [Document(page_content=t, metadata={id_key: table_ids, file_name: filename, embed_type: "table", usage: mode}) for t in tables]
                    retriever.vectorstore.add_documents(summary_tables)
                    retriever.docstore.mset(list(zip(table_ids, tables)))

                # Add image summaries
                if img_summary:
                    img_ids = [str(uuid.uuid4()) for _ in img_summary]
                    summary_img = [
                        Document(page_content=s, metadata={id_key: img_ids[i], file_name: filename, embed_type: "image", usage: mode})
                        for i, s in enumerate(img_summary)
                    ]
                    img_summary = [Document(page_content=i, metadata={id_key: img_ids, file_name: filename, embed_type: "image", usage: mode}) for i in img_summary]
                    retriever.vectorstore.add_documents(summary_img)
                    retriever.docstore.mset(list(zip(img_ids, img_summary)))

                for directory_path in [IMG_DIR_C, IMG_DIR_CD]:
                    if os.path.exists(directory_path) and os.path.isdir(directory_path):
                        shutil.rmtree(directory_path)
                        print(f"Removed directory: {directory_path}")
                    else:
                        print(f"Directory does not exist: {directory_path}")
        return retriever

# constructing a pdf from text
class DPIAPDFGenerator:
    def __init__(self, base_dir, jwt_identity, project_id, title, dpia):
        self.base_dir = base_dir
        self.jwt_identity = jwt_identity
        self.project_id = project_id
        self.title = title
        self.dpia = dpia
        self.pdf_path = os.path.join(self.base_dir, "dpias", str(self.jwt_identity), str(self.project_id))
        self.pdf_filename = f"{self.pdf_path}/{self.title}.pdf"
        self.width, self.height = A4

    def draw_table(self, story):
        data = []
        styles = getSampleStyleSheet()
        row_colors = []
        for i, (step, content) in enumerate(self.dpia.items()):
            data.append([Paragraph(f"<b>{step}</b>", styles['Normal']), ""])
            row_colors.append(colors.lightblue if i % 2 == 0 else colors.lightgrey)
            for sub_step, description in content.items():
                description = description.replace("\n", "<br/>")
                data.append([Paragraph(f"<b>{sub_step}</b>", styles['Normal']), Paragraph(description, styles['Normal'])])
                row_colors.append(None)  # No color for sub-steps

        table = Table(data, colWidths=[self.width * 0.2, self.width * 0.7], splitInRow=1)
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('LEFTPADDING', (0, 0), (-1, -1), 10),
            ('RIGHTPADDING', (0, 0), (-1, -1), 10),
            ('TOPPADDING', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
        ]))

        # Apply row colors
        for row_idx, color in enumerate(row_colors):
            if color:
                table.setStyle(TableStyle([
                    ('BACKGROUND', (0, row_idx), (-1, row_idx), color)
                ]))
        
        story.append(table)

    def generate_pdf(self):
        if not os.path.exists(self.pdf_path):
            os.makedirs(self.pdf_path)
        
        doc = SimpleDocTemplate(self.pdf_filename, pagesize=A4, topMargin=30, bottomMargin=30)
        story = []
        
        # Title
        styles = getSampleStyleSheet()
        title = Paragraph("Data Protection Impact Assessment (DPIA) Report", styles['Title'])
        story.append(title)
        story.append(Spacer(1, 10))
        
        # Draw the table
        self.draw_table(story)
        # Define a frame and template to manage content flow
        frame = Frame(doc.leftMargin, doc.bottomMargin, doc.width, doc.height - 2 * doc.bottomMargin, id='normal') # Adjust height for page number space
        template = PageTemplate(id='test', frames=frame, onPage=self.add_page_number)
        doc.addPageTemplates([template])

        # Build the PDF
        doc.build(story, onFirstPage=self.add_page_number, onLaterPages=self.add_page_number)

    def add_page_number(self, canvas, doc):
        page_num = canvas.getPageNumber()
        text = f"Page {page_num}"
        canvas.drawRightString(doc.pagesize[0] - 30, 15, text)  # Using doc.pagesize[0] to get the width of the page