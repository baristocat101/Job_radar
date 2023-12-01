from config.datastructure import DOMAIN_MARKERS

SEARCH_KEYWORDS = [
    ["Data%20Scientist", "Machine%20Learning", "Data%20Engineer", "Statistiker", "Analyst", "Python"],
    ["location=Hovedstaden%2C Danmark"],
]


def title_filtering(title, current_domain):
    def _determine_if_correct_domain(title, current_domain):
    
        # find out if any job post belong to another dataframe
        domain_marker = DOMAIN_MARKERS[current_domain]

        is_included = False
        is_included = any(keyword.lower() in title.lower() 
                          for keyword in domain_marker[0])

        # choose whether an exclude filter is needed
        if len(domain_marker) > 1:
            is_excluded = (any(keyword.lower() in title.lower() 
                                  for keyword in domain_marker[1]))
        else:
            is_excluded = False

        if is_excluded:
            is_included = False
                
        return is_included  
    

    # filter off based on seniority and correct domain classification
    is_excluded = any(keyword in title.lower() 
                     for keyword in ["senior", "lead", "head of", "principal", "director", "sr.", "manager", "relocation", "junior", "relocate", "erfaren"])
    is_included = _determine_if_correct_domain(title, current_domain)
    
    is_stored = True
    if is_excluded == True or is_included == False:
        is_stored = False

    return is_stored 


def attribute_filtering(job_info_dic):
    is_stored = True

    if (job_info_dic['Employment type'] != "Full-time" or 
        job_info_dic['num_applicants'] > 150
        ):
    
        is_stored = False

    return is_stored