"""
Additional utilities for Learner Recommendations.
"""
import logging
import requests

from algoliasearch.exceptions import RequestException, AlgoliaUnreachableHostException
from algoliasearch.search_client import SearchClient
from django.conf import settings

from common.djangoapps.student.models import CourseEnrollment
from openedx.core.djangoapps.catalog.utils import get_course_data


log = logging.getLogger(__name__)

COURSE_LEVELS = [
    'Introductory',
    'Intermediate',
    'Advanced'
]


class AlgoliaClient:
    """ Class for instantiating an Algolia search client instance. """
    algolia_client = None
    algolia_app_id = settings.ALGOLIA_APP_ID
    algolia_search_api_key = settings.ALGOLIA_SEARCH_API_KEY

    @classmethod
    def get_algolia_client(cls):
        """ Get Algolia client instance. """
        if not cls.algolia_client:
            if not (cls.algolia_app_id and cls.algolia_search_api_key):
                return None

            cls.algolia_client = SearchClient.create(cls.algolia_app_id, cls.algolia_search_api_key)

        return cls.algolia_client


def _remove_user_enrolled_course_keys(user, course_keys):
    """
    Remove the course keys a user is already enrolled in
    and returns enrollable course keys.
    """
    user_enrolled_course_keys = set()
    course_enrollments = CourseEnrollment.enrollments_for_user(user)

    for course_enrollment in course_enrollments:
        course_key = f"{course_enrollment.course_id.org}+{course_enrollment.course_id.course}"
        user_enrolled_course_keys.add(course_key)

    enrollable_course_keys = [course_key for course_key in course_keys if course_key not in user_enrolled_course_keys]
    return enrollable_course_keys


def get_algolia_courses_recommendation(course_data):
    """
    Get courses recommendation from Algolia search.

    Args:
        course_data (dict): Course data to create the search query.

    Returns:
        Response object with courses recommendation from Algolia search.
    """
    algolia_client = AlgoliaClient.get_algolia_client()

    search_query = " ".join(course_data["skill_names"])
    searchable_course_levels = [
        f"level:{course_level}"
        for course_level in COURSE_LEVELS
        if course_level != course_data["level_type"]
    ]
    if algolia_client and search_query:
        algolia_index = algolia_client.init_index(settings.ALGOLIA_COURSES_RECOMMENDATION_INDEX_NAME)
        try:
            # Algolia search filter criteria:
            # - Product type: Course
            # - Courses are available (enrollable)
            # - Courses should not have the same course level as the current course
            # - Exclude current course from the results
            results = algolia_index.search(
                search_query,
                {
                    "filters": f"NOT active_run_key:'{course_data['key']}'",
                    "facetFilters": ["availability:Available now", "product:Course", searchable_course_levels],
                    "optionalWords": f"{search_query}",
                }
            )

            return results
        except (AlgoliaUnreachableHostException, RequestException) as ex:
            log.warning(f"Unexpected exception while attempting to fetch courses data from Algolia: {str(ex)}")

    return {}


def get_amplitude_course_recommendations(user_id, recommendation_id):
    """
    Get personalized recommendations from Amplitude.

    Args:
        user_id: The user for which the recommendations need to be pulled
        recommendation_id: Amplitude model id

    Returns:
        is_control (bool): Control group value for the user
        has_is_control (bool): Boolean value indicating if the control group for
        the user has been decided.
        recommended_course_keys (list): Course keys returned by Amplitude.
    """
    headers = {
        "Authorization": f"Api-Key {settings.AMPLITUDE_API_KEY}",
        "Content-Type": "application/json",
    }
    params = {
        "user_id": user_id,
        "get_recs": True,
        "rec_id": recommendation_id,
    }
    response = requests.get(settings.AMPLITUDE_URL, params=params, headers=headers)
    if response.status_code == 200:
        response = response.json()
        recommendations = response.get("userData", {}).get("recommendations", [])
        if recommendations:
            is_control = recommendations[0].get("is_control")
            has_is_control = recommendations[0].get("has_is_control")
            recommended_course_keys = recommendations[0].get("items")
            return is_control, has_is_control, recommended_course_keys

    return True, False, []


def filter_recommended_courses(user, unfiltered_course_keys, recommendation_count=5):
    """
    Returns the filtered course recommendations. The unfiltered course keys
    pass through the following filters:
        1. Remove courses that a user is already enrolled in
        2. <To be added later>

    Returns:
        filtered_recommended_courses (list): A list of course objects. Each item has
        the following details for a course:
            - course key (course_key)
            - title
            - partner image url (logo_image_url)
            - marketing url for the course (marketing_url)
    """
    filtered_recommended_courses = []
    fields = ["title", "owners", "marketing_url"]

    # Remove the course keys a user is already enrolled in
    enrollable_course_keys = _remove_user_enrolled_course_keys(user, unfiltered_course_keys)[:recommendation_count]

    for course_id in enrollable_course_keys:
        course_data = get_course_data(course_id, fields)
        if course_data:
            filtered_recommended_courses.append(
                {
                    "course_key": course_id,
                    "title": course_data["title"],
                    "logo_image_url": course_data["owners"][0]["logo_image_url"],
                    "marketing_url": course_data.get("marketing_url"),
                }
            )

    return filtered_recommended_courses
