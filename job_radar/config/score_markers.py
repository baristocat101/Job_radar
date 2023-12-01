generelle_score_markers = {
    "python" : 3,
    "programming" : 3,
    " ml " : 3,
    "machine learning" : 3,
    "object-oriented" : 3,
    "data mining" : 3,
    "data analyse" : 1
}

kompetence_score_markers = {
    "mathematically" : 1,
    "mathematics" : 1,
    "statistics": 3,
    "statistical":3,
    "python" : 3,
    " r " : 2,
    "optimization" : 1,
    "modeling" : 3,
    "time series" : 3,
    "c++" : 1,
    "hpc" : 1,
    "sql" : 3,
    "data" : 3,
    "azure" : 2,
    "databricks" : 2,
    "spark" : 2,
    " sop " : 2,
    " gmp " : 1,
    " etl " : 3,
    "github" : 3,
    "azure devops" : 2,
    "rest api" : 1,
    "git" : 2,
    "visualization": 2,
    "deep learning": 3,
    "graphs":2,
    "dashboard":2,
    "unit-test": 3,
    "test-based": 3
}

domain_score_markers = {
    'data scientist' : 3,
    'machine learning' : 3,
    'python' : 2
}

num_applicants_score_markers = {
    (0, 25): 3,
    (26, 50): 2,
    (51, 75): 1,
    (76, 100): -2,
    (100, 130): -4,
    (130, float('inf')): -6
}

industry_score_markers = {
    "Biotechnology" : 1,
    "Chemical Manufacturing" : 3,
    "Chemical Raw Materials Manufacturing" : 3,
    "Chemicals" : 3,
    "Civil Engineering" : 1,
    "Climate Data and Analytics" : 2,
    "Computer Software" : 1,
    "Data Infrastructure and Analytics" : 3,
    "Financial Services" : 1,
    "Fuel Cell Manufacturing" : 3,
    "Funds and Trusts" : 2,
    "Information Services" : 1,
    "Information Technology and Services" : 1,
    "Insurance" : 2,
    "Insurance Carriers" : 2,
    "International Trade and Development" :3,
    "Investment Management" : 3,
    "Investment Banking" : 3,
    "Investment Advice" : 3,
    "IT Services and IT Consulting" : 2,
    "IT System Custom Software Development" : 2,
    "IT System Data Services" : 2,
    "Logistics and Supply Chain" : 3,
    "Management Consulting" : 3,
    "Medical Device" : 1,
    "Nanotechnology" : 3,
    "Nanotechnology Research" : 3,
    "Oil & Energy" : 2,
    "Paint, Coating, and Adhesive Manufacturing" : 2,
    "Pension Funds" : 2,
    "Pharmaceutical Manufacturing" : 3,
    "Pharmaceuticals" : 3,
    "Renewable Energy Equipment Manufacturing" : 3,
    "Renewable Energy Power Generation" : 3,
    "Renewables & Environment" : 3,
    "Research" : 3,
    "Services for Renewable Energy" : 3,
    "Software Development" : 1,
    "Trusts and Estates" : 3,
    "Venture Capital & Private Equity" : 3,
    "Venture Capital and Private Equity Principals" : 3
}

jobfunction_score_markers = {
    "Consulting" : 3,
    "Engineering" : 3,
    "Entrepreneurship" : 2,
    "Information Technology" : 1,
    "Research" : 3
}

senioritylevel_score_markser = {
    "Entry level" : 3,
    "Mid-Senior level" : -4
}

age_score_markser = {
     0: 0,
     1: 0,
     2: 1,
     3: 2,
     4: 3
}

score_markers = [generelle_score_markers, kompetence_score_markers, domain_score_markers, 
                 num_applicants_score_markers, industry_score_markers, jobfunction_score_markers,
                 senioritylevel_score_markser, age_score_markser]