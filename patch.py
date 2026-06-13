import json
with open('personal_details/personal_details.json', 'r') as f:
    data = json.load(f)

data['total_experience'] = "3 years"
data['skills_experience'] = {
    skill: "3 years" for skill in data.get('skills', [])
}

with open('personal_details/personal_details.json', 'w') as f:
    json.dump(data, f, indent=4)
