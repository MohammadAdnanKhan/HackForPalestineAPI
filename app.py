from flask import Flask, request, jsonify, render_template, make_response
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_limiter.errors import RateLimitExceeded
import pandas as pd
from rapidfuzz import process, fuzz
import base64
import os
from models import db, Feedback, Service, Visitors
from sqlalchemy import or_, func
from dotenv import load_dotenv
load_dotenv()

app = Flask(__name__)
CORS(app)

limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=["100 per hour"],  # Optional global default
)

@app.errorhandler(RateLimitExceeded)
def ratelimit_error(e):
    return jsonify({"error": "Rate limit exceeded. Please try again later."}), 429

# refer db.doc.md for 'how to use DB'
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DB_URI') or 'sqlite:////data/hack4pal.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# SQLite instance
db.init_app(app)

with app.app_context():
    # db.drop_all()
    db.create_all()
    
    existing_data = Service.query.all()
    if not existing_data:
        try:
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
            print("✅ CSV data successfully imported into SQLite.")
        except FileNotFoundError:
            print("❌ CSV file not found — skipping import.")

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
@limiter.limit("160 per hour", methods=["POST"])
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
@limiter.limit("25 per hour", methods=["POST", "GET"])
def feedback():
    if request.method == 'POST':
        if not request.is_json:
            return jsonify({"error": "Invalid or missing JSON"}), 400

        data = request.json
        category = data.get('category')
        
        # extract shared fields
        name = data.get('name')
        email = data.get('email')
        
        # err handling
        if (not name or not email or not category):
            return jsonify({"error": "name, email or category can't be null"}), 400

        # default empty fields
        field1 = field2 = field3 = field4 = None

        # Map categories to expected fields and data keys
        category_fields_map = {
            "Content Issue": ("contentIss", ["name", "description", "type", "link"]),
            "Feature Request": ("feature", ["description", "where"]),
            "UI/UX Problem": ("uiIss", ["work", "wrong", "device"]),
            "Trustworthiness Concern": ("trustConcern", ["issueWith", "why", "link"]),
            "Other": ("other", ["message"])
        }
        
        # Validate category
        if category not in category_fields_map:
            return jsonify({"error": "unexpected category"}), 400
        
        data_key, field_keys = category_fields_map[category]
        sub_data = data.get(data_key, {})
        
        # Extract values in correct order
        field_values = [sub_data.get(k) for k in field_keys]
        
        # Validate that all fields are non-empty
        if any(not str(v).strip() for v in field_values):
            return jsonify({"error": f"All fields must be non-empty for category '{category}'"}), 400

        # Pad to exactly 4 fields
        field_values += [None] * (4 - len(field_values))
        field1, field2, field3, field4 = field_values[:4]
        
        submission = Feedback(
            name=name,
            email=email,
            category=category,
            field1=field1,
            field2=field2,
            field3=field3,
            field4=field4
        )

        try:
            db.session.add(submission)
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            app.logger.error(f"DB error: {e}")
            return jsonify({"error": "Failed to save feedback"}), 500

        return jsonify({"message": "Submission saved!"}), 201
    
    # --------- GET Method ---------
    elif request.method == 'GET':
        category = request.args.get('category')

        if not category:
            return jsonify({"error": "category query parameter is required"}), 400

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
            return jsonify({"error": "unexpected category"}), 400
    
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
@limiter.limit("160 per hour", methods=["GET"])
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
@limiter.limit("100 per hour", methods=["POST"])
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

@app.route('/visits', methods=['GET', 'POST'])
@limiter.limit("100 per hour", methods=['GET'])
@limiter.limit("5 per hour", methods=['POST'])
def visits():
    if request.method == 'GET':
        count = Visitors.query.count()
        return jsonify({"total_visits": count}), 200
    
    elif request.method == 'POST':
        random_bytes = os.urandom(12)
        visitor_id = base64.urlsafe_b64encode(random_bytes).decode('utf-8').rstrip("=")
        
        new_visitor = Visitors(id=visitor_id)
        db.session.add(new_visitor)
        db.session.commit()
        
        # Set the ID in a cookie (not now)
        # response = make_response(jsonify({"visitor_id": visitor_id}), 201)
        # response.set_cookie('visitor_id', visitor_id, httponly=True, max_age=3600*24*7)  # 1 week

        return jsonify({"visitor_id": visitor_id}), 201

@app.route('/')
def index():
    return jsonify({"message": "The API is running."})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('FLASK_ENV', '').lower() == 'development'
    app.run(host='0.0.0.0', port=port, debug=debug)