import re
import time
from datetime import datetime, timedelta
from typing import List, Union, Tuple
import logging

import pandas as pd
import langid
from googletrans import Translator
from deep_translator import GoogleTranslator
import datefinder
from nltk.tokenize import sent_tokenize

from manage_jobposts import JobStorageManager
from config.score_markers import score_markers
from log_helpers import log_big_separator, log_small_separator

logger = logging.getLogger(__name__)


def detect_language(text: str) -> str:
    lang, confidence = langid.classify(text)
    return lang


def translate_text(text: str, target_language="en") -> str:
    translator = Translator()
    translation = translator.translate(text, dest=target_language)
    return translation.text


def find_application_deadline(text: str) -> List[Union[datetime, str, None]]:
    """Find application deadline from job description, if it exists, using regular
    expressions and assumptions on how the deadline is presented in the text."""

    def _find_date_or_date_list(text: str) -> List[Union[datetime, str]]:
        # remove chars that can prevent datefinder finding dates
        text_clean = "".join(char for char in text if char.isalnum() or char.isspace())
        # Search for "as soon as possible"
        asap_match = re.search(r"as soon as possible", text_clean, re.IGNORECASE)
        if asap_match:
            # Search for followup date indicated by "no later than" or "at the latest"
            followup_date_match_str = re.search(
                r"(.{0,35})(no later than|at the latest)\b(.{35})", text, re.IGNORECASE
            )
            if followup_date_match_str:
                followup_date = next(datefinder.find_dates(followup_date_match_str[0]))
                return [followup_date]
            else:
                return ["asap"]
        # if asap not found, return all dates as list
        return list(datefinder.find_dates(text_clean))

    def _find_with_deadline_word(text: str) -> Union[None, datetime]:
        # assume deadline date is in the 40 following characters after "deadline"
        pattern = r"\bdeadline\b.{60}"
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            # Extract the 20 characters following the word "deadline"
            chars_after_deadline = match.group(0)[len("deadline") :]
            try:
                deadline_date = _find_date_or_date_list(chars_after_deadline)[0]
                return deadline_date
            except Exception:
                pass
        return None

    def _find_closest_date(text: str) -> Union[None, datetime]:
        def _validate_date(date: datetime):
            # assume that if found date is more than 3 months old, it is not the
            # an application deadline

            is_date_valid = 1
            difference = datetime.now() - date
            if difference > timedelta(days=90):
                is_date_valid = 0
            return is_date_valid

        date_list = _find_date_or_date_list(text)
        if len(date_list) == 1:
            if date_list[0] != "asap" and _validate_date(date_list[0]):
                return date_list[0]
            else:
                return None
        if date_list:
            # Find the current date
            current_date = datetime.now()
            # Find the nearest date to the current date
            nearest_date = min(date_list, key=lambda date: abs(date - current_date))
            # validate date
            if _validate_date(nearest_date):
                return nearest_date
        return None

    # first search after deadline using a potential "deadline" word
    deadline_date = _find_with_deadline_word(text)
    if deadline_date:
        if deadline_date != "asap":
            deadline_date = deadline_date.strftime("%d-%m-%Y")
        return deadline_date

    # second, find the closest date and assume it to be the deadline
    deadline_date = _find_closest_date(text)
    if deadline_date:
        if not isinstance(deadline_date, str):
            deadline_date = deadline_date.strftime("%d-%m-%Y")
        return deadline_date
    else:
        return "N/A"


def is_valid_date_format(date_string):
    try:
        datetime.strptime(date_string, "%d-%m-%Y")
        return True
    except ValueError:
        return False


def keyword_matching_scoring(row: pd.Series, current_domain) -> Tuple[int, str]:
    """Provide scores to job posts based on simply keyword matching.

    Returns the total score and a scorebard (string) containing the score details."""

    def calc_general_score(text: str):
        general_score, score_log = 0, ""
        for key, score in score_markers[0].items():
            if key in text:
                general_score += score
                score_log += f"{key} + "
        return {"score": general_score * 3, "score_log": score_log}

    def calc_competence_score(text: str):
        def _find_year_of_experience(text):
            # find statements regarding number of years of experience
            sentences = sent_tokenize(text)
            years_of_experience = 0
            for sentence in sentences:
                if "experience" in sentence.lower() and "years" in sentence.lower():
                    try:
                        years_of_experience = int(re.findall(r"\b\d+\b", sentence)[0])
                    except Exception:
                        try:
                            if re.findall(r"couple of years", sentence)[0]:
                                years_of_experience = 2
                        except Exception:
                            pass

            if years_of_experience >= 10:
                years_of_experience = 0

            return years_of_experience

        competence_score, score_log = 0, ""
        for key, score in score_markers[1].items():
            if key in text:
                competence_score += score
                score_log += f"{key} + "
        num_years_exp = _find_year_of_experience(text)
        competence_score -= 10 * int(num_years_exp)
        score_log += f"num_years_exp: {num_years_exp}"
        return {"score": competence_score * 2, "score_log": score_log}

    def calc_domain_score(domain: str):
        score = 0
        if domain.lower() in score_markers[2].keys():
            score += score_markers[2][domain.lower()]
        return {"score": score * 2, "score_log": domain}

    def calc_num_applicant_score(num_applicants: int):
        for range_, score in score_markers[3].items():
            lower_bound, upper_bound = range_
            if lower_bound <= num_applicants <= upper_bound:
                break
        return {"score": score, "score_log": str(num_applicants)}

    def calc_industry_score(industry: str):
        industry_score = 0
        if industry in score_markers[4].keys():
            industry_score += 2 * score_markers[4][industry]
        return {"score": industry_score, "score_log": f"{industry}"}

    def calc_jobfunction_score(jobfunction: str):
        jobfunction_score = 0
        if jobfunction in score_markers[5].keys():
            jobfunction_score += score_markers[5][jobfunction]
        return {"score": jobfunction_score, "score_log": f"{jobfunction}"}

    def calc_seniority_score(senioritylevel: str):
        seniority_score = 0
        if senioritylevel in score_markers[6].keys():
            seniority_score += score_markers[6][senioritylevel]
        return {"score": seniority_score * 2, "score_log": f"{senioritylevel}"}

    def calc_age_score(date_str: str):
        date = datetime.strptime(date_str, "%Y-%m-%d")
        current_date = date.now()
        age = current_date - date
        weeks_difference = age.days // 7
        if weeks_difference > max(score_markers[7].keys()):
            age_score = 4
        else:
            age_score = score_markers[7][weeks_difference]
        return {"score": age_score, "score_log": f"{weeks_difference}"}

    def _scoreboard_update(scoreboard: str, key: str, score_info: str) -> str:
        scoreboard += f"{key} : {score_info['score']}\n"
        scoreboard += score_info["score_log"]
        scoreboard += "\n--------------------\n"
        return scoreboard

    score_list = {}
    score_list["General Score"] = calc_general_score(row["description"])
    score_list["Competence Score"] = calc_competence_score(row["description"])
    score_list["Domain Score"] = calc_domain_score(current_domain)
    score_list["# Applicants Score"] = calc_num_applicant_score(row["num_applicants"])
    score_list["Industry Score"] = calc_industry_score(row["Industries"])
    score_list["Job Function Score"] = calc_jobfunction_score(row["Job function"])
    score_list["Seniority Score"] = calc_seniority_score(row["Seniority level"])
    score_list["Age Score"] = calc_age_score(row["date"])

    total_score, scoreboard = 0, ""
    for key, score_info in score_list.items():
        total_score += score_info["score"]
        scoreboard = _scoreboard_update(scoreboard, key, score_info)
    return total_score, scoreboard


def evaluate_if_active(deadline_date, industry_score_markers, df, row_idx):
    job_inactive = False

    # industries to always include
    industries = list(industry_score_markers.keys())
    industry_keepers = [industries[i] for i in [1, 2, 3, 13, 29, 30, 31]]

    # Retrieve the number of years of experience - if 2 or more -> inactive
    pattern = r"num_years_exp: (\d+)"
    match = re.search(pattern, df.loc[row_idx, "score_details"])
    if (
        match
        and int(match.group(1)) >= 3
        and df.loc[row_idx, "Industries"] not in industry_keepers
    ):
        df.loc[row_idx, "is_active"] = 0
        job_inactive = True

    # If deadline is after the current date or num applicants +110 -> inactive
    if (
        is_valid_date_format(deadline_date)
        and (
            datetime.strptime(deadline_date, "%d-%m-%Y").date() < datetime.now().date()
            or df.loc[row_idx, "num_applicants"] > 110
        )
        and df.loc[row_idx, "Industries"] not in industry_keepers
    ):
        df.loc[row_idx, "is_active"] = 0
        job_inactive = True

    return df, job_inactive


def rate_all_jobpost():
    log_big_separator(logger, "RATING JOBPOSTS")
    start_time = time.time()

    job_storage_manager = JobStorageManager(spreadsheet_name="Job_radar_aktiv")

    for ws_idx, worksheet in enumerate(
        job_storage_manager.google_sheet_manager.sheet.worksheets()[1:]
    ):
        df = job_storage_manager.google_sheet_manager.get_worksheet_as_dataframe(
            worksheet
        )

        logger.info("Rating of worksheet job posts started")
        inactive_jobs_found = False
        for row_idx, row in df.iterrows():
            # if description not in englist, tranlate it for uniform rate processing
            description = row["description"]
            language = detect_language(description)
            if len(description) > 5000 and language != "en":
                language = detect_language(description)
                chunk_size = 4999
                chunks = [
                    description[i : i + chunk_size]
                    for i in range(0, len(description), chunk_size)
                ]
                chunks_translated = [
                    GoogleTranslator(source=language, target="en").translate(x)
                    for x in chunks
                ]
                description = " ".join(chunks_translated)
                logger.info("Language translated")
            elif language != "en":
                description = GoogleTranslator(source=language, target="en").translate(
                    description
                )
                logger.info("Language translated")

            # finding application deadline
            deadline_date = find_application_deadline(description)
            df.loc[row_idx, "deadline"] = deadline_date

            current_domain = worksheet.title

            # rating based on simple keyword matching
            total_score, scoreboard = keyword_matching_scoring(row, current_domain)
            df.loc[row_idx, "score"] = total_score
            df.loc[row_idx, "score_details"] = scoreboard

            # Evalulate if jobpost should be marked inactive
            df, job_inactive = evaluate_if_active(
                deadline_date, score_markers[4], df, row_idx
            )
            if job_inactive:
                inactive_jobs_found = True

        logger.info("Updating worksheet job posts with ratings")
        df = df.sort_values(by="score", ascending=False)
        job_storage_manager.google_sheet_manager.update_google_worksheet(worksheet, df)
        if inactive_jobs_found:
            job_storage_manager.archive_inactive_jobposts(ws_idx)

    job_storage_manager.google_sheet_manager.sheet.worksheets()[0].update(
        "B1", str(datetime.now())
    )

    completion_time = time.time() - start_time
    log_small_separator(
        logger, f"All job posts rated - completion time {completion_time}"
    )


def check_for_cool_jobs(cool_score: int) -> List[str]:
    log_small_separator(logger, "checking for cool jobs")

    job_storage_manager = JobStorageManager(spreadsheet_name="Job_radar_aktiv")
    cool_job_list = []
    for worksheet in job_storage_manager.google_sheet_manager.sheet.worksheets()[1:]:
        df = job_storage_manager.google_sheet_manager.get_worksheet_as_dataframe(
            worksheet
        )
        cool_job_list.extend(
            [
                (row["id"], row["jobpost_title"])
                for _, row in df.iterrows()
                if row["score"] > cool_score
            ]
        )

    return cool_job_list
