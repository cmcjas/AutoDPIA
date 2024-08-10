import fitz
import os, re
from dotenv import load_dotenv
from langchain.evaluation import load_evaluator
from langchain_community.embeddings import OllamaEmbeddings
from langchain_openai.chat_models import ChatOpenAI
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.lib.utils import simpleSplit


load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

embeddings = OllamaEmbeddings(model="mxbai-embed-large:latest")

hf_evaluator = load_evaluator("embedding_distance", embeddings=embeddings)

llm = ChatOpenAI(api_key=OPENAI_API_KEY, model="gpt-4o-mini", temperature=0.2)

def extract_dpia_steps(pdf_path):
    # Open the PDF file
    doc = fitz.open(pdf_path)
    
    # Extract text from the entire document
    text = ""
    for page in doc:
        text += page.get_text()

    # # Define regex pattern for steps and subsections
    # step_pattern = re.compile(r"(Step \d+ - [^\n]+)")
    # subsection_pattern = re.compile(r"(Step \d+\.\d+ - [^\n]+)")
    
    # # Find all steps and their positions
    # steps = [(match.group(), match.start()) for match in re.finditer(step_pattern, text)]
    
    # # Include subsections in step content
    # extracted_steps = {}
    # for i, (step_title, start_pos) in enumerate(steps):
    #     if i < len(steps) - 1:
    #         next_step_start = steps[i + 1][1]
    #         step_content = text[start_pos:next_step_start].strip()
    #     else:
    #         step_content = text[start_pos:].strip()

    #     # Capture subsections within the current step
    #     subsections = [(match.group(), match.start()) for match in re.finditer(subsection_pattern, step_content)]
    #     if subsections:
    #         step_text_parts = []
    #         for j, (subsection_title, sub_start_pos) in enumerate(subsections):
    #             if j < len(subsections) - 1:
    #                 subsection_content = step_content[sub_start_pos:subsections[j + 1][1]].strip()
    #             else:
    #                 subsection_content = step_content[sub_start_pos:].strip()
    #             step_text_parts.append(subsection_content)
    #         step_content = "\n\n".join(step_text_parts)
        
    #     extracted_steps[step_title] = step_content
    
    # return extracted_steps
    return text

# Example usage
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
pdf_path = os.path.join(BASE_DIR, 'dpias', '1', '1', 'gemma2.pdf')

# dpia_steps = extract_dpia_steps(pdf_path)
content = extract_dpia_steps(pdf_path)

genDoc_query = """I'm providing a DPIA report that's been generated from a set of documents. 
Based on the provided report text information: {context} \n
Please construct a detailed Risk Assessment report that would have been used to produce the DPIA report.
"""

assign_prompt = ChatPromptTemplate.from_template(genDoc_query)
parser = StrOutputParser()
assign_chain = assign_prompt | llm | parser


doc_content = []
# Print extracted steps and their content
# for step, content in dpia_steps.items():

genDoc_query.format(context=content)
llm_answer = assign_chain.invoke({"context": content})
doc_content.append(llm_answer + "\n")  # Add a newline after each content


def save_content_to_pdf(doc_content, pdf_filename):
    # Create a PDF with the specified filename
    c = canvas.Canvas(pdf_filename, pagesize=letter)
    width, height = letter
    
    # Set a starting position
    margin = 40
    y_position = height - margin  # Start near the top of the page
    line_height = 12  # Line height for text
    max_line_width = width - 2 * margin  # Width available for text
    
    # Loop through each content in doc_content and add it to the PDF
    for content in doc_content:
        text_lines = content.split("\n")
        for line in text_lines:
            # Wrap the text to fit within the page width
            wrapped_lines = simpleSplit(line, c._fontname, c._fontsize, max_line_width)
            for wrapped_line in wrapped_lines:
                c.drawString(margin, y_position, wrapped_line)
                y_position -= line_height

                # If the y_position is too low, create a new page
                if y_position < margin:
                    c.showPage()
                    y_position = height - margin
    
    # Save the PDF file
    c.save()

# Example usage
pdf_filename = os.path.join(BASE_DIR, 'dpias', '1', '1', 'generated_doc_4.pdf')
save_content_to_pdf(doc_content, pdf_filename)




  

        







    

