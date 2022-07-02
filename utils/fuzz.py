from rapidfuzz import fuzz, process
# from rapidfuzz.distance.Levenshtein import normalized_similarity
from rapidfuzz.distance.JaroWinkler import similarity
from beanie.odm.queries.find import FindMany
from copy import deepcopy
# def scorer(s1, s2, **kwargs):
#     return normalized_distance()


def fuzzy_autocomplete(query: str, choices):
    results = process.extract(query, choices, scorer=fuzz.WRatio, limit=25, score_cutoff=50)
    return results


async def fuzzy_find_obj(query: str, db_query: FindMany):
    query = query.replace("_", " ")
    obj = await deepcopy(db_query).find({'name': query}).first_or_none()
    if obj is None:  # user gave us incorrect or incomplete name
        obj_choices = await deepcopy(db_query).find().to_list()
        obj_choices = {o: o.name for o in obj_choices}
        result = process.extractOne(query, obj_choices, scorer=fuzz.WRatio, score_cutoff=50)

        if result is None:
            raise ValueError(f"Can't find {query}!")

        obj = result[2]
    return obj
