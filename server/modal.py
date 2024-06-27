from flask_login import UserMixin
from sqlalchemy.orm import Mapped, mapped_column, DeclarativeBase, relationship
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import Integer, String
from sqlalchemy.ext.hybrid import hybrid_property
from flask_bcrypt import Bcrypt


'''         Class Set Up For SQL Database             '''

# Base class for SQLAlchemy models (User, Project, Dpia, File)
class Base(DeclarativeBase):
  pass
bcrypt = Bcrypt()
db = SQLAlchemy(model_class=Base)

class File(db.Model):
    __tablename__ = 'file'
    fileID = db.Column(db.Integer, primary_key=True, autoincrement=True)
    projectID = db.Column(db.Integer, db.ForeignKey('project.projectID'), nullable=True)
    fileName = db.Column(db.String(255), nullable=False)

    def __repr__(self):
        return f'<File {self.fileName}>'

class DPIA(db.Model):
    __tablename__ = 'dpia'
    dpiaID = db.Column(db.Integer, primary_key=True, autoincrement=True)
    projectID = db.Column(db.Integer, db.ForeignKey('project.projectID'), nullable=False)
    title = db.Column(db.String(255), nullable=False)

    def __repr__(self):
        return f'<Dpia {self.title}>'
    
class Template(db.Model):
    __tablename__ = 'template'
    tempID = db.Column(db.Integer, primary_key=True, autoincrement=True)
    tempName = db.Column(db.String, nullable=False)
    tempData = db.Column(db.JSON, nullable=False)

    def __repr__(self):
      return f'<Template {self.tempName}>'
    
class Project(db.Model):
    projectID = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(80), nullable=False)
    description = db.Column(db.String(200), nullable=False)

    def __repr__(self):
      return f'<Template {self.title}>'
