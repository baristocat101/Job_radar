
JOBATTRUBUTE_HTML_TAG_CLASS_LIST = {
    'jobpost_title' : ["h2", '''top-card-layout__title font-sans text-lg papabear:text-xl font-bold leading-open text-color-text mb-0 topcard__title'''],
    'company' : ["span",'''topcard__flavor'''],
    'location' : ["span", '''topcard__flavor topcard__flavor--bullet'''],
    'num_applicants' : ["span", '''num-applicants__caption topcard__flavor--metadata topcard__flavor--bullet'''],
    'num_applicants_alt' : ["figcaption", '''num-applicants__caption'''],
    'description' : ["div", '''show-more-less-html__markup show-more-less-html__markup--clamp-after-5 relative overflow-hidden'''],
    'criteria_key' : ['h3', 'description__job-criteria-subheader'],
    'criteria_value' : ['span', 'description__job-criteria-text description__job-criteria-text--criteria'],
}

PATHS_POPUP_BUTTONS = [
        '''//*[@id="artdeco-global-alert-container"]/div/section/div/div[2]/button[2]''',
        "/html/body/div[4]/button",
        '''/html/body/div[3]/button''',
        '''infinite-scroller__show-more-button infinite-scroller__show-more-button--visible'''
    ]
