from flask import Flask, request, jsonify, render_template
from flask_cors import CORS  
import pandas as pd
from rapidfuzz import process, fuzz
import os

from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)
CORS(app) 

# refer db.doc.md for 'how to use DB'
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DB_URI') or 'sqlite:///hack4pal.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# SQLite instance
db = SQLAlchemy(app)

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

with app.app_context():
    # db.drop_all()
    db.create_all()

brands = pd.read_csv("data/brands.csv")
companies = pd.read_csv("data/companies.csv")

#irrelevant data
brands_to_rem = ['id', 'website', 'allOf']
companies_to_rem = ['id']

brands['name_lower'] = brands['name'].str.lower()
companies['name_lower'] = companies['name'].str.lower()

brands_names = brands['name_lower'].dropna().tolist()
companies_names = companies['name_lower'].dropna().tolist()

#low threshold for handling typos entered by the user
def fuzzy_search(name, choices, threshold=72):
    name = name.lower()
    match = process.extractOne(name, choices, scorer=fuzz.token_sort_ratio)
    if (match and match[1] >= threshold):
        return match[0]  
    return None

@app.route('/search', methods=['POST'])
def search():
    data = request.get_json()
    input_name = data.get('name', '').strip().lower()
    
    if not input_name:
        return jsonify({'error': 'No name provided, enter a name to search'}), 400

    # Search in brands
    match_name = fuzzy_search(input_name, brands_names)
    if match_name:
        row = brands[brands['name_lower'] == match_name]
        if (not row.empty):
            result = (
                row.drop(columns=brands_to_rem + ['name_lower'])
                .iloc[0]
                .where(pd.notnull, None)
                .to_dict()
            )
            return jsonify({
                'source': 'brands',
                'match': row.iloc[0]['name'],
                'data': result
            })

    # Search in companies
    match_name = fuzzy_search(input_name, companies_names)
    if match_name:
        row = companies[companies['name_lower'] == match_name]
        if (not row.empty):
            result = (
                row.drop(columns=companies_to_rem + ['name_lower'])
                .iloc[0]
                .where(pd.notnull, None)
                .to_dict()
            )
            return jsonify({
                'source': 'companies',
                'match': row.iloc[0]['name'],
                'data': result
            })

    return jsonify({'result': 'Not in our list. There is high probability that the product is not in boycott list'}), 200

@app.route('/feedback', methods=['GET', 'POST'])
def feedback():
    if (request.method == 'POST'):
        data = request.json
        category = data.get('category')
        
        # extract shared fields
        name = data.get('name')
        email = data.get('email')
        
        # err handling
        if (not name or not email or not category):
            return jsonify({"message": "name, email or category can't be null"}), 400

        # default empty fields
        field1 = field2 = field3 = field4 = None

        # conditional mapping based on category
        if category == 'Content Issue':
            field1 = data['contentIss'].get('name')
            field2 = data['contentIss'].get('description')
            field3 = data['contentIss'].get('type')
            field4 = data['contentIss'].get('link')

        elif category == 'Feature Request':
            field1 = data['feature'].get('description')
            field2 = data['feature'].get('where')

        elif category == 'UI/UX Problem':
            field1 = data['uiIss'].get('work')
            field2 = data['uiIss'].get('wrong')
            field3 = data['uiIss'].get('device')

        elif category == 'Trustworthiness Concern':
            field1 = data['trustConcern'].get('issueWith')
            field2 = data['trustConcern'].get('why')
            field3 = data['trustConcern'].get('link')

        elif category == 'Other':
            field1 = data['other'].get('message')
            
        else:
            return jsonify({"message": "unexpected category"}), 400
        
        if all(not f for f in [field1, field2, field3, field4]):
            return jsonify({"message": "Bad request: no field was populated"}), 400

        submission = Feedback(
            name=name,
            email=email,
            category=category,
            field1=field1,
            field2=field2,
            field3=field3,
            field4=field4
        )

        db.session.add(submission)
        db.session.commit()

        return jsonify({"message": "Submission saved!"}), 201
    
    # --------- GET Method ---------
    elif request.method == 'GET':
        data = request.json
        category = data.get('category')

        if not category:
            return jsonify({"message": "category body parameter is required"}), 400

        feedbacks = Feedback.query.filter_by(category=category).all()
        
        # Mapping field names based on category
        category_fields = {
            "Content Issue": ["name", "description", "type", "link"],
            "Feature Request": ["description", "where"],
            "UI/UX Problem": ["work", "wrong", "device"],
            "Trustworthiness Concern": ["issueWith", "why", "link"],
            "Other": ["message"]
        }
        
        field_keys = category_fields.get(category)
        
        if not field_keys:
            return jsonify({"message": "unexpected category"}), 400
    
        results = []
        for f in feedbacks:
            # Prepare shared fields
            base = {
                "id": f.id,
                "name": f.name,
                "email": f.email,
                "category": f.category,
            }

            # Extract values in order from field1 to field4
            values = [f.field1, f.field2, f.field3, f.field4][:len(field_keys)]

            # Reconstruct category-specific fields
            category_data = dict(zip(field_keys, values))

            # Merge and append to results
            base.update({"data": category_data})
            results.append(base)

    return jsonify(results), 200

@app.route('/usage')
def usage():
    return render_template('usage.html')

@app.route('/')
def index():
    return jsonify({"message": "The API is running."})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)