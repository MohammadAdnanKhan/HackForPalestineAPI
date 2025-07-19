import pandas as pd

# Load both CSV files
services = pd.read_csv('services.csv')
ranks = pd.read_csv('ranks.csv')

# Select only the relevant columns from ranks
ranks_subset = ranks[[
    'Service', 'Service Provider Name', 'Service Type',
    'Education_Score', 'Health_Score', 'Finance_Score', 'Tech_Score'
]]

# Merge on common columns
merged = services.drop(columns=['Education_Score', 'Health_Score', 'Finance_Score', 'Tech_Score'], errors='ignore')
merged = merged.merge(ranks_subset, on=['Service', 'Service Type'], how='left')

# Save the updated CSV
merged.to_csv('services_main.csv', index=False)