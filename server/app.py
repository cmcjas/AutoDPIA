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

from flask_jwt_extended import create_access_token,get_jwt,get_jwt_identity, unset_jwt_cookies, jwt_required, JWTManager
from datetime import timedelta, datetime, timezone
from modal import db, File, DPIA, bcrypt, Template, Project, User
from sqlalchemy.orm import sessionmaker
from helper import check_path, clear_chat_embed, partition_process, chat_dict, llm_response

import uuid
from dotenv import load_dotenv
import os, glob, json
from werkzeug.utils import secure_filename
import threading, shutil


app = Flask(__name__)

cors = CORS(app, resources={r"/*": {"origins": "*"}})

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///info.db'

prepopulated_UK_format = ""
# Open the file and read its content
with open(BASE_DIR + '/template/test.txt', 'r') as file:
    prepopulated_UK_format = file.read()

# Set up llm and embedding models
 # model = ChatOpenAI(api_key=OPENAI_API_KEY, model="gpt-3.5-turbo", temperature=0.5)
model = Ollama(model="llama3", temperature=0.0, num_ctx=8000)
parser = StrOutputParser()
embeddings = OllamaEmbeddings(model="nomic-embed-text")

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
template_entry = Template(tempID=1, userID=0, tempName="test_format", tempData=prepopulated_UK_format)
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
# generate unique secret key as an environment variable
SECRET_KEY_FILE = 'secret_key.txt'

def generate_secret_key():
    return os.urandom(24)

def load_or_generate_secret_key():
    if os.path.exists(SECRET_KEY_FILE):
        with open(SECRET_KEY_FILE, 'rb') as f:
            secret_key = f.read()
    else:
        secret_key = generate_secret_key()
        with open(SECRET_KEY_FILE, 'wb') as f:
            f.write(secret_key)
    return secret_key

app.config['SECRET_KEY'] = load_or_generate_secret_key()

previousMessage = [] # store chat history
# store temporaries for subsequent messages
cache_retriever = []
cache_chat_chain = []

# login jwt manager
app.config['JWT_SECRET_KEY'] = '123'
app.config["JWT_ACCESS_TOKEN_EXPIRES"] = timedelta(hours=1)
jwt = JWTManager(app)


@app.after_request
def refresh_expiring_jwts(response):
    try:
        exp_timestamp = get_jwt()["exp"]
        now = datetime.now(timezone.utc)
        target_timestamp = datetime.timestamp(now + timedelta(minutes=30))
        if target_timestamp > exp_timestamp:
            access_token = create_access_token(identity=get_jwt_identity())
            data = response.get_json()
            if type(data) is dict:
                data["access_token"] = access_token 
                response.data = json.dumps(data)
        return response
    except (RuntimeError, KeyError):
        # Case where there is not a valid JWT. Just return the original respone
        return response


@app.route('/register', methods=['POST'])
def register():
    data = request.get_json()
    email = data['email']
    password = data['password']

    if User.query.filter_by(email=email).first():
        return jsonify({"msg": "User already exists"}), 409

    new_user = User(email=email)
    new_user.set_password(password)
    db.session.add(new_user)
    db.session.commit()

    return jsonify({"msg": "User registered successfully"}), 201


@app.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    email = data['email']
    password = data['password']

    user = User.query.filter_by(email=email).first()
    user.check_password(password)
    if not user or not user.check_password(password):
        return jsonify({"msg": "Invalid credentials"}), 401

    access_token = create_access_token(identity=user.userID)
    return jsonify(access_token=access_token), 200


@app.route('/logout', methods=['POST'])
def logout():
    response = jsonify({"msg": "logout successful"})
    unset_jwt_cookies(response)
    return jsonify({'message': 'Logged out successfully'}), 200

@app.route('/', methods=['GET'])
def index():
    return jsonify({"message": 'Flask server is running'})


# chatbot backend
@app.route('/get_msg', methods=['POST'])
@jwt_required()
def get_msg():

    # Initialise the vectorstore
    vectorstore = Chroma(collection_name=f"summary_{get_jwt_identity()}", embedding_function=embeddings, persist_directory=BASE_DIR + "/vectorDB/")

    data = request.json
    msg = data.get('message', '')
    filename = data.get('fileName', '')
    ragMode = data.get('ragMode', '')

    # doc figures output directory
    IMG_DIR_C = os.path.join(BASE_DIR, "figures", str(get_jwt_identity()), "chat")
    IMG_DIR_CD = os.path.join(BASE_DIR, "figures", str(get_jwt_identity()), "chatDescription")
    UP_DIR_C = os.path.join(BASE_DIR, "uploads", str(get_jwt_identity()), "chat")

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
    You are an expert at summarizing documents. Answer the user's question based only on the following context,
    If the answer is not in the context, reply politely that you do not have the available information.
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

        combined_filter = {
            "$and": [
                {"file_name": filename},
                {"usage": "chat"}
            ]
        }

        retriever = MultiVectorRetriever(
            vectorstore=vectorstore,
            docstore=store,
            id_key=id_key,
            file_name=file_name,
            embed_type=embed_type,
            usage=usage,
            search_kwargs={'k': 8, 'filter': combined_filter},
        )

        # skip partition process for subseqent messages after the first one
        existing_documents = vectorstore.get(where={"file_name": filename})['ids']

        if len(existing_documents) > 0:
            retriever = cache_retriever[-1]
            chat_chain = cache_chat_chain[-1]

            prompt = ChatPromptTemplate.from_template(template2)
            prompt.format(context=retriever, chat_history=previousMessage, input=msg)

            answer = llm_response(retriever, previousMessage, msg, chat_chain)

            previousMessage.append("user: " + msg + "\n" + "bot: " + answer + "\n")
            return jsonify({"reply": answer})

        # partition the document and process
        chat_chain = partition_process(UP_DIR_C, filename, IMG_DIR_C, IMG_DIR_CD, model, retriever, id_key, file_name, embed_type, usage, "chat")

        prompt = ChatPromptTemplate.from_template(template2)
        prompt.format(context=retriever, chat_history=previousMessage, input=msg)

        cache_retriever.append(retriever)
        cache_chat_chain.append(chat_chain)

        # chat_history = chat_dict(previousMessage)

        # chat_chain = (
        #     {"context": retriever, "chat_history": chat_history, "input": RunnablePassthrough()}
        #     | prompt | model | StrOutputParser()
        # )

        # answer = chat_chain.invoke(msg)
        answer = llm_response(retriever, previousMessage, msg, chat_chain)
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


@app.route('/clear_chat', methods=['GET'])
@jwt_required()
def clear_chat():
    previousMessage.clear()
    vectorstore = Chroma(collection_name=f"summary_{get_jwt_identity()}", embedding_function=embeddings, persist_directory=BASE_DIR + "/vectorDB/")
    clear_chat_embed(vectorstore, get_jwt_identity(), BASE_DIR)
    
    return jsonify({"message": 'Chat cleared'})


@app.route('/upload_doc', methods=['POST'])
@jwt_required()
def get_doc():

    vectorstore = Chroma(collection_name=f"summary_{get_jwt_identity()}", embedding_function=embeddings, persist_directory=BASE_DIR + "/vectorDB/")
    clear_chat_embed(vectorstore, get_jwt_identity(), BASE_DIR)

    files = request.files.getlist('File')
    mode = request.form.get('Mode')
    project_id = request.form.get('projectID')

    UP_DIR_C = os.path.join(BASE_DIR, "uploads", str(get_jwt_identity()), "chat")
    check_path(UP_DIR_C)

    if mode == "report":
        UP_DIR_R = os.path.join(BASE_DIR,  "uploads", str(get_jwt_identity()), project_id )
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
@jwt_required()
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
@jwt_required()
def get_documents():
    project_id = request.args.get('projectID')
    
    if project_id:
        documents = File.query.filter_by(projectID=int(project_id)).all()
    else:
        documents = []

    document_list = [{'fileID': doc.fileID, 'fileName': doc.fileName} for doc in documents]

    return jsonify(document_list)


@app.route('/delete_files', methods=['POST'])
@jwt_required()
def delete_document():
    file_ids = request.get_json()

    for file_id in file_ids:
        document = File.query.get(file_id)
        if document:
            # Construct the file path
            file_path = os.path.join(BASE_DIR, 'uploads', str(get_jwt_identity()), str(document.projectID), document.fileName)

            # Remove the file from the directory
            if os.path.exists(file_path):
                os.remove(file_path)

            db.session.delete(document)
            db.session.commit()
        else:
            return jsonify({'error': 'File not found'}), 404
    
    return jsonify({'success': True}), 200
    

@app.route('/view_files/<int:file_id>', methods=['GET'])
@jwt_required()
def view_document(file_id):
    project_id = request.args.get('projectID')
    DIR = os.path.join(BASE_DIR, "uploads", str(get_jwt_identity()), project_id)
    document = File.query.get(file_id)
    if document:
        return send_from_directory(DIR, document.fileName)
    return jsonify({'error': 'File not found'}), 404


@app.route('/get_templates', methods=['GET'])
@jwt_required()
def get_template():
    templates = Template.query.filter((Template.userID == 0) | (Template.userID == get_jwt_identity())).all()
    result = []
    for template in templates:
        result.append({
            'tempName': template.tempName,
            'tempData': template.tempData
        })
    return jsonify(result)


@app.route('/select_template', methods=['POST'])
@jwt_required()
def select_template():
    try:
        template_data = request.json
        template_data = json.dumps(template_data, indent=4)

        if not template_data:
            return jsonify({"error": "No data provided"}), 400
        
        # Define the file path
        user_dir = os.path.join(BASE_DIR, 'template', str(get_jwt_identity()))
        check_path(user_dir)

        # Write the data to select.txt
        with open(BASE_DIR + f'/template/{str(get_jwt_identity())}/select.txt', 'w') as file:
            file.write(template_data)
        
        return jsonify({"message": "Data saved successfully"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    
    
@app.route('/save_template', methods=['POST'])
@jwt_required()
def save_template():
    data = request.get_json()
    tempName = data.get('tempName')
    tempData = ""
    # Open the file and read its content
    with open(BASE_DIR + f'/template/{get_jwt_identity()}/select.txt', 'r') as file:
        tempData = file.read()

    if not tempName or not tempData:
        return jsonify({'error': 'Invalid input'}), 400
    
    new_template = Template(userID=get_jwt_identity(), tempName=tempName, tempData=tempData)
    db.session.add(new_template)
    db.session.commit()

    return jsonify({'success': True}), 200

@app.route('/delete_template', methods=['POST'])
@jwt_required()
def delete_template():
    template_name = request.get_json()
    template = Template.query.filter_by(userID=get_jwt_identity(), tempName=template_name).first()
    
    if template:
        db.session.delete(template)
        db.session.commit()
    else:
        return jsonify({'error': 'Template not found'}), 404

    return jsonify({'success': True}), 200

# DPIA section
@app.route('/create_project', methods=['POST'])
@jwt_required()
def create_project():
    data = request.get_json()
    title = data.get('title')
    description = data.get('description')

    if not title or not description:
        return jsonify({'error': 'Invalid input'}), 400
    
    new_project = Project(userID=get_jwt_identity(), title=title, description=description)
    db.session.add(new_project)
    db.session.commit()

    return jsonify({'success': True}), 200


@app.route('/get_projects', methods=['GET'])
@jwt_required()
def get_projects():
    projects = Project.query.filter_by(userID=get_jwt_identity()).all()
    project_list = [{'projectID': project.projectID, 'title': project.title, 'description': project.description} for project in projects]

    return jsonify(project_list)


@app.route('/delete_projects', methods=['POST'])
@jwt_required()
def delete_project():
    project_ids = request.get_json()

    for project_id in project_ids:
        project = Project.query.get(project_id)

        if project:
            # Find all files associated with the project
            files = File.query.filter_by(projectID=project_id).all()

            # Delete the files
            for file in files:
                # Construct the file path
                file_path = os.path.join(BASE_DIR, 'uploads', str(get_jwt_identity()), str(project_id), file.fileName)
                folder_path = os.path.join(BASE_DIR, 'uploads', str(get_jwt_identity()), str(project_id))

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


@app.route('/get_dpias', methods=['GET'])
@jwt_required()
def get_dpias():
    project_id = request.args.get('projectID')
    dpias = DPIA.query.filter_by(projectID=project_id).all()

    if not dpias:
        return jsonify([])
    dpia_list = [{'dpiaID': dpia.dpiaID, 'title': dpia.title} for dpia in dpias]

    return jsonify(dpia_list)


@app.route('/delete_dpias', methods=['POST'])
@jwt_required()
def delete_dpia():
    dpia_ids = request.get_json()

    for dpia_id in dpia_ids:
        dpia = DPIA.query.get(dpia_id)

        if dpia:
            # Construct the dpia path
            dpia_path = os.path.join(BASE_DIR, 'reports', str(get_jwt_identity()), str(dpia.projectID), dpia.title)

            # Remove the dpia from the directory
            if os.path.exists(dpia_path):
                os.remove(dpia_path)

            db.session.delete(dpia)
            db.session.commit()
        else:
            return jsonify({'error': 'DPIA not found'}), 404
    
    return jsonify({'success': True}), 200


@app.route('/view_dpias/<int:dpia_id>', methods=['GET'])
@jwt_required()
def view_dpia(dpia_id):
    dpia = DPIA.query.get(dpia_id)
    if dpia:
        return send_from_directory(os.path.join(BASE_DIR, 'reports', str(get_jwt_identity()), str(dpia.projectID)), dpia.title)
    return jsonify({'error': 'DPIA not found'}), 404


@app.route('/generate_dpia', methods=['POST'])
@jwt_required()
def generate_dpia():
    data = request.get_json()

    project_id = data.get('projectID')
    title = data.get('title')
    file_names = data.get('fileName')

    if not project_id or not title or len(file_names) == 0:
        return jsonify({'error': 'Invalid input'}), 400
    
    # # Create a DPIA report

    vectorstore = Chroma(collection_name=f"summary_{get_jwt_identity()}", embedding_function=embeddings, persist_directory=BASE_DIR + "/vectorDB/")

    # doc figures output directory
    IMG_DIR_R = os.path.join(BASE_DIR, "figures", str(get_jwt_identity()), str(project_id))
    IMG_DIR_RD = os.path.join(BASE_DIR, "figures", str(get_jwt_identity()), str(project_id) + "_Description")
    UP_DIR_R = os.path.join(BASE_DIR, "uploads", str(get_jwt_identity()), str(project_id))

    for directory in [IMG_DIR_R, IMG_DIR_RD]:
        check_path(directory)

    for filename in file_names:
                # The storage layer for the parent documents
        store = InMemoryStore()
        id_key = "doc_id"
        file_name = "file_name"
        embed_type = "embed_type"
        usage = "usage"

        combined_filter = {
            "$and": [
                {"file_name": filename},
                {"usage": "report"}
            ]
        }

        retriever = MultiVectorRetriever(
            vectorstore=vectorstore,
            docstore=store,
            id_key=id_key,
            file_name=file_name,
            embed_type=embed_type,
            usage=usage,
            search_kwargs={'k': 8, 'filter': combined_filter},
        )

        # partition the document and process
        dpia_chain = partition_process(UP_DIR_R, filename, IMG_DIR_R, IMG_DIR_RD, model, retriever, id_key, file_name, embed_type, usage, "report")

    return jsonify({'success': True}), 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080, debug=True)