from flask import Flask, jsonify, request, session, send_from_directory
from flask_cors import CORS
from langchain_openai.chat_models import ChatOpenAI
from langchain_openai.embeddings import OpenAIEmbeddings
from langchain_community.embeddings import OllamaEmbeddings
from langchain_community.llms import Ollama
from langchain_community.document_loaders import PDFPlumberLoader, PyPDFLoader
from langchain_community.vectorstores import Chroma
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnablePassthrough

from unstructured.partition.pdf import partition_pdf
from typing import Any
from pydantic import BaseModel
import ollama
from langchain.retrievers.multi_vector import MultiVectorRetriever
from langchain.storage import InMemoryStore
from langchain_core.documents import Document

from modal import db, File, DPIA, bcrypt, Template, Project
from sqlalchemy.orm import sessionmaker
from helper import check_path, clear_chat_embed, partition_process

import uuid
from dotenv import load_dotenv
import os, glob, json
from werkzeug.utils import secure_filename
import threading, shutil


app = Flask(__name__)

CORS(app)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///info.db'

prepopulated_UK_format = ""
# Open the file and read its content
with open(BASE_DIR + '/template/test.txt', 'r') as file:
    prepopulated_UK_format = file.read()

# Set up llm and embedding models
 # model = ChatOpenAI(api_key=OPENAI_API_KEY, model="gpt-3.5-turbo", temperature=0.5)
model = Ollama(model="phi3:14b", temperature=0.0, num_ctx=8000)
parser = StrOutputParser()
embeddings = OllamaEmbeddings(model="nomic-embed-text")
# Initialise the vectorstore
vectorstore = Chroma(collection_name="context", embedding_function=embeddings, persist_directory=BASE_DIR + "/vectorDB/")
clear_chat_embed(vectorstore, BASE_DIR) # Clear the chat docs

db.init_app(app)
bcrypt.init_app(app)
# creates the database.
with app.app_context():
    db.create_all()

engine = db.create_engine('sqlite:///instance/info.db', echo=True)
# Create a session
Session = sessionmaker(bind=engine)
session = Session()

# Create a Template object
template_entry = Template(tempID=1, tempName="test_format", tempData=prepopulated_UK_format)
# Add the entry to the session and commit
try:
    session.add(template_entry)
    session.commit()
except:
    pass
# Close the session
session.close()


load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
app.secret_key = '123'

previousMessage = []

# store temporary chat chain and retriever
cache_retriever = []
cache_chat_chain = []


@app.route('/get_msg', methods=['POST'])
def get_msg():

    data = request.json
    msg = data.get('message', '')
    filename = data.get('fileName', '')
    ragMode = data.get('ragMode', '')

    # doc figures output directory
    IMG_DIR_C = os.path.join(BASE_DIR, "figures", "chat")
    IMG_DIR_CD = os.path.join(BASE_DIR, "figures", "description")
    UP_DIR_C = os.path.join(BASE_DIR, "uploads", "chat")

    for directory in [IMG_DIR_C, IMG_DIR_CD]:
        check_path(directory)

    print(filename)
    print(ragMode)
    print(previousMessage)

    template1 = """
    You are a comedian. You have witty replies to user questions and love telling jokes.

    Current conversation:
    {chat_history}

    user: {input}
    bot:
    """

    template2 = """
    You are an expert at summarizing documents. Answer the user's questions based only on the following context. 
    If the answer is not in the context, reply politely that you do not have that information available.
    ==============================
    Context: {context}
    ==============================
    Current conversation: 
    {chat_history}

    user: {input}
    bot:
    """


    if ragMode:

        # The storage layer for the parent documents
        store = InMemoryStore()
        id_key = "doc_id"
        file_name = "file_name"
        embed_type = "embed_type"
        usage = "usage"

        retriever = MultiVectorRetriever(
            vectorstore=vectorstore,
            docstore=store,
            id_key=id_key,
            file_name=file_name,
            embed_type=embed_type,
            usage=usage,
        )

        # skip partition process for subseqent messages after the first one
        existing_documents = vectorstore.get(where={"usage": "chat"})['ids']
        if len(existing_documents) > 0:
            prompt = ChatPromptTemplate.from_template(template2)
            prompt.format(context=retriever, chat_history=previousMessage, input=msg)

            print('test', cache_retriever)

            retriever = cache_retriever[-1]
            chat_chain = cache_chat_chain[-1]

            retriever = retriever.invoke(msg, k=8)
            answer = chat_chain.invoke(
                {
                    "context": retriever,
                    "chat_history": previousMessage,
                    "input": msg,
                }
            )
            previousMessage.append("user: " + msg + "\n" + "bot: " + answer + "\n")
            return jsonify({"reply": answer})
        
        # partition the document and process
        chat_chain = partition_process(UP_DIR_C, filename, IMG_DIR_C, IMG_DIR_CD, model, retriever, id_key, file_name, embed_type, usage)

        prompt = ChatPromptTemplate.from_template(template2)
        prompt.format(context=retriever, chat_history=previousMessage, input=msg)

        cache_retriever.append(retriever)
        cache_chat_chain.append(chat_chain)

        retriever = retriever.invoke(msg, k=8)
        answer = chat_chain.invoke(
            {
                "context": retriever,
                "chat_history": previousMessage,
                "input": msg,
            }
        )

        previousMessage.append("user: " + msg + "\n" + "bot: " + answer + "\n")
    else:
        prompt = ChatPromptTemplate.from_template(template1)

        chat_chain = prompt | model | parser

        prompt.format(chat_history=previousMessage, input=msg)

        answer = chat_chain.invoke(
            {"chat_history": previousMessage, "input": msg}
        )

        previousMessage.append("user: " + msg + "\n" + "bot: " + answer + "\n") 

    return jsonify({"reply": answer})


@app.route('/', methods=['GET'])
def index():
    return jsonify({"message": 'Flask server is running'})

@app.route('/clear_chat', methods=['POST'])
def clear_chat():
    previousMessage.clear()
    clear_chat_embed(vectorstore, BASE_DIR)
    
    return jsonify({"message": 'Chat cleared'})

@app.route('/upload_doc', methods=['POST'])
def get_doc():

    files = request.files.getlist('File')
    mode = request.form.get('Mode')
    project_id = request.form.get('projectID')

    UP_DIR_C = os.path.join(BASE_DIR, "uploads", "chat")

    if mode == "report":
        UP_DIR_R = os.path.join(BASE_DIR,  "uploads", project_id )
        for directory in [UP_DIR_C, UP_DIR_R]:
            check_path(directory)

    if not files or files[0].filename == '':
        return jsonify({"error": "No files selected"}), 400
    
    for file in files:  
        filename = secure_filename(file.filename)
        if mode == "report":
            file.save(os.path.join(UP_DIR_R, filename))
        else:
            file.save(os.path.join(UP_DIR_C, filename))

    return jsonify({"message": "Embedding uploaded successfully", "filename": filename, "ragMode": True}), 200

@app.route('/toSQL', methods=['POST'])
def to_SQL():
    files = request.files.getlist('File')
    project_id = request.form.get('projectID')

    if not files or files[0].filename == '':
        return jsonify({"error": "No files selected"}), 400
    
    for file in files:
        filename = secure_filename(file.filename)
        # Save the filename to the database
        new_document = File(fileName=filename, projectID=int(project_id))
        db.session.add(new_document)
        db.session.commit()

    return jsonify({'success': True, 'filename': filename}), 201

@app.route('/get_files', methods=['GET'])
def get_documents():
    project_id = request.args.get('projectID')
    
    if project_id:
        documents = File.query.filter_by(projectID=int(project_id)).all()
    else:
        documents = []

    document_list = [{'fileID': doc.fileID, 'fileName': doc.fileName} for doc in documents]

    return jsonify(document_list)


@app.route('/delete_files', methods=['POST'])
def delete_document():
    data = request.get_json()
    file_ids = data.get('selectedDocs', [])

    for file_id in file_ids:
        document = File.query.get(file_id)
        if document:
            # Construct the file path
            file_path = os.path.join(BASE_DIR, 'uploads', str(document.projectID), document.fileName)

            # Remove the file from the directory
            if os.path.exists(file_path):
                os.remove(file_path)

            db.session.delete(document)
            db.session.commit()
        else:
            return jsonify({'error': 'File not found'}), 404
    
    return jsonify({'success': True}), 200
    

@app.route('/view_files/<int:file_id>', methods=['GET'])
def view_document(file_id):
    project_id = request.args.get('projectID')
    DIR = os.path.join(BASE_DIR, "uploads", project_id)
    document = File.query.get(file_id)
    if document:
        return send_from_directory(DIR, document.fileName)
    return jsonify({'error': 'File not found'}), 404

@app.route('/get_templates', methods=['GET'])
def get_template():
    templates = Template.query.all()
    result = []
    for template in templates:
        result.append({
            'tempName': template.tempName,
            'tempData': template.tempData
        })
    return jsonify(result)

@app.route('/select_template', methods=['POST'])
def select_template():
    try:
        template_data = request.json
        template_data = json.dumps(template_data, indent=4)

        if not template_data:
            return jsonify({"error": "No data provided"}), 400
        
        # Write the data to select.txt
        with open(BASE_DIR + '/template/select.txt', 'w') as file:
            file.write(template_data)
        
        return jsonify({"message": "Data saved successfully"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    
@app.route('/save_template', methods=['POST'])
def save_template():
    data = request.get_json()
    tempName = data.get('tempName')
    tempData = ""
    # Open the file and read its content
    with open(BASE_DIR + '/template/select.txt', 'r') as file:
        tempData = file.read()

    if not tempName or not tempData:
        return jsonify({'error': 'Invalid input'}), 400
    
    new_template = Template(tempName=tempName, tempData=tempData)
    db.session.add(new_template)
    db.session.commit()

    return jsonify({'success': True}), 200


@app.route('/create_project', methods=['POST'])
def create_project():
    data = request.get_json()
    title = data.get('title')
    description = data.get('description')

    if not title or not description:
        return jsonify({'error': 'Invalid input'}), 400
    
    new_project = Project(title=title, description=description)
    db.session.add(new_project)
    db.session.commit()

    return jsonify({'success': True}), 200


@app.route('/get_projects', methods=['GET'])
def get_projects():
    projects = Project.query.all()
    project_list = [{'projectID': project.projectID, 'title': project.title, 'description': project.description} for project in projects]

    return jsonify(project_list)

@app.route('/delete_projects', methods=['POST'])
def delete_project():
    data = request.get_json()
    project_ids = data.get('selectedPrjs', [])

    for project_id in project_ids:
        project = Project.query.get(project_id)

        if project:
            # Find all files associated with the project
            files = File.query.filter_by(projectID=project_id).all()

            # Delete the files
            for file in files:
                # Construct the file path
                file_path = os.path.join(BASE_DIR, 'uploads', str(project_id), file.fileName)
                folder_path = os.path.join(BASE_DIR, 'uploads', str(project_id))

                try:
                    # Remove the folder from the directory
                    if os.path.exists(file_path):
                        os.remove(file_path)
                except Exception as e:
                    return jsonify({'error': str(e)}), 500
                
                # Delete the file record from the database
                db.session.delete(file)
            
            # Delete the project record from the database
            shutil.rmtree(folder_path)
            db.session.delete(project)
            db.session.commit()
        else:
            return jsonify({'error': 'Project not found'}), 404
    
    return jsonify({'success': True}), 200


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080, debug=True)