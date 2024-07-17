import os
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Table, TableStyle, Paragraph, SimpleDocTemplate, Spacer, Frame, PageTemplate, PageBreak

from langchain_community.vectorstores import Chroma
from langchain_community.embeddings import OllamaEmbeddings
from langchain_core.documents import Document
from langchain_community.document_loaders import TextLoader
from langchain.storage import InMemoryStore
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain.retrievers import ParentDocumentRetriever


# class DPIAPDFGenerator:
#     def __init__(self, base_dir, jwt_identity, project_id, title, dpia):
#         self.base_dir = base_dir
#         self.jwt_identity = jwt_identity
#         self.project_id = project_id
#         self.title = title
#         self.dpia = dpia
#         self.pdf_path = os.path.join(self.base_dir, "dpias", str(self.jwt_identity), str(self.project_id))
#         self.pdf_filename = f"{self.pdf_path}/{self.title}.pdf"
#         self.width, self.height = A4

#     def draw_table(self, story):
#         data = []
#         styles = getSampleStyleSheet()
#         row_colors = []
#         for i, (step, content) in enumerate(self.dpia.items()):
#             data.append([Paragraph(f"<b>{step}</b>", styles['Normal']), ""])
#             row_colors.append(colors.lightblue if i % 2 == 0 else colors.lightgrey)
#             for sub_step, description in content.items():
#                 description = description.replace("\n", "<br/>")
#                 data.append([Paragraph(f"<b>{sub_step}</b>", styles['Normal']), Paragraph(description, styles['Normal'])])
#                 row_colors.append(None)  # No color for sub-steps

#         table = Table(data, colWidths=[self.width * 0.2, self.width * 0.7], splitInRow=1, repeatRows=1)
#         table.setStyle(TableStyle([
#             ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
#             ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
#             ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
#             ('VALIGN', (0, 0), (-1, -1), 'TOP'),
#             ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
#             ('FONTSIZE', (0, 0), (-1, -1), 10),
#             ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
#             ('GRID', (0, 0), (-1, -1), 1, colors.black),
#             ('LEFTPADDING', (0, 0), (-1, -1), 10),
#             ('RIGHTPADDING', (0, 0), (-1, -1), 10),
#             ('TOPPADDING', (0, 0), (-1, -1), 10),
#             ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
#         ]))

#         # Apply row colors
#         for row_idx, color in enumerate(row_colors):
#             if color:
#                 table.setStyle(TableStyle([
#                     ('BACKGROUND', (0, row_idx), (-1, row_idx), color)
#                 ]))
        
#         story.append(table)

#     def generate_pdf(self):
#         if not os.path.exists(self.pdf_path):
#             os.makedirs(self.pdf_path)
        
#         doc = SimpleDocTemplate(self.pdf_filename, pagesize=A4, topMargin=30, bottomMargin=30)
#         story = []
        
#         # Title
#         styles = getSampleStyleSheet()
#         title = Paragraph("Data Protection Impact Assessment (DPIA) Report", styles['Title'])
#         story.append(title)
#         story.append(Spacer(1, 10))
        
#         # Draw the table
#         self.draw_table(story)
#         # Define a frame and template to manage content flow
#         frame = Frame(doc.leftMargin, doc.bottomMargin, doc.width, doc.height - 2 * doc.bottomMargin, id='normal') # Adjust height for page number space
#         template = PageTemplate(id='test', frames=frame, onPage=self.add_page_number)
#         doc.addPageTemplates([template])

#         # Build the PDF
#         doc.build(story, onFirstPage=self.add_page_number, onLaterPages=self.add_page_number)

#     def add_page_number(self, canvas, doc):
#         page_num = canvas.getPageNumber()
#         text = f"Page {page_num}"
#         canvas.drawRightString(doc.pagesize[0] - 30, 15, text)  # Using doc.pagesize[0] to get the width of the page

# # Example usage
# dpia_content = {'Step 1 - Identify and Assess Risks': {'Identified Risks': "**Document Validator's Final Assessment**\n\n1. **Risk:** Loss of Performance when Training Dataset is Reduced\n**Likelihood of harm:** Probable\n**Severity of harm:** Significant\n**Overall risk:** Medium\n**Action:** Conduct thorough testing and validation to ensure that the performance reduction does not compromise the accuracy or reliability of the pre-training methods.\n\n2. Inconsistency in Pre-Training Methods\n**Risk:** Possible\n**Likelihood of harm:** Minimal\n**Severity of harm:** None\n**Overall risk:** Low\n**Action:** Implement a consistent pre-training strategy and monitor the results to ensure that the inconsistencies do not affect the overall performance.\n\n3. Overfitting due to Large Training Dataset\n**Risk:** Remote\n**Likelihood of harm:** Minimal\n**Severity of harm:** None\n**Overall risk:** Low\n**Action:** Apply regularization techniques and monitoring mechanisms to prevent overfitting and ensure that the model generalizes well.\n\n4. Insufficient Data for Fine-Tuning\n**Risk:** Possible\n**Likelihood of harm:** Significant\n**Severity of harm:** High\n**Overall risk:** Medium\n**Action:** Gather additional data or explore alternative fine-tuning strategies to ensure that the pre-trained models generalize well to new tasks.\n\n5. Computational Cost and Resources\n**Risk:** Probable\n**Likelihood of harm:** Severe\n**Severity of harm:** Critical\n**Overall risk:** High\n**Action:** Optimize the computational costs by utilizing cloud computing resources, GPU acceleration, or distributed training to minimize downtime and ensure seamless processing.\n\n6. Limited Interpretability of Pre-Trained Models\n**Risk:** Possible\n**Likelihood of harm:** Minimal\n**Severity of harm:** Low\n**Overall risk:** Low\n**Action:** Implement model-agnostic interpretability techniques, such as feature importance analysis or partial dependence plots, to gain insights into the pre-trained models' behavior.\n\n7. Lack of Transparency in Pre-Training Process\n**Risk:** Remote\n**Likelihood of harm:** Minimal\n**Severity of harm:** Low\n**Overall risk:** Low\n**Action:** Maintain detailed documentation and version control of the pre-training process to ensure transparency and reproducibility of the results.\n\n**Recommendation:** To minimize the risks associated with these potential issues, I recommend implementing a thorough testing and validation process for the pre-trained models. Additionally, monitoring the performance and consistency of the models during training and fine-tuning can help detect any potential issues early on. **Recommendation:** To minimize the risks associated with these potential issues, I recommend implementing a thorough testing and validation process for the pre-trained models. Additionally, monitoring the performance and consistency of the models during training and fine-tuning can help detect any potential issues early on."}, 'Step 2 - Identify Measures to Reduce Risk': {'Identified Solutions': "**Document Validator's Final Assessment**\n\n1. **Risk:** Loss of Performance when Training Dataset is Reduced\n**Solution:** Implement techniques such as data augmentation and transfer learning to minimize the impact of reduced training dataset.\n**Effect:** Reduced\n**Residual Risk:** Medium\n**Measure Approved:** Y/N\n\n2. **Risk:** Inconsistency in Pre-Training Methods\n**Solution:** Develop a consistent pre-training strategy by standardizing the input data, model architecture, and hyperparameters.\n**Effect:** Accepted\n**Residual Risk:** Low\n**Measure Approved:** Y/N\n\n3. **Risk:** Overfitting due to Large Training Dataset\n**Solution:** Apply regularization techniques such as dropout and L1/L2 penalty, and monitor the performance on a validation set.\n**Effect:** Reduced\n**Residual Risk:** Low\n**Measure Approved:** Y/N\n\n4. **Risk:** Insufficient Data for Fine-Tuning\n**Solution:** Gather additional data or explore alternative fine-tuning strategies, such as transfer learning or few-shot learning.\n**Effect:** Accepted\n**Residual Risk:** Medium\n**Measure Approved:** Y/N\n\n5. **Risk:** Computational Cost and Resources\n**Solution:** Optimize the computational costs by utilizing cloud computing resources, GPU acceleration, or distributed training.\n**Effect:** Eliminated\n**Residual Risk:** Low\n**Measure Approved:** Y/N\n\n6. **Risk:** Limited Interpretability of Pre-Trained Models\n**Solution:** Implement model-agnostic interpretability techniques, such as feature importance analysis or partial dependence plots.\n**Effect:** Reduced\n**Residual Risk:** Medium\n**Measure Approved:** Y/N\n\n7. **Risk:** Lack of Transparency in Pre-Training Process\n**Solution:** Maintain detailed documentation and version control of the pre-training process.\n**Effect:** Accepted\n**Residual Risk:** Low\n**Measure Approved:** Y/N"}}

# pdf_generator = DPIAPDFGenerator(base_dir=".", jwt_identity=123, project_id=456, title="DPIA Example", dpia=dpia_content)
# pdf_generator.generate_pdf()


import os

# Path to your parent directory
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
path = os.path.join(BASE_DIR, 'vectorDB', '1', '1', 'parentData')

# Get the list of folders in the directory
folder_list = [f for f in path if os.path.isdir(os.path.join(path, f))]

# The selected list that needs to be ordered
selected_list = ['Paper2.pdf', 'Paper1.pdf', 'ComfyUI_00904_.pdf', 'group20_ManChunChan.pdf']

# Create a mapping from folder names to their index positions
folder_index_map = {folder: index for index, folder in enumerate(folder_list)}

# Sort the selected_list based on the order in folder_list
sorted_selected_list = sorted(selected_list, key=lambda x: folder_index_map.get(x, float('inf')))

print("Original selected list:", selected_list)
print("Sorted selected list:", sorted_selected_list)




    




        







    

