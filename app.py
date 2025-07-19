from flask import Flask, request, jsonify, render_template
from flask_cors import CORS  
import pandas as pd
from rapidfuzz import process, fuzz
import os
from models import db, Feedback, Service
from sqlalchemy import or_, func

app = Flask(__name__)
CORS(app) 

# refer db.doc.md for 'how to use DB'
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DB_URI') or 'sqlite:///hack4pal.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# SQLite instance
db.init_app(app)

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

@app.route('/service', methods=['GET'])
def suggest_services():
    name = request.args.get('name', '').strip()
    
    query = Service.query.filter(
        or_(
            Service.Service.ilike(f"%{name}%"),
            Service.Service_Type.ilike(f"%{name}%")
        )
    )
    matches = query.limit(10).all()
    
    return jsonify([{
        "Service_Name": s.Service,
        "Service_Type": s.Service_Type,
        "Service_Provider": s.Service_Provider_Name,
        "Feature_1": s.Top_B_Feature_1,
        "Feature_2": s.Top_B_Feature_2
    } for s in matches])

@app.route('/service', methods=['POST'])
def suggest_replacements():
    data = request.json
    
    domain = data.get('domain')
    service_name = data.get('name')
    service_type = data.get('type')
    
    if not all([domain, service_name, service_type]):
        return jsonify({"error": "Missing domain, type, or name"}), 400
    
    # Get selected service
    selected = Service.query.filter_by(Service=service_name, Service_Type=service_type).first()
    if not selected:
        return jsonify({"error": "Invalid Service selected"}), 404
    
    # 'Other' domain case
    if domain.lower() == 'other':
        # Average score of selected service
        selected_avg = (
            (selected.Education_Score or 0) +
            (selected.Health_Score or 0) +
            (selected.Finance_Score or 0) +
            (selected.Tech_Score or 0)
        ) / 4.0

        # Get all same-type services with better (lower) average score
        suggestions = Service.query.filter(
            Service.Service_Type == service_type
        ).filter(
            (
                (func.coalesce(Service.Education_Score, 0) +
                 func.coalesce(Service.Health_Score, 0) +
                 func.coalesce(Service.Finance_Score, 0) +
                 func.coalesce(Service.Tech_Score, 0)) / 4.0
                <= selected_avg
            )
            # Service.Service != service_name  # exclude original
        ).order_by(
            (func.coalesce(Service.Education_Score, 0) +
             func.coalesce(Service.Health_Score, 0) +
             func.coalesce(Service.Finance_Score, 0) +
             func.coalesce(Service.Tech_Score, 0)) / 4.0
        ).all()

        return jsonify([{
            "Service_Name": s.Service,
            "Service_Provider": s.Service_Provider_Name,
            "Service_Type": s.Service_Type,
            "Score": round((
                (s.Education_Score or 0) +
                (s.Health_Score or 0) +
                (s.Finance_Score or 0) +
                (s.Tech_Score or 0)
            ) / 4.0, 2),
            "Description": s.Description,
            "average_monthly_running_cost": s.average_monthly_running_cost,
            "Feature_1": s.Top_B_Feature_1,
            "Feature_2": s.Top_B_Feature_2
        } for s in suggestions])
    
    # Normal domain case (education, health, finance, tech)
    # Domain column mapping
    domain_column_map = {
        "education": Service.Education_Score,
        "health": Service.Health_Score,
        "finance": Service.Finance_Score,
        "tech": Service.Tech_Score
    }
    
    if domain not in domain_column_map:
        return jsonify({"error": "Invalid domain"}), 400
    
    domain_col = domain_column_map[domain]
    selected_score = getattr(selected, f"{domain.capitalize()}_Score")
    
    # Get alternatives with better domain score
    suggestions = Service.query.filter(
        Service.Service_Type == service_type,
        domain_col <= selected_score
        # Service.Service != service_name  # exclude original
    ).order_by(domain_col).all()
    
    return jsonify([{
        "Service_Name": s.Service,
        "Service_Provider": s.Service_Provider_Name,
        "Service_Type": s.Service_Type,
        "Score": getattr(s, f"{domain.capitalize()}_Score"),
        "Description": s.Description,
        "average_monthly_running_cost": s.average_monthly_running_cost,
        "Feature_1": s.Top_B_Feature_1,
        "Feature_2": s.Top_B_Feature_2
    } for s in suggestions])

@app.route('/')
def index():
    return jsonify({"message": "The API is running."})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)