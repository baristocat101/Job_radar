DATACOLOUMNS = ['id', 'score', 'deadline', "is_active" , 'jobpost_title', 
            'company', 'score_details', 'description', 'num_applicants', 'Seniority level', 'date','location', 
            'Employment type', 'Job function', "Industries",
            'href']

# first list: words to include
# second list: words to exclude
DOMAIN_MARKERS = [
                    [["Data Scientist"]],
                    [["ML", "Machine Learning"]],
                    [["Engineer", "BI", "MLOps"], ["Software", "Backend", "Frontend", "Programmer", "Developer",  "DevOps"]],
                    [["Statistician", "Statistics", "Statistiker"]],
                    [["Quantitative", "Analyst", "Analytical"], ['Cybersecurity', 'IT', 'Business', 'Finance ', 'HR', 'Marketing', 'Financial']],
                    [["Python"]], #"Backend", "Frontend", "Programmer", "Developer",  "DevOps"
                ]