from flask import Flask, jsonify, request, send_from_directory
from flask import session as flask_session
from flask_cors import CORS
from langchain_openai.chat_models import ChatOpenAI
from langchain_community.embeddings import OllamaEmbeddings
from langchain_community.chat_models import ChatOllama
from langchain_chroma import Chroma
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate

from flask_jwt_extended import create_access_token,get_jwt,get_jwt_identity, unset_jwt_cookies, jwt_required, JWTManager
from datetime import timedelta, datetime
from modal import db, File, DPIA, bcrypt, Template, Project, User, DPIA_File
from sqlalchemy.orm import sessionmaker
from helper import check_path, clear_chat_embed, partition_process, DPIAPDFGenerator, create_template, create_chatData, split_text_into_chunks, expanded_response
from celery import Celery
from celery.result import AsyncResult
from crewai import Agent, Task, Crew, Process

import secrets, pdfplumber, math, psutil, GPUtil, fitz
from dotenv import load_dotenv, set_key
import os, json, subprocess, logging, time
from werkzeug.utils import secure_filename
import shutil
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
tempID = 0
default_prompt = """
Please think step by step.
You have contexts provided as knowledge to pull from, please refer to them as your ONLY knowledge source. 
The contexts may contain texts, images, or tables, or a combination of these. Pay extra attention to the details in images and tables.
Avoid speculations. Heavily favour knowledge provided in the contexts before falling back to baseline knowledge or other sources.
Refrain from sharing sensitive data such as names, passwords, or download links.
With the above in mind, please provide a detailed and professional response to the user query.
"""

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

# Set up embedding models
embeddings = OllamaEmbeddings(model="nomic-embed-text")
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

for fileName in ['UK ICO (Default).txt', 'Test1.txt']:
    create_template(BASE_DIR, session, fileName) # create default templates

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

# Configure Celery
app.config['CELERY_BROKER_URL'] = 'redis://localhost:6379/0'
app.config['CELERY_RESULT_BACKEND'] = 'redis://localhost:6379/0'
celery = Celery(app.name, broker=app.config['CELERY_BROKER_URL'])
celery.conf.update(app.config)


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


@app.route('/refresh_token', methods=['POST'])
def refresh_token():
    data = request.get_json()
    email = data['email']
    print("email:", email)
    user = User.query.filter_by(email=email).first()
    access_token = create_access_token(identity=user.userID)
    return jsonify(access_token=access_token), 200


@app.route('/', methods=['GET'])
def index():
    return jsonify({"message": 'Flask server is running'})


@app.route('/refresh_page', methods=['POST'])
def refresh_page():
    data = request.get_json()
    email = data['email']
    user = User.query.filter_by(email=email).first()

    inspector = celery.control.inspect()
    # Get all active tasks
    active_tasks = inspector.active()
    if active_tasks:
        for worker, tasks in active_tasks.items():
            for task in tasks:
                celery.control.revoke(task['id'], terminate=True)

    # Get all reserved tasks (waiting to be executed)
    reserved_tasks = inspector.reserved()
    if reserved_tasks:
        for worker, tasks in reserved_tasks.items():
            for task in tasks:
                celery.control.revoke(task['id'], terminate=True)

    vectorstore = Chroma(collection_name=f"summary_{user.userID}", embedding_function=embeddings, persist_directory=BASE_DIR + "/vectorDB/")
    clear_chat_embed(vectorstore, user.userID, BASE_DIR)

    return "Refresh operations success", 200


@app.route('/start_task', methods=['POST'])
@jwt_required()
def start_task():
    data = request.json
    user_id = str(get_jwt_identity())
    data['user_id'] = user_id
    task_name = data.get('taskName', '')

    if task_name == 'get_msg':
        task = get_msg.apply_async(args=[data])
    if task_name == 'generate_dpia':
        # Path to the text file
        file_path = os.path.join(BASE_DIR, 'template', str(get_jwt_identity()), 'select.txt')
        # Read the file content
        with open(file_path, 'r') as file:
            template = json.load(file)

        data['template'] = template
        task = generate_dpia.apply_async(args=[data])
    if task_name == 'extract_template':
        task = extract_template.apply_async(args=[data])

    return jsonify({'task_id': task.id}), 202


@app.route('/get_task_result', methods=['GET'])
@jwt_required()
def get_task_result():
    task_id = request.args.get('taskID')
    task_name = request.args.get('taskName')

    if task_name == 'get_msg':
        task = get_msg.AsyncResult(task_id)
    if task_name == 'generate_dpia':
        task = generate_dpia.AsyncResult(task_id)
    if task_name == 'extract_template':
        task = extract_template.AsyncResult(task_id)
   # Poll for task status until it's no longer 'PENDING'
    while task.status == 'PENDING':
        time.sleep(1)  # Wait for 1 second before checking again

    # Return the task status and result
    if task.status == 'SUCCESS':
        response = {
            'state': task.state,
            'result': task.result
        }
    if task.status == 'REVOKED':
        response = {
            'state': task.state,
            'status': 'task cancelled'
        }

    if task.status == 'FAILURE':
        response = {
            'state': task.state,
            'status': str(task.info),  # Exception info if task failed
        }
    return jsonify(response), 200

@app.route('/cancel_task', methods=['POST'])
@jwt_required()
def cancel_task():
    task_id = request.json['taskID']
    print('task_id:', task_id)  
    celery.control.revoke(task_id, terminate=True)
    return jsonify({'status': 'task cancelled'}), 200


@celery.task(bind=True)
def get_msg(self, data):
    # data = request.json
    with app.app_context():

        model = ChatOllama(model="gemma2", temperature=0.0, num_ctx=8000)
        parition_model = ChatOllama(model="phi3:3.8b-mini-128k-instruct-q8_0", temperature=0.0, num_ctx=8000)
        user_id = data.get('user_id', '')
        sequential_response = ''

        msg = data.get('message', '') # Get the user message
        filename = data.get('fileName', '') # Get the filename
        pdfMode = data.get('pdfMode', '') # Get the pdfMode
        filenames = [filename] # Get the filenames

        IMG_DIR_C = os.path.join(BASE_DIR, "figures", data.get('user_id', ''), "chat")
        IMG_DIR_CD = os.path.join(BASE_DIR, "figures", data.get('user_id', ''), "chatDescription")
        UP_DIR_C = os.path.join(BASE_DIR, "uploads", data.get('user_id', ''), "chat")

        for directory in [IMG_DIR_C, IMG_DIR_CD]:
            check_path(directory)

        format_chat = Agent(
            role="Chat Assistant",
            goal="Formatting the information provided by the user into a light-hearted response.",
            backstory="Expert in analyzing and proofreading user responses.",
            llm=model,
            allow_delegation=False,
        )

        print(pdfMode)

        if pdfMode:
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
                role="Document Analyst",
                goal="Summarizing and analyzing documents to provide professional responses to user queries.",
                backstory=default_prompt,
                llm=model,
                allow_delegation=False,
                verbose=False
            )
            # Process the document
            retriever = partition_process(UP_DIR_C, user_id, '0', filenames, IMG_DIR_C, IMG_DIR_CD, parition_model, embeddings, filter, id_key, file_name, embed_type, usage, "chat")
            context = retriever.invoke(msg)
            page_content = [doc.page_content for doc in context]
            rerank_content = rerank_response(msg, page_content)
            # Split the content into chunks, multi-chain
            split_content = split_text_into_chunks(''.join(rerank_content))
            for content in enumerate(split_content):      
                pdf_answer = Task(
                    description= (f"""Based on the provided document inforamtion: {sequential_response}\n {content}\n
                                Please provide a friendly professional response to the user query: {msg}"""),
                    expected_output=(f"""Return a concise and accurate response."""),
                    agent=pdf_msg
                )
                crew = Crew(
                    agents=[pdf_msg],
                    tasks=[pdf_answer],
                    processes=Process.sequential
                )
                sequential_response = crew.kickoff().raw
            
            crew = expanded_response(pdf_answer, rerank_content, msg, pdf_msg, format_chat)
            msg_response = crew.kickoff()
        else:
            default_msg = Agent(
                role="DPIA assistant",
                goal="Provide a professional response based on user query.",
                backstory=default_prompt,
                llm=model,
                allow_delegation=False,
                verbose=False
            )
            
            context = create_chatData(BASE_DIR, embeddings, msg) # create knowledge base
            page_content = [doc.page_content for doc in context]
            rerank_content = rerank_response(msg, page_content)
            # Split the content into chunks, multi-chain
            split_content = split_text_into_chunks(''.join(rerank_content))
            for content in enumerate(split_content): 
                msg_answer = Task(
                    description= (f"""Based on the provided inforamtion: {sequential_response}\n {content}\n
                                Please provide a friendly professional response to the user query: {msg}"""),
                    expected_output=(f"""Return a concise and accurate response."""),
                    agent=default_msg,
                )

                crew = Crew(
                    agents=[default_msg],
                    tasks=[msg_answer],
                    processes=Process.sequential
                )
                sequential_response = crew.kickoff().raw

            crew = expanded_response(msg_answer, rerank_content, msg, default_msg, format_chat)
            msg_response = crew.kickoff()
        
        for i in range(10):
            if self.request.called_directly:  # Check if the task is being revoked
                break
            time.sleep(1)  # Simulate a long process
        return msg_response.raw
            

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
        filename_root, _ = os.path.splitext(filename)

        existing_file = File.query.filter_by(fileName=filename_root, projectID=project_id).first()
        if existing_file:
            return jsonify({"error": f"File with name '{filename}' already exists for this project"}), 400

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

    return jsonify({"message": "File uploaded successfully", "filename": filename, "ragMode": True}), 200


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
    try:
        for template in templates:
            result.append({
                'userID': template.userID,
                'tempName': template.tempName,
                'tempData': template.tempData
            })
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/select_template', methods=['POST'])
@jwt_required()
def select_template():
    global tempID
    try:
        data = request.json
        template_data = data.get('tempData', '')
        template_name = data.get('tempName', '')
        template_data = json.dumps(template_data, indent=4)

        result = Template.query.filter_by(userID=get_jwt_identity(), tempName=template_name).first()
        if result is None:
            result = Template.query.filter_by(userID=0, tempName=template_name).first()

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
        tempID = ''
        return jsonify({"error": str(e)}), 500
    

@celery.task(bind=True)
def extract_template(self, data):

    with app.app_context(): # Create a new context for the task
        file_name = data.get('fileName', '') # Get the filename
        filename = os.path.splitext(file_name)[0] # Get the filename without the extension
        pdf_path = os.path.join(BASE_DIR, "uploads", data.get('user_id', ''), "template", file_name)
        temp_path = os.path.join(BASE_DIR, "uploads", data.get('user_id', ''), "template")
        
        model = ChatOllama(model="qwen2:7b-instruct-q8_0", temperature=0.0, num_ctx=8000)

        def extract_text_from_pdf(pdf_path): # Extract text from PDF
            text = ""
            with fitz.open(pdf_path) as doc:
                for page in doc:
                    text += page.get_text()
            return text

        def extract_tables_from_pdf(pdf_path): # Extract tables from PDF
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
        It MUST follow the format of the following exmaple:
        {exmaplar}
        """
        follow_up_query = """
        For the provided JSON: {prev_answer}\n
        Please fill in any missing information from the template: {context}\n
        With the above in mind, rewrite an imrove JSON format template without [].
        The JSON format consists of a list of steps, each step contains one or multiple sections.
        Each section contains one key-value pair "content:" and empty "from:".
        It MUST follow the format of the following exmaple:
        {exmaplar}
        """
        
        text = extract_text_from_pdf(pdf_path) # Extract text from PDF
        tables = extract_tables_from_pdf(pdf_path) # Extract tables from PDF
        parser = StrOutputParser() # Create a parser

        initial_prompt = ChatPromptTemplate.from_template(initial_query)
        initial_chain = initial_prompt | model | parser
        initial_prompt.format(context=text, context_more=tables)
        decider = initial_chain.invoke({"context": text, "context_more": tables})

        if decider.lower() == "no":
            if os.path.exists(temp_path) and os.path.isdir(temp_path):
                shutil.rmtree(temp_path)
            return "Input is not a DPIA template"

        template_prompt = ChatPromptTemplate.from_template(template_query)
        template_chain = template_prompt | model | parser
        template_prompt.format(context=text, context_more=tables, exmaplar=exmaplar)
        answer = template_chain.invoke({"context": text, "context_more": tables, "exmaplar": exmaplar})

        follow_up_prompt = ChatPromptTemplate.from_template(follow_up_query)
        follow_up_chain = follow_up_prompt | model | parser
        follow_up_prompt.format(prev_answer=answer, context=text, exmaplar=exmaplar)
        final_answer = follow_up_chain.invoke({"prev_answer": answer, "context": text, "exmaplar": exmaplar})

        final_answer = json.dumps(json.loads(final_answer), indent=4) # Format the JSON response
        # save the template to the database
        new_template = Template(userID=data.get('user_id', ''), tempName=filename + '_prototype', tempData=final_answer)
        # Check if the template name already exists
        existing_tempName = Template.query.filter_by(userID=data.get('user_id', ''), tempName=filename + '_prototype').first()
        if existing_tempName:
            return "Template with the same name already exists"

        db.session.add(new_template)
        db.session.commit()
        if os.path.exists(temp_path) and os.path.isdir(temp_path):
            shutil.rmtree(temp_path)

        for i in range(10):
            if self.request.called_directly:  # Check if the task is being revoked
                break
            time.sleep(1)  # Simulate a long process
        
        return "Template extracted successfully"

    
@app.route('/save_template', methods=['POST'])
@jwt_required()
def save_template():
    data = request.get_json()
    tempName = data.get('tempName')
    tempData = ""
    # Open the file and read its content
    with open(BASE_DIR + f'/template/{get_jwt_identity()}/select.txt', 'r') as file:
        tempData = file.read()
    # Check if the template name already exists
    existing_tempName = Template.query.filter_by(userID=get_jwt_identity(), tempName=tempName).first()
    if existing_tempName:
        return jsonify({"error": "Template with the same name already exists"}), 400

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
    vectorstore = Chroma(collection_name=f"summary_{get_jwt_identity()}", embedding_function=embeddings, persist_directory=BASE_DIR + "/vectorDB/")

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

                existing_documents = vectorstore.get(where={
                "$and": [
                    {"file_name": file.fileName + ".pdf"},
                    {"usage": f"project_{project_id}"}
                ]
                })['ids']
            
                for ids in existing_documents:
                    vectorstore.delete(ids)

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
            if os.path.exists(folder_path_file) and os.path.isdir(folder_path_file):
                shutil.rmtree(folder_path_file)
            if os.path.exists(folder_path_dpia) and os.path.isdir(folder_path_dpia):
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
    
    dpia_list = []
    for dpia in dpias:
        try:
            template = Template.query.filter_by(tempID=dpia.tempID).first()
            temp_name = template.tempName if template else 'Deleted'
        except Exception as e:
            temp_name = '**OOPS...DELETED**'
        
        dpia_list.append({
            'dpiaID': dpia.dpiaID,
            'title': dpia.title,
            'status': dpia.status,
            'tempName': temp_name
        })

    return jsonify(dpia_list)


@app.route('/delete_dpias', methods=['POST'])
@jwt_required()
def delete_dpia():
    dpia_ids = request.get_json()

    for dpia_id in dpia_ids:
        dpia = DPIA.query.get(dpia_id) # Get the DPIA record
        dpia_files = DPIA_File.query.filter_by(dpiaID=dpia_id).all() # Get the DPIA files

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

    global process_dpia, tempID # access the global variables
    process_dpia = True 

    data = request.get_json() # Get the request data
    project_id = data.get('projectID')
    title = data.get('title')
    file_names = data.get('fileName')
    # check for existing DPIA with the same name
    existing_name = DPIA.query.filter_by(projectID=project_id, title=title).first()

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
    # Check if the template or files are empty
    if template == {} or len(file_names) == 0:
        return jsonify({'error': 'No template or files selected'}), 400
    # Check if project_id and title are empty
    if not project_id or not title:
        return jsonify({'error': 'Invalid input'}), 400
    # Check if DPIA with the same name already exists
    if existing_name:
        return jsonify({'error': 'DPIA with the same name already exists'}), 400
    
    init_dpia = DPIA(projectID=project_id, title=title, status="working", tempID=tempID)
    db.session.add(init_dpia)
    db.session.commit()
    # Add the files to the DPIA_File table
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


@celery.task(bind=True)
def generate_dpia(self, data):
    with app.app_context():
        now = time.time()
        # data = request.get_json()
        project_id = data.get('projectID') # Get the project ID
        title = data.get('title') # Get the project title
        file_names = sorted(data.get('fileName')) # Get the file names
        dpia_id = data.get('dpiaID') # Get the DPIA ID
        template = data.get('template') # Get the template

        # Create a DPIA report
        assign_model = ChatOllama(model="qwen2:7b-instruct-q8_0", temperature=0.0, num_ctx=8000)
        partition_model = ChatOllama(model="phi3:3.8b-mini-128k-instruct-q8_0", temperature=0.0, num_ctx=8000)
        general_model = ChatOllama(model="gemma2", temperature=0.0, num_ctx=8000)
        llm = ChatOpenAI(api_key=OPENAI_API_KEY, model="gpt-4o-mini", temperature=0.0)

        IMG_DIR_R = os.path.join(BASE_DIR, "figures", data.get('user_id', ''), str(project_id))
        IMG_DIR_RD = os.path.join(BASE_DIR, "figures", data.get('user_id', ''), str(project_id) + "_Description")
        UP_DIR_R = os.path.join(BASE_DIR, "uploads", data.get('user_id', ''), str(project_id))

        for directory in [IMG_DIR_R, IMG_DIR_RD]:
            check_path(directory)

        id_key = "doc_id"
        file_name = "file_name"
        embed_type = "embed_type"
        usage = "usage"

        retriever = partition_process(UP_DIR_R, data.get('user_id', ''), str(project_id), file_names, IMG_DIR_R, IMG_DIR_RD, partition_model, embeddings, 
                                      'n/a', id_key, file_name, embed_type, usage, f"project_{project_id}")
        # Assign role and backstory to the agent
        assign_query = """Based on the provided context: {context}. Provide a 'Role', and a 'Backstory' with one sentence. Your response must be in key-value JSON format."""
        assign_prompt = ChatPromptTemplate.from_template(assign_query)
        parser = StrOutputParser()
        assign_chain = assign_prompt | assign_model | parser

        dpia_text = {} # Store the DPIA text
        visited_keys = [] # Store the visited keys
        visited_sections = [] # Store the visited sections

        # Loop through each key-value pair in the data and store them in the dictionary
        for step_key, step_value in template.items():
            visited_keys.append(step_key)
            # read the content of the step, and assign the role and backstory based on the content
            overview = f"{step_key}: {step_value}\n" 
            assign_prompt.format(context=overview)
            assign_answer = assign_chain.invoke({"context": overview})
            print('DEBUG: ', assign_answer )
            assign_answer = json.loads(assign_answer)
            # Get the role and backstory
            role = assign_answer.get("Role")
            backstory = assign_answer.get("Backstory")
            # Create a writing agent
            writing_agent = Agent(
                role=role,
                goal=default_prompt,
                backstory=backstory,
                llm=general_model,
                allow_delegation=False,
                verbose=True
            )
            # Create a formatting agent
            Format_agent = Agent(
                role="DPIA report Formatter",
                goal=default_prompt,
                backstory="""A professional with experience in DPIA formatting and proofreading.""",
                llm=general_model,
                allow_delegation=False,
                verbose=True
            )
            # loop through each part of the step
            part_text = {}
            for part_key, part_value in step_value.items():
                visited_sections.append(part_key)
                prompt = part_value['content']
                from_step = part_value['from']['Step']
                from_section = part_value['from']['Section']

                context = retriever.invoke(prompt)
                sequential_answer = ''

                page_content = [f"{doc.page_content}" for doc in context]
                try:
                    rerank_content = rerank_response(prompt, page_content)
                except:
                    rerank_content = page_content
                
                if not prompt.strip():
                    part_text[f"""{part_key}"""] = ""
                else:
                    if from_step in visited_keys and from_section in visited_sections: # Check if the from_step and from_section are in the visited keys and sections
                        try:
                            prev_response = dpia_text[from_step][from_section]
                        except:
                            prev_response = part_text[from_section]
                        # use answer from previous part to be the input for the current part
                        split_content = split_text_into_chunks(''.join(rerank_content)) # Split the content into chunks, multi-chain
                        for content in enumerate(split_content):        
                            initial_answer = Task(
                                description= (f"""Background information: {prev_response}\n 
                                                Based on the background information and the provided context: {sequential_answer}, {content}\n 
                                                Provide a detailed answer to the prompt: {prompt}.
                                                References and citations are not relevant."""),
                                expected_output=(f"""Return an accurate and coherent response in a professional tone."""),
                                agent=writing_agent,
                            )

                            crew = Crew(
                                agents=[writing_agent],
                                tasks=[initial_answer],
                                processes=Process.sequential,
                            )
                            sequential_answer = crew.kickoff().raw
                    else:
                        split_content = split_text_into_chunks(''.join(page_content)) # Split the content into chunks, multi-chain
                        for content in enumerate(split_content):
                            initial_answer = Task(
                                description= (f"""Based on the provided context: {sequential_answer}\n {content}\n 
                                                Provide a detailed answer to the prompt: {prompt}.
                                                References and citations are not relevant."""),
                                expected_output=(f"""Return an accurate and coherent response in a professional tone."""),
                                agent=writing_agent,
                            )

                            crew = Crew(
                                agents=[writing_agent],
                                tasks=[initial_answer],
                                processes=Process.sequential,
                            )
                            sequential_answer = crew.kickoff().raw
                    # post process the response
                    crew = expanded_response(sequential_answer, rerank_content, prompt, writing_agent, Format_agent)
                    # final response
                    response = crew.kickoff().raw
                    part_text[f"""{part_key}"""] = f"""{response}""" # append the response to the part
            dpia_text[f"""{step_key}"""] = part_text # append the part to the step
            
        dpia_json_text = json.dumps(dpia_text, indent=4) # Format the JSON response
        dpia = json.loads(dpia_json_text)

        # Saving DPIA PDF
        pdf_generator = DPIAPDFGenerator(BASE_DIR, data.get('user_id', ''), project_id, title, dpia)
        pdf_generator.generate_pdf()

        end = time.time()
        print(f"Time taken: {(end - now)/60} minutes")

        global process_dpia
        process_dpia = False

        session.query(DPIA).\
        filter(DPIA.dpiaID == dpia_id).\
        update({'status': 'completed'})
        session.commit() 

        for i in range(10):
            if self.request.called_directly:  # Check if the task is being revoked
                break
            time.sleep(1)  # Simulate a long process
        return
        

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
    app.run(host='0.0.0.0', port=8080, debug=True, threaded=True)