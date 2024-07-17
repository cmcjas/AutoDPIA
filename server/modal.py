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

class User(db.Model):
    __tablename__ = 'user'
    userID = db.Column(db.Integer, primary_key=True, autoincrement=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(128), nullable=False)

    def set_password(self, password):
        self.password = bcrypt.generate_password_hash(password).decode('utf-8')

    def check_password(self, password):
        return bcrypt.check_password_hash(self.password, password)

    def __repr__(self):
        return f'<User {self.email}>'


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
    status = db.Column(db.String(80), nullable=False)

    def __repr__(self):
        return f'<Dpia {self.title}>'
    
class Template(db.Model):
    __tablename__ = 'template'
    tempID = db.Column(db.Integer, primary_key=True, autoincrement=True)
    userID = db.Column(db.Integer, db.ForeignKey('user.userID'), nullable=False)
    tempName = db.Column(db.String, nullable=False)
    tempData = db.Column(db.JSON, nullable=False)

    def __repr__(self):
      return f'<Template {self.tempName}>'
    
class Project(db.Model):
    __tablename__ = 'project'
    projectID = db.Column(db.Integer, primary_key=True, autoincrement=True)
    userID = db.Column(db.Integer, db.ForeignKey('user.userID'), nullable=False)
    title = db.Column(db.String(80), nullable=False)
    description = db.Column(db.String(200), nullable=False)

    def __repr__(self):
      return f'<Project {self.title}>'

class DPIA_File(db.Model):
    __tablename__ = 'dpia_file'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    dpiaID = db.Column(db.Integer, db.ForeignKey('dpia.dpiaID'), nullable=False)
    fileID = db.Column(db.Integer, db.ForeignKey('file.fileID'), nullable=False)

    def __repr__(self):
        return f'<Dpia_File {self.dpiaID} {self.fileID}>'