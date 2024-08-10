from flask import Flask, jsonify, request, session, send_from_directory
from flask_cors import CORS
from langchain_openai.chat_models import ChatOpenAI
from langchain_openai.embeddings import OpenAIEmbeddings
from langchain_community.embeddings import OllamaEmbeddings
from langchain_community.chat_models import ChatOllama
from langchain_chroma import Chroma
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate

from flask_jwt_extended import create_access_token,get_jwt,get_jwt_identity, unset_jwt_cookies, jwt_required, JWTManager
from datetime import timedelta, datetime, timezone
from modal import db, File, DPIA, bcrypt, Template, Project, User, DPIA_File
from sqlalchemy.orm import sessionmaker
from helper import check_path, clear_chat_embed, partition_process, DPIAPDFGenerator, create_template, create_chatData
from crewai import Agent, Task, Crew, Process

import uuid, secrets, pdfplumber, math, psutil, GPUtil, fitz
from dotenv import load_dotenv, set_key
import os, glob, json, subprocess, logging, time
from werkzeug.utils import secure_filename
import threading, shutil
import pdfplumber
import pandas as pd
from rerank import rerank_response


class AjaxFilter(logging.Filter):
    def filter(self, record):  
        return "usage_metric" not in record.getMessage()

log = logging.getLogger('werkzeug')
log.addFilter(AjaxFilter())

#global variable
process_dpia = False

# disable telemetry from crewai
from crewai.telemetry import Telemetry

def noop(*args, **kwargs):
    print("Telemetry method call disabled!\n")
    pass

for attr in dir(Telemetry):
    if callable(getattr(Telemetry, attr)) and not attr.startswith("__"):
        setattr(Telemetry, attr, noop)


app = Flask(__name__)

cors = CORS(app, resources={r"/*": {"origins": "*"}})

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///info.db'

# Set up llm and embedding models
embeddings = OllamaEmbeddings(model="mxbai-embed-large")
parser = StrOutputParser()

db.init_app(app)
bcrypt.init_app(app)
# creates the database.
with app.app_context():
    db.create_all()

engine = db.create_engine('sqlite:///instance/info.db', echo=True)
# Create a session
Session = sessionmaker(bind=engine)
session = Session()

create_template(BASE_DIR, session) # create default templates

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# generate unique secret key as an environment variable
ENV_PATH = os.path.join(BASE_DIR, '.env')

def generate_secret_key():
    return secrets.token_urlsafe(24)

def load_or_generate_secret_key():
    secret_key = os.getenv('SECRET_KEY')
    if not secret_key:
        secret_key = generate_secret_key()
        set_key(ENV_PATH, 'SECRET_KEY', secret_key)
    return secret_key

app.config['SECRET_KEY'] = load_or_generate_secret_key()

# login jwt manager
# generate unique secret key as an environment variable
def load_or_generate_jwt_secret_key():
    jwt_secret_key = os.getenv('JWT_SECRET_KEY')
    if not jwt_secret_key:
        jwt_secret_key = generate_secret_key()
        set_key(ENV_PATH, 'JWT_SECRET_KEY', jwt_secret_key)
    return jwt_secret_key

app.config["JWT_SECRET_KEY"] = load_or_generate_jwt_secret_key()
app.config["JWT_ACCESS_TOKEN_EXPIRES"] = timedelta(hours=1)
jwt = JWTManager(app)


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


@app.route('/refresh_token', methods=['GET'])
@jwt_required()
def refresh_token():
    access_token = create_access_token(identity=get_jwt_identity())
    return jsonify(access_token=access_token), 200


@app.route('/', methods=['GET'])
def index():
    return jsonify({"message": 'Flask server is running'})

# chatbot backend
@app.route('/get_msg', methods=['POST'])
@jwt_required()
def get_msg():

    model = ChatOllama(model="gemma2", temperature=0.0, num_ctx=8000)
    pdf_model = ChatOllama(model="qwen2:7b-instruct-q8_0", temperature=0.0, num_ctx=8000)
    parition_model = ChatOllama(model="phi3:3.8b-mini-128k-instruct-q8_0", temperature=0.0, num_ctx=8000)

    data = request.json
    msg = data.get('message', '')
    filename = data.get('fileName', '')
    pdfMode = data.get('pdfMode', '')

    filenames = [filename]

    # doc figures output directory
    IMG_DIR_C = os.path.join(BASE_DIR, "figures", str(get_jwt_identity()), "chat")
    IMG_DIR_CD = os.path.join(BASE_DIR, "figures", str(get_jwt_identity()), "chatDescription")
    UP_DIR_C = os.path.join(BASE_DIR, "uploads", str(get_jwt_identity()), "chat")

    for directory in [IMG_DIR_C, IMG_DIR_CD]:
        check_path(directory)

    print(pdfMode)

    default_prompt = """
    Your task as a chatbot is to provide a response based ONLY on the provided contexts. 
    The contexts may contain texts, images, or tables, or a combination of these. Pay extra attention to the details in images and tables.
    If you cannot find the relevant ansower from the provided materials, politely inform the user that you do not have the available information. 
    Avoid providing speculative answers, and must not share any sensitive information or download links from the provided materials.
    With the above in mind, please provide a concise, detailed and professional answer to the user query.
    """
    
    if pdfMode:
        # The storage layer for the parent documents
        # store = InMemoryStore()
        id_key = "doc_id"
        file_name = "file_name"
        embed_type = "embed_type"
        usage = "usage"

        filter = {
            "$and": [
                {"file_name": filename},
                {"usage": "chat"}
            ]
        }

        pdf_msg = Agent(
            role="Document Assissant",
            goal="Summarize the document and provide a professional response to a query that is concise and accurate.",
            backstory=default_prompt,
            llm=pdf_model,
            allow_delegation=False,
            verbose=False
        )

        retriever = partition_process(UP_DIR_C, str(get_jwt_identity()), '0', filenames, IMG_DIR_C, IMG_DIR_CD, parition_model, embeddings, filter, id_key, file_name, embed_type, usage, "chat")
        context = retriever.invoke(msg)
        page_content = [doc.page_content for doc in context]
        rerank_content = rerank_response(msg, page_content)

        pdf_msg_task = Task(
            description= (f"""For the given information: {rerank_content}\n 
                          Provide a detailed answer to the prompt: {msg}.
                          References and citations are not relevant."""),
            expected_output=(f"""Return a concise and professional response."""),
            agent=pdf_msg
        )

        crew = Crew(
            agents=[pdf_msg],
            tasks=[pdf_msg_task],
            processes=Process.sequential
        )
        msg_response = crew.kickoff()
    else:
        default_msg = Agent(
            role="DPIA assistant",
            goal="Provide a light hearted and professional response to the user query.",
            backstory=default_prompt,
            llm=model,
            allow_delegation=False,
            verbose=False
        )

        context = create_chatData(BASE_DIR, embeddings, msg)
        page_content = [doc.page_content for doc in context]
        rerank_content = rerank_response(msg, page_content)

        msg_task = Task(
            description= (f"""Using the provided context: {rerank_content}, provide a light-hearted answer to the user's query: {msg}."""),
            expected_output=(f"""Return a concise and friendly response."""),
            agent=default_msg,
        )

        crew = Crew(
            agents=[default_msg],
            tasks=[msg_task],
            processes=Process.sequential
        )
        msg_response = crew.kickoff()
        
    return jsonify({"reply": msg_response.raw})


@app.route('/clear_chat', methods=['GET'])
@jwt_required()
def clear_chat():
    vectorstore = Chroma(collection_name=f"summary_{get_jwt_identity()}", embedding_function=embeddings, persist_directory=BASE_DIR + "/vectorDB/")
    clear_chat_embed(vectorstore, get_jwt_identity(), BASE_DIR)
    
    return jsonify({"message": 'Chat cleared'})


@app.route('/upload_doc', methods=['POST'])
@jwt_required()
def get_doc():

    files = request.files.getlist('File')
    mode = request.form.get('Mode')
    project_id = request.form.get('projectID')

    UP_DIR_C = os.path.join(BASE_DIR, "uploads", str(get_jwt_identity()), "chat")
    check_path(UP_DIR_C)

    if mode == "report":
        UP_DIR_R = os.path.join(BASE_DIR,  "uploads", str(get_jwt_identity()), project_id )
        for directory in [UP_DIR_C, UP_DIR_R]:
            check_path(directory)
    elif mode == "template":
        UP_DIR_T = os.path.join(BASE_DIR, "uploads", str(get_jwt_identity()), "template")
        check_path(UP_DIR_T)

    if not files or files[0].filename == '':
        return jsonify({"error": "No files selected"}), 400
    
    for file in files:  
        filename = secure_filename(file.filename)

        if mode == "report":
            file_path = os.path.join(UP_DIR_R, filename)
            save_path = os.path.join(UP_DIR_R)
        elif mode == "template":
            file_path = os.path.join(UP_DIR_T, filename)
            save_path = os.path.join(UP_DIR_T)
        else:
            file_path = os.path.join(UP_DIR_C, filename)
            save_path = os.path.join(UP_DIR_C)

        file.save(file_path)

        # Convert files to PDF if they are not PDF
        if not filename.lower().endswith('.pdf'):
            if filename.lower().endswith('.docx'):
                pdf_path = file_path.replace('.docx', '.pdf')
                subprocess.run(['libreoffice', '--headless', '--convert-to', 'pdf:writer_pdf_Export', file_path, '--outdir', save_path], check=True)
            elif filename.lower().endswith('.txt'):
                pdf_path = file_path.replace('.txt', '.pdf')
                subprocess.run(['libreoffice', '--headless', '--convert-to', 'pdf:writer_pdf_Export', file_path, '--outdir', save_path], check=True)
            else:
                return jsonify({"error": "Unsupported file type"}), 400

            # Save the converted PDF
            os.remove(file_path)
            file_path = pdf_path
            filename = os.path.basename(pdf_path)

    return jsonify({"message": "Embedding uploaded successfully", "filename": filename, "ragMode": True}), 200


@app.route('/toSQL', methods=['POST'])
@jwt_required()
def to_SQL():
    files = request.files.getlist('File')
    project_id = request.form.get('projectID')

    if not files or files[0].filename == '':
        return jsonify({"error": "No files selected"}), 400
    
    for file in files:
        filename = os.path.splitext(secure_filename(file.filename))[0]
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
    vectorstore = Chroma(collection_name=f"summary_{get_jwt_identity()}", embedding_function=embeddings, persist_directory=BASE_DIR + "/vectorDB/")

    for file_id in file_ids:
        document = File.query.get(file_id)
        if document:
            # Construct the file path
            file_path = os.path.join(BASE_DIR, 'uploads', str(get_jwt_identity()), str(document.projectID), document.fileName + ".pdf")
            data_path = os.path.join(BASE_DIR, 'vectorDB', 'parentData', str(get_jwt_identity()), str(document.projectID), document.fileName)
            DIR_P = os.path.join(BASE_DIR, "vectorDB", "parentData", str(get_jwt_identity()), str(document.projectID), document.fileName + ".pdf")

            existing_documents = vectorstore.get(where={
                "$and": [
                    {"file_name": document.fileName + ".pdf"},
                    {"usage": f"project_{document.projectID}"}
                ]
                })['ids']
            
            for ids in existing_documents:
                vectorstore.delete(ids)

            # Remove the file from the directory
            if os.path.exists(file_path):
                os.remove(file_path)

            for path in [data_path, DIR_P]:
                if os.path.exists(path) and os.path.isdir(path):
                    shutil.rmtree(path)

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
        return send_from_directory(DIR, document.fileName + ".pdf")
    return jsonify({'error': 'File not found'}), 404


@app.route('/get_templates', methods=['GET'])
@jwt_required()
def get_template():
    templates = Template.query.filter((Template.userID == 0) | (Template.userID == get_jwt_identity())).all()
    result = []
    for template in templates:
        result.append({
            'userID': template.userID,
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
    

@app.route('/extract_template', methods=['POST'])
@jwt_required()
def extract_template():
    file_name = request.form.get('Filename')
    filename = os.path.splitext(file_name)[0]
    pdf_path = os.path.join(BASE_DIR, "uploads", str(get_jwt_identity()), "template", file_name)
    temp_path = os.path.join(BASE_DIR, "uploads", str(get_jwt_identity()), "template")

    model = ChatOllama(model="qwen2:7b-instruct-q8_0", temperature=0.0, num_ctx=8000)

    def extract_text_from_pdf(pdf_path):
        text = ""
        with fitz.open(pdf_path) as doc:
            for page in doc:
                text += page.get_text()
        return text

    def extract_tables_from_pdf(pdf_path):
        tables = []
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                extracted_tables = page.extract_tables()
                for table in extracted_tables:
                    tables.append(pd.DataFrame(table))
        return tables
    
    exmaplar = {
    "Step 1 - Identify the Need for a DPIA": {
        "Project Overview": {
            "content": "Broadly summarise the project described in the documents you have been given.",
            "from": {"Step": "", "Section": ""}
        }
    }
    }
    
    initial_query = """
    Document template texts: {context}\n
    Document template tables: {context_more}\n
    Please process the information provided step by step.
    Answer the question: Is the document a DPIA template?
    Say "yes" or "no" ONLY.
    """
    template_query = """
    Document template texts: {context}\n
    Document template tables: {context_more}\n
    Please refer ONLY to the information provided. 
    With the above in mind, return a JSON format template that describes the information.
    The JSON format consists of a list of steps, each step contains one or multiple sections.
    Each section contains one key-value pair "content:" and empty "from:".
    It should follow the format of the following exmaple:
    {exmaplar}
    """
    follow_up_query = """
    For the provided JSON: {prev_answer}\n
    Please fill in any missing information from the template: {context}\n
    With the above in mind, rewrite an imrove JSON format template without [].
    The JSON format consists of a list of steps, each step contains one or multiple sections.
    For each section, "content:" should be filled with a prompt asking for information.
    It should follow the format of the following exmaple:
    {exmaplar}
    """
    
    text = extract_text_from_pdf(pdf_path)
    tables = extract_tables_from_pdf(pdf_path)
    parser = StrOutputParser()

    initial_prompt = ChatPromptTemplate.from_template(initial_query)
    initial_chain = initial_prompt | model | parser
    initial_prompt.format(context=text, context_more=tables)
    decider = initial_chain.invoke({"context": text, "context_more": tables})

    if decider.lower() == "no":
        if os.path.exists(temp_path) and os.path.isdir(temp_path):
            shutil.rmtree(temp_path)
        return jsonify({"message": "Input is not a DPIA template"}), 400

    template_prompt = ChatPromptTemplate.from_template(template_query)
    template_chain = template_prompt | model | parser
    template_prompt.format(context=text, context_more=tables, exmaplar=exmaplar)
    answer = template_chain.invoke({"context": text, "context_more": tables, "exmaplar": exmaplar})

    print(answer)

    follow_up_prompt = ChatPromptTemplate.from_template(follow_up_query)
    follow_up_chain = follow_up_prompt | model | parser
    follow_up_prompt.format(prev_answer=answer, context=text, exmaplar=exmaplar)
    final_answer = follow_up_chain.invoke({"prev_answer": answer, "context": text, "exmaplar": exmaplar})

    print(final_answer)

    final_answer = json.dumps(json.loads(final_answer), indent=4)

    new_template = Template(userID=get_jwt_identity(), tempName=filename + '_prototype', tempData=final_answer)
    db.session.add(new_template)
    db.session.commit()
    if os.path.exists(temp_path) and os.path.isdir(temp_path):
        shutil.rmtree(temp_path)
    
    return jsonify({"message": "Template extracted successfully"}), 200

    
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
            # Find all files and dpias associated with the project
            files = File.query.filter_by(projectID=project_id).all()
            dpias = DPIA.query.filter_by(projectID=project_id).all()
            dpia_files = DPIA_File.query.filter(DPIA_File.dpiaID.in_([dpia.dpiaID for dpia in dpias])).all()

            folder_path_file = os.path.join(BASE_DIR, 'uploads', str(get_jwt_identity()), str(project_id))
            folder_path_dpia = os.path.join(BASE_DIR, 'dpias', str(get_jwt_identity()), str(project_id))

            # Delete the files
            for file in files:
                # Construct the file path
                file_path = os.path.join(BASE_DIR, 'uploads', str(get_jwt_identity()), str(project_id), file.fileName)
                DIR_P = os.path.join(BASE_DIR, "vectorDB", "parentData", str(get_jwt_identity()), str(project_id), file.fileName)

                if os.path.exists(DIR_P) and os.path.isdir(DIR_P):
                    shutil.rmtree(DIR_P)

                try:
                    # Remove the folder from the directory
                    if os.path.exists(file_path):
                        os.remove(file_path)
                except Exception as e:
                    return jsonify({'error': str(e)}), 500
                
                # Delete the file record from the database
                db.session.delete(file)
            
            # Delete parentData
            data_path = os.path.join(BASE_DIR, 'vectorDB', 'parentData', str(get_jwt_identity()), str(project_id))
            if os.path.exists(data_path) and os.path.isdir(data_path):
                shutil.rmtree(data_path)
            
            # Delete the DPIAs
            for dpia in dpias:
                # Construct the dpia path
                dpia_path = os.path.join(BASE_DIR, 'dpias', str(get_jwt_identity()), str(project_id), dpia.title + ".pdf")

                try:
                    # Remove the dpia from the directory
                    if os.path.exists(dpia_path):
                        os.remove(dpia_path)
                except Exception as e:
                    return jsonify({'error': str(e)}), 500
                
                # Delete the dpia record from the database
                db.session.delete(dpia)
            
            # Delete the DPIA files
            for dpia_file in dpia_files:
                db.session.delete(dpia_file)
            
            # Delete the project record from the database
            shutil.rmtree(folder_path_file)
            shutil.rmtree(folder_path_dpia)
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
    dpia_list = [{'dpiaID': dpia.dpiaID, 'title': dpia.title, 'status': dpia.status} for dpia in dpias]

    return jsonify(dpia_list)


@app.route('/delete_dpias', methods=['POST'])
@jwt_required()
def delete_dpia():
    dpia_ids = request.get_json()

    for dpia_id in dpia_ids:
        dpia = DPIA.query.get(dpia_id)
        dpia_files = DPIA_File.query.filter_by(dpiaID=dpia_id).all()

        for dpia_file in dpia_files:
            db.session.delete(dpia_file)

        if dpia:
            # Construct the dpia path
            dpia_path = os.path.join(BASE_DIR, 'dpias', str(get_jwt_identity()), str(dpia.projectID), dpia.title + ".pdf")

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
    project_id = request.args.get('projectID')
    DIR = os.path.join(BASE_DIR, "dpias", str(get_jwt_identity()), project_id)
    document = DPIA.query.get(dpia_id)
    if document:
        return send_from_directory(DIR, document.title + ".pdf")
    return jsonify({'error': 'File not found'}), 404


@app.route('/init_dpia', methods=['POST'])
@jwt_required()
def init_dpia():

    global process_dpia 
    process_dpia = True

    data = request.get_json()
    project_id = data.get('projectID')
    title = data.get('title')
    file_names = data.get('fileName')

    # Get file_ids based on projectID and each file_name in file_names
    file_ids = []
    for file_name in file_names:
        file = File.query.filter_by(projectID=project_id, fileName=file_name).first()
        if file:
            file_ids.append(file.fileID)  # Assuming fileID is the primary key or unique identifier

    # Path to the text file
    file_path = os.path.join(BASE_DIR, 'template', str(get_jwt_identity()), 'select.txt')

    # Read the file content
    with open(file_path, 'r') as file:
        template = json.load(file)
    
    if template == {} or len(file_names) == 0:
        return jsonify({'error': 'No template or files selected'}), 400

    if not project_id or not title:
        return jsonify({'error': 'Invalid input'}), 400
    
    init_dpia = DPIA(projectID=project_id, title=title, status="working")
    db.session.add(init_dpia)
    db.session.commit()

    for file_id in file_ids:
        dpia_file = DPIA_File(dpiaID=init_dpia.dpiaID, fileID=file_id)
        db.session.add(dpia_file)
        db.session.commit()

    return jsonify({'success': True, 'dpiaID': init_dpia.dpiaID}), 200


@app.route('/dpia_download/<int:dpia_id>', methods=['GET'])
@jwt_required()
def dpia_download(dpia_id):
    project_id = request.args.get('projectID')
    document = DPIA.query.get(dpia_id)

    directory = os.path.join(BASE_DIR, 'dpias', str(get_jwt_identity()), project_id)
    filename = f"{document.title}.pdf"  
    return send_from_directory(directory, filename, as_attachment=True)


@app.route('/generate_dpia', methods=['POST'])
@jwt_required()
def generate_dpia():

    now = time.time()

    data = request.get_json()
    project_id = data.get('projectID')
    title = data.get('title')
    file_names = sorted(data.get('fileName'))
    dpia_id = data.get('dpiaID')

    # Create a DPIA report
    assign_model = ChatOllama(model="qwen2:7b-instruct-q8_0", temperature=0.0, num_ctx=8000)
    partition_model = ChatOllama(model="phi3:3.8b-mini-128k-instruct-q8_0", temperature=0.0, num_ctx=8000)
    general_model = ChatOllama(model="qwen2:7b-instruct-q8_0", temperature=0.0, num_ctx=8000)
    validate_model = ChatOllama(model="gemma2", temperature=0.0, num_ctx=8000)
    # general_model = ChatOpenAI(api_key=OPENAI_API_KEY, model="gpt-3.5-turbo", temperature=0.0)

    # doc figures output directory
    IMG_DIR_R = os.path.join(BASE_DIR, "figures", str(get_jwt_identity()), str(project_id))
    IMG_DIR_RD = os.path.join(BASE_DIR, "figures", str(get_jwt_identity()), str(project_id) + "_Description")
    UP_DIR_R = os.path.join(BASE_DIR, "uploads", str(get_jwt_identity()), str(project_id))

    # llm = ChatOpenAI(model="llama3.1", base_url="http://localhost:11434/v1", temperature=0.0, max_tokens=8000)
    llm = ChatOpenAI(api_key=OPENAI_API_KEY, model="gpt-4o-mini", temperature=0.0)

    for directory in [IMG_DIR_R, IMG_DIR_RD]:
        check_path(directory)

    id_key = "doc_id"
    file_name = "file_name"
    embed_type = "embed_type"
    usage = "usage"

    retriever = partition_process(UP_DIR_R, str(get_jwt_identity()), str(project_id), file_names, IMG_DIR_R, IMG_DIR_RD, partition_model, embeddings, 'n/a', id_key, file_name, embed_type, usage, f"project_{project_id}")

    # Path to the text file
    file_path = os.path.join(BASE_DIR, 'template', str(get_jwt_identity()), 'select.txt')

    # Read the file content
    with open(file_path, 'r') as file:
        template = json.load(file)
        
    assign_query = """Based on the provided context: {context}. Provide a 'Role', and a 'Backstory' with one sentence. Your response must be in key-value JSON format."""

    assign_prompt = ChatPromptTemplate.from_template(assign_query)
    parser = StrOutputParser()
    assign_chain = assign_prompt | assign_model | parser

    dpia_text = {}
    visited_keys = []
    visited_sections = []

    default_prompt = """
    You have contexts provided as knowledge to pull from, please refer to them as your ONLY knowledge source. 
    The contexts may contain texts, images, or tables, or a combination of these. Pay extra attention to the details in images and tables.
    Avoid speculations. Heavily favour knowledge provided in the contexts before falling back to baseline knowledge or other sources.
    Refrain from sharing sensitive data such as names, passwords, or download links.
    With the above in mind, please provide a detailed and professional response to the user query.
    """

    # Loop through each key-value pair in the data and store them in the dictionary
    for step_key, step_value in template.items():
        visited_keys.append(step_key)

        overview = f"{step_key}: {step_value}\n"
        assign_prompt.format(context=overview)
        assign_answer = assign_chain.invoke({"context": overview})
        print('DEBUG: ', assign_answer )
        assign_answer = json.loads(assign_answer)

        role = assign_answer.get("Role")
        backstory = assign_answer.get("Backstory")

        writing_agent = Agent(
            role=role,
            goal=default_prompt,
            backstory=backstory,
            llm=general_model,
            allow_delegation=False,
            verbose=True
        )
        
        validating_agent = Agent(
            role="Document Validator",
            goal=default_prompt,
            backstory="""A professional with experience in document validation and proofreading.""",
            llm=validate_model,
            allow_delegation=False,
            verbose=True
        )

        part_text = {}
        for part_key, part_value in step_value.items():
            visited_sections.append(part_key)
            prompt = part_value['content']
            from_step = part_value['from']['Step']
            from_section = part_value['from']['Section']

            context = retriever.invoke(prompt)
            page_content = [doc.page_content for doc in context]
            rerank_content = rerank_response(prompt, page_content)
            # rerank_content = page_content

            print(f"DEBUG: {rerank_content}")

            if not prompt.strip():
                part_text[f"""{part_key}"""] = ""
            else:
                if from_step in visited_keys and from_section in visited_sections:
                    prev_response = dpia_text[from_step][from_section]
                    
                    initial_answer = Task(
                        description= (f"""Using the given background information: {prev_response}\n 
                                      And the provided context: {rerank_content}\n
                                      Provide an answer to the prompt: {prompt}.
                                      References and citations are not relevant."""),
                        expected_output=(f"""Return an accurate and coherent response in a professional tone."""),
                        agent=writing_agent,
                    )
                else:
                    initial_answer = Task(
                        description= (f"""Using the provided context: {rerank_content}\n 
                                    Provide an answer to the prompt: {prompt}.
                                    References and citations are not relevant."""),
                        expected_output=(f"""Return an accurate and coherent response in a professional tone."""),
                        agent=writing_agent,
                    )

                validate_answer = Task(
                    description= (f"""Using the provided context: {rerank_content}\n
                                 Validate the answer against the prompt: {prompt}.
                                 Please fill in any missing information and provide an improve answer."""),
                    agent=validating_agent,
                    expected_output=(f"""Return a professional formatted text suitable for a document report."""),
                    context=[initial_answer]
                )

                crew = Crew(
                    agents=[writing_agent, validating_agent],
                    tasks=[initial_answer, validate_answer],
                    processes=Process.sequential
                )

                response = crew.kickoff()
                part_text[f"""{part_key}"""] = f"""{response}"""
        dpia_text[f"""{step_key}"""] = part_text
        
    dpia_json_text = json.dumps(dpia_text, indent=4)
    dpia = json.loads(dpia_json_text)

    # Saving DPIA PDF
    pdf_generator = DPIAPDFGenerator(BASE_DIR, get_jwt_identity(), project_id, title, dpia)
    pdf_generator.generate_pdf()

    end = time.time()
    print(f"Time taken: {(end - now)/60} minutes")

    global process_dpia
    process_dpia = False

    session.query(DPIA).\
    filter(DPIA.dpiaID == dpia_id).\
    update({'status': 'completed'})
    session.commit() 
    
    return jsonify({'success': True}), 200


@app.route('/usage_metric', methods=['GET'])
def usage_metric():

    # CPU usage
    cpu_usage = math.ceil(psutil.cpu_percent(interval=1))

    # Get virtual memory statistics
    memory = psutil.virtual_memory() 
    # Calculate total and used memory in MB
    total_ram = math.ceil(memory.total / (1024 ** 2))
    used_ram = math.ceil(memory.used / (1024 ** 2))

    # GPU usage
    gpus = GPUtil.getGPUs()
    if gpus:
        gpu = gpus[0]
        total_vram = gpu.memoryTotal  # Already in MB
        used_vram = gpu.memoryUsed  # Already in MB
        gpu_usage = math.ceil(gpu.load * 100)
    else:
        total_vram = 0
        used_vram = 0
        gpu_usage = 0

    # Shared VRAM usage (if applicable)
    used_shared_vram = math.ceil(memory.shared / (1024 ** 2)) if hasattr(memory, 'shared') else 0  # Convert to MB

    info = {
        'cpu': cpu_usage,
        'ram': used_ram,
        'gpu': gpu_usage,
        'vram': used_vram,
        'shared_vram': used_shared_vram,
        'total_ram': total_ram,
        'total_vram': total_vram,
    }

    format_info = {
        'cpu': f"{cpu_usage}%",
        'gpu': f"{gpu_usage}%",
        'ram': f"{used_ram}/{total_ram} MB",
        'vram': f"{used_vram}/{total_vram} MB",
        'shared_vram': f"{used_shared_vram} MB"
    }

    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    if process_dpia:
        # Write info to a text file
        with open(BASE_DIR + '/usage_metric.txt', 'a') as f:
            f.write(f'Timestamp: {timestamp}\n')
            for key, value in format_info.items():
                f.write(f'{key}: {value}\n')
            f.write('\n')  
    
    return jsonify(info), 200


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080, debug=True)