from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

# defining models
class Feedback(db.Model):
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), nullable=False)
    category = db.Column(db.String(50), nullable=False)
    
    field1 = db.Column(db.Text, nullable=True)
    field2 = db.Column(db.Text, nullable=True)
    field3 = db.Column(db.Text, nullable=True)
    field4 = db.Column(db.Text, nullable=True)
    
    def __repr__(self):
        return f"<UserSubmission {self.name}, {self.category}>"

class Service(db.Model):
    Service = db.Column(db.String(255), primary_key=True)
    Service_Provider_Name = db.Column(db.String(255))
    Service_Type = db.Column(db.String(100))
    Top_B_Feature_1 = db.Column(db.String(255))
    Top_B_Feature_2 = db.Column(db.String(255))
    average_monthly_running_cost = db.Column(db.Float)
    Description = db.Column(db.Text)
    Education_Score = db.Column(db.Float)
    Health_Score = db.Column(db.Float)
    Finance_Score = db.Column(db.Float)
    Tech_Score = db.Column(db.Float)

class Visitors(db.Model):
    id = db.Column(db.String(32), primary_key=True, unique=True)