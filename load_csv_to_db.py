import pandas as pd
from flask import Flask
from models import db, Service

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///hack4pal.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db.init_app(app)

with app.app_context():
  # db.drop_all()
  db.create_all()
  df = pd.read_csv('b2bData/services_main.csv')

  for _, row in df.iterrows():
    service = Service(
      Service=row['Service'],
      Service_Provider_Name=row['Service Provider Name'],
      Service_Type=row['Service Type'],
      Top_B_Feature_1=row['Top_B_Feature_1'],
      Top_B_Feature_2=row['Top_B_Feature_2'],
      average_monthly_running_cost=row['average_monthly_running_cost'],
      Description=row['Description'],
      Education_Score=row['Education_Score'],
      Health_Score=row['Health_Score'],
      Finance_Score=row['Finance_Score'],
      Tech_Score=row['Tech_Score']
      )
    db.session.add(service)

    db.session.commit()
  print("CSV data successfully imported into SQLite.")